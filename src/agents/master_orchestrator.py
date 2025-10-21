"""
Master Orchestrator Agent - Coordinate all agents and manage workflows.

This agent orchestrates the entire content generation pipeline, managing
dependencies, resource allocation, and error handling.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from anthropic import Anthropic

from ..core.config import settings
from ..core.exceptions import WorkflowError
from ..core.logger import setup_logger
from .ced_parser import CEDParser
from .template_crafter import TemplateCrafter

logger = setup_logger(__name__)


class MasterOrchestrator:
    """
    Coordinate agent workflows for content generation.

    Responsibilities:
    - Workflow planning and execution
    - Agent coordination and dispatching
    - Resource management
    - Error handling and recovery
    - Progress tracking and reporting
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize Master Orchestrator.

        Args:
            model: Claude model for decision-making
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.claude_model_opus
        self.logger = logger
        self.workflows: Dict[str, Dict[str, Any]] = {}

        # Initialize agents
        self.ced_parser = CEDParser()
        self.template_crafter = TemplateCrafter()

    async def execute_workflow(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main workflow execution entry point.

        Args:
            task: Task dictionary with:
                - task_id: str
                - task_type: str (batch_generation, template_update, etc.)
                - request: dict with task-specific params
                - constraints: dict with limits (cost, time, etc.)

        Returns:
            Final workflow report

        Raises:
            WorkflowError: If workflow fails
        """
        self.logger.info(f"Executing workflow: {task.get('task_id')}")

        try:
            # Phase 1: Planning
            workflow_plan = self.plan_workflow(task)
            workflow_id = workflow_plan["workflow_id"]

            # Store workflow
            self.workflows[workflow_id] = {
                "plan": workflow_plan,
                "status": "executing",
                "started_at": datetime.now(),
                "task": task,
            }

            # Phase 2: Execution
            results = {}

            for stage_idx, stage in enumerate(workflow_plan["stages"], start=1):
                self.logger.info(f"Executing stage {stage_idx}: {stage}")

                # Execute stage
                stage_results = await self._execute_stage(
                    workflow_id, stage_idx, stage, task, results
                )

                # Check for failures
                if not self._check_stage_success(stage_results):
                    raise WorkflowError(f"Stage {stage_idx} failed")

                # Store results
                results.update(stage_results)

            # Phase 3: Finalization
            final_report = self._generate_final_report(
                workflow_id, results, workflow_plan, task
            )

            self.workflows[workflow_id]["status"] = "completed"
            self.logger.info(f"Workflow {workflow_id} completed successfully")

            return final_report

        except Exception as e:
            self.logger.error(f"Workflow execution failed: {e}")
            if workflow_id in self.workflows:
                self.workflows[workflow_id]["status"] = "failed"
                self.workflows[workflow_id]["error"] = str(e)
            raise WorkflowError(f"Workflow failed: {e}") from e

    def plan_workflow(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create execution plan for workflow.

        Args:
            task: Task definition

        Returns:
            Workflow plan with stages and resource allocation
        """
        task_type = task["task_type"]

        # Identify required agents
        required_agents = self._identify_required_agents(task_type)

        # Build dependency graph
        graph = self._build_dependency_graph(required_agents)

        # Create stages (topologically sorted)
        stages = self._group_into_stages(graph)

        # Estimate resources
        cost = self._estimate_cost(stages, task)
        duration = self._estimate_duration(stages, task)

        workflow_id = f"wf_{datetime.now().strftime('%Y%m%d')}_{uuid4().hex[:8]}"

        return {
            "workflow_id": workflow_id,
            "stages": stages,
            "total_stages": len(stages),
            "estimated_cost_usd": cost,
            "estimated_duration_hours": duration,
            "parallel_capacity": min(len(max(stages, key=len)), 5),
        }

    def _identify_required_agents(self, task_type: str) -> List[str]:
        """
        Map task type to required agents.

        Args:
            task_type: Type of task

        Returns:
            List of agent names
        """
        agent_requirements = {
            "batch_generation": [
                "ced_parser",
                "template_crafter",
                # "parametric_generator",  # TODO: Implement
                # "solution_verifier",      # TODO: Implement
            ],
            "template_update": [
                "template_crafter",
            ],
            "ced_update": [
                "ced_parser",
            ],
        }

        return agent_requirements.get(task_type, [])

    def _build_dependency_graph(self, agents: List[str]) -> Dict[str, List[str]]:
        """
        Create dependency graph for agents.

        Args:
            agents: List of agent names

        Returns:
            Dependency graph (agent -> list of dependencies)
        """
        # Define dependencies
        dependencies = {
            "ced_parser": [],
            "template_crafter": ["ced_parser"],
            "parametric_generator": ["template_crafter"],
            "solution_verifier": ["parametric_generator"],
        }

        # Build graph for requested agents only
        graph = {}
        for agent in agents:
            deps = [d for d in dependencies.get(agent, []) if d in agents]
            graph[agent] = deps

        return graph

    def _group_into_stages(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """
        Group agents into parallel execution stages.

        Args:
            graph: Dependency graph

        Returns:
            List of stages (each stage is a list of agents)
        """
        stages = []
        remaining = set(graph.keys())

        while remaining:
            # Find agents with no pending dependencies
            stage = []
            for agent in list(remaining):
                deps = graph[agent]
                if all(dep not in remaining for dep in deps):
                    stage.append(agent)

            if not stage:
                raise WorkflowError("Circular dependency detected")

            stages.append(stage)
            remaining -= set(stage)

        return stages

    async def _execute_stage(
        self,
        workflow_id: str,
        stage_id: int,
        stage: List[str],
        task: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute all agents in a stage concurrently.

        Args:
            workflow_id: Workflow identifier
            stage_id: Stage number
            stage: List of agent names
            task: Task definition
            previous_results: Results from previous stages

        Returns:
            Stage results dictionary
        """
        tasks = []
        for agent_name in stage:
            agent_input = self._prepare_agent_input(
                agent_name, task, previous_results
            )
            tasks.append(self._dispatch_agent(agent_name, agent_input))

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        stage_results = {}
        for agent_name, result in zip(stage, results):
            if isinstance(result, Exception):
                self.logger.error(f"Agent {agent_name} failed: {result}")
                stage_results[agent_name] = {"status": "failed", "error": str(result)}
            else:
                stage_results[agent_name] = result

        return stage_results

    async def _dispatch_agent(
        self, agent_name: str, agent_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch agent and track metrics.

        Args:
            agent_name: Agent to execute
            agent_input: Input data for agent

        Returns:
            Agent output
        """
        start = datetime.now()

        try:
            if agent_name == "ced_parser":
                result = self.ced_parser.parse_ced(agent_input)
            elif agent_name == "template_crafter":
                result = self.template_crafter.create_template(agent_input)
            else:
                raise WorkflowError(f"Unknown agent: {agent_name}")

            duration = (datetime.now() - start).total_seconds()

            return {
                "status": "success",
                "result": result,
                "duration_sec": duration,
            }

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.logger.error(f"Agent {agent_name} execution failed: {e}")

            return {
                "status": "failed",
                "error": str(e),
                "duration_sec": duration,
            }

    def _prepare_agent_input(
        self, agent_name: str, task: Dict[str, Any], previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare input for specific agent from task and previous results.

        Args:
            agent_name: Agent to prepare input for
            task: Task definition
            previous_results: Results from previous stages

        Returns:
            Agent-specific input dictionary
        """
        if agent_name == "ced_parser":
            return {
                "course_id": task["request"]["course_id"],
                "course_name": task["request"].get("course_name", ""),
                "ced_document": task["request"].get("ced_document", {}),
                "parsing_config": task["request"].get("parsing_config", {}),
            }

        elif agent_name == "template_crafter":
            # Use CED data from previous stage if available
            ced_data = previous_results.get("ced_parser", {}).get("result", {})

            return {
                "task_id": task["task_id"],
                "course_id": task["request"]["course_id"],
                "unit_id": task["request"].get("unit_id"),
                "topic_id": task["request"].get("topic_id"),
                "learning_objectives": task["request"].get("learning_objectives", []),
                "difficulty_target": task["request"].get("difficulty_target", [0.4, 0.7]),
                "calculator_policy": task["request"].get("calculator_policy", "No-Calc"),
                "misconceptions": task["request"].get("misconceptions", []),
                "ced_data": ced_data,
            }

        return {}

    def _check_stage_success(self, stage_results: Dict[str, Any]) -> bool:
        """
        Check if stage executed successfully.

        Args:
            stage_results: Results from stage execution

        Returns:
            True if all agents succeeded
        """
        return all(
            result.get("status") == "success" for result in stage_results.values()
        )

    def _estimate_cost(self, stages: List[List[str]], task: Dict[str, Any]) -> float:
        """
        Estimate total cost for workflow.

        Args:
            stages: Execution stages
            task: Task definition

        Returns:
            Estimated cost in USD
        """
        # Simple cost estimation (TODO: Improve)
        cost_per_agent = {
            "ced_parser": 0.10,
            "template_crafter": 0.25,
            "parametric_generator": 0.50,
            "solution_verifier": 1.00,
        }

        total_cost = 0.0
        for stage in stages:
            for agent in stage:
                total_cost += cost_per_agent.get(agent, 0.10)

        # Multiply by item count if applicable
        item_count = task.get("request", {}).get("template_count", 1)
        total_cost *= item_count

        return round(total_cost, 2)

    def _estimate_duration(
        self, stages: List[List[str]], task: Dict[str, Any]
    ) -> float:
        """
        Estimate workflow duration in hours.

        Args:
            stages: Execution stages
            task: Task definition

        Returns:
            Estimated duration in hours
        """
        # Simple duration estimation
        duration_per_agent = {
            "ced_parser": 0.1,  # 6 minutes
            "template_crafter": 0.05,  # 3 minutes
            "parametric_generator": 0.02,  # 1 minute
        }

        # Stages run sequentially, agents within stages run in parallel
        total_hours = 0.0
        for stage in stages:
            # Max duration in stage (parallel execution)
            stage_duration = max(
                duration_per_agent.get(agent, 0.05) for agent in stage
            )
            total_hours += stage_duration

        return round(total_hours, 2)

    def _generate_final_report(
        self,
        workflow_id: str,
        results: Dict[str, Any],
        plan: Dict[str, Any],
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compile final workflow report.

        Args:
            workflow_id: Workflow identifier
            results: Execution results
            plan: Workflow plan
            task: Task definition

        Returns:
            Final report dictionary
        """
        workflow = self.workflows[workflow_id]
        duration = (datetime.now() - workflow["started_at"]).total_seconds() / 3600

        # Count successes
        successful = sum(
            1 for r in results.values() if r.get("status") == "success"
        )

        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "summary": {
                "total_agents": len(results),
                "successful_agents": successful,
                "failed_agents": len(results) - successful,
            },
            "performance": {
                "total_duration_hours": round(duration, 2),
                "planned_duration_hours": plan["estimated_duration_hours"],
                "total_cost_usd": plan["estimated_cost_usd"],  # TODO: Track actual cost
            },
            "outputs": [
                {
                    "agent": agent_name,
                    "status": result.get("status"),
                    "output": result.get("result"),
                }
                for agent_name, result in results.items()
            ],
        }
