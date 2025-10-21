"""
Example usage of Aprep AI agents.

This script demonstrates how to use the implemented agents
for content generation workflows.
"""

import asyncio
from src.agents import CEDParser, TemplateCrafter, MasterOrchestrator


async def example_full_workflow():
    """Example: Full workflow from CED to templates."""
    print("=" * 60)
    print("EXAMPLE: Full Workflow - CED Parser + Template Crafter")
    print("=" * 60)

    # Initialize orchestrator
    orchestrator = MasterOrchestrator()

    # Define task
    task = {
        "task_id": "demo_calc_bc_templates",
        "task_type": "batch_generation",
        "request": {
            "course_id": "ap_calculus_bc",
            "course_name": "AP Calculus BC",
            "ced_document": {
                "local_path": "data/ced/sample_calculus_bc.pdf",
                "version": "2024-2025",
            },
            "parsing_config": {
                "extract_learning_objectives": True,
                "extract_skills": True,
            },
            "unit_id": "u2_differentiation",
            "topic_id": "t3_chain_rule",
            "learning_objectives": [
                "Apply chain rule to composite functions",
                "Differentiate trigonometric compositions",
            ],
            "difficulty_target": [0.4, 0.7],
            "calculator_policy": "No-Calc",
            "misconceptions": [
                "Omitting inner derivative",
                "Confusing chain rule with product rule",
            ],
            "template_count": 5,
        },
        "constraints": {
            "max_cost_usd": 10.0,
            "max_duration_hours": 1.0,
        },
    }

    try:
        # Execute workflow
        print("\n🚀 Starting workflow...")
        result = await orchestrator.execute_workflow(task)

        print("\n✅ Workflow completed!")
        print(f"Workflow ID: {result['workflow_id']}")
        print(f"Duration: {result['performance']['total_duration_hours']} hours")
        print(f"Cost: ${result['performance']['total_cost_usd']}")
        print(f"\nAgents executed: {result['summary']['total_agents']}")
        print(f"Successful: {result['summary']['successful_agents']}")
        print(f"Failed: {result['summary']['failed_agents']}")

        return result

    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        return None


def example_ced_parser():
    """Example: CED Parser standalone."""
    print("\n" + "=" * 60)
    print("EXAMPLE: CED Parser - Parse Course Description")
    print("=" * 60)

    parser = CEDParser()

    ced_info = {
        "course_id": "ap_calculus_bc",
        "course_name": "AP Calculus BC",
        "ced_document": {
            "local_path": "data/ced/sample_calculus_bc.pdf",
            "version": "2024-2025",
        },
        "parsing_config": {
            "extract_learning_objectives": True,
            "extract_skills": True,
        },
    }

    try:
        print("\n📖 Parsing CED document...")
        # Note: This will fail without an actual PDF file
        parsed_data = parser.parse_ced(ced_info)

        print("\n✅ CED parsed successfully!")
        print(f"Course: {parsed_data['course_name']}")
        print(f"Units found: {parsed_data['metadata']['total_units']}")
        print(f"Total pages: {parsed_data['metadata']['total_pages']}")

        return parsed_data

    except Exception as e:
        print(f"\n⚠️  CED parsing skipped (requires actual PDF file)")
        print(f"Error: {e}")
        return None


def example_template_crafter():
    """Example: Template Crafter standalone."""
    print("\n" + "=" * 60)
    print("EXAMPLE: Template Crafter - Create Question Template")
    print("=" * 60)

    crafter = TemplateCrafter()

    template_input = {
        "task_id": "demo_template_001",
        "course_id": "ap_calculus_bc",
        "unit_id": "u2_differentiation",
        "topic_id": "t3_chain_rule",
        "learning_objectives": [
            "Apply chain rule to composite functions",
            "Differentiate trigonometric compositions",
        ],
        "difficulty_target": [0.4, 0.7],
        "calculator_policy": "No-Calc",
        "misconceptions": [
            "Omitting inner derivative",
            "Confusing chain rule with product rule",
            "Incorrect trig derivative signs",
        ],
    }

    try:
        print("\n🎨 Creating template...")
        template = crafter.create_template(template_input)

        print("\n✅ Template created!")
        print(f"Template ID: {template.get('template_id')}")
        print(f"Course: {template.get('course_id')}")
        print(f"Topic: {template.get('topic_id')}")
        print(f"Parameters: {len(template.get('params', {}))} defined")
        print(f"Distractors: {len(template.get('distractor_rules', []))} rules")

        return template

    except Exception as e:
        print(f"\n❌ Template creation failed: {e}")
        return None


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("APREP AI AGENTS - DEMO")
    print("=" * 60)

    # Example 1: CED Parser
    example_ced_parser()

    # Example 2: Template Crafter
    example_template_crafter()

    # Example 3: Full Workflow (async)
    print("\n\nRunning full workflow example...")
    asyncio.run(example_full_workflow())

    print("\n" + "=" * 60)
    print("DEMO COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
