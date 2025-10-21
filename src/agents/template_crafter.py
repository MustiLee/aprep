"""
Template Crafter Agent - Create pedagogically sound MCQ templates.

This agent generates high-quality question templates that serve as blueprints
for parametric question generation, aligned with AP CEDs.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml
from anthropic import Anthropic

from ..core.config import settings
from ..core.exceptions import TemplateError, ValidationError
from ..core.logger import setup_logger

logger = setup_logger(__name__)

# Retry configuration (HIGH PRIORITY feature)
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0


class TemplateCrafter:
    """
    Create MCQ templates aligned with AP Course and Exam Descriptions.

    Templates include:
    - Parameterized question stems
    - Solution logic
    - Distractor generation rules
    - Misconception mappings
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize Template Crafter.

        Args:
            model: Claude model to use (defaults to settings)
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.claude_model_sonnet
        self.logger = logger

        # Cost tracking (HIGH PRIORITY feature)
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self.api_call_count = 0

    def create_template(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for template creation.

        Args:
            inputs: Dictionary containing:
                - task_id: str
                - course_id: str
                - unit_id: str
                - topic_id: str
                - learning_objectives: List[str]
                - difficulty_target: List[float]
                - calculator_policy: str
                - misconceptions: List[str]
                - template_count: int (default 1)

        Returns:
            Template dictionary with YAML structure

        Raises:
            TemplateError: If template creation fails
        """
        self.logger.info(f"Creating template for {inputs.get('topic_id')}")

        try:
            # Phase 1: Analyze CED context
            analysis = self._analyze_learning_objective(inputs)

            # Phase 2: Design template structure
            structure = self._design_template_structure(analysis, inputs)

            # Phase 3: Create distractor rules
            distractors = self._create_distractor_rules(
                inputs.get("misconceptions", []), structure
            )

            # Phase 4: Generate template using Claude
            template = self._generate_with_claude(
                inputs, analysis, structure, distractors
            )

            # Phase 5: Validate
            validation = self._validate_template(template)
            if not validation["passed"]:
                raise ValidationError(
                    f"Template validation failed: {validation['checks']}"
                )

            # Phase 6: Add metadata (including versioning - HIGH PRIORITY feature)
            template["created_by"] = "agent.template_crafter"
            template["created_at"] = datetime.now().isoformat()
            template["version"] = "1.0"
            template["task_id"] = inputs.get("task_id")

            # Add quality score to metadata
            template["quality_score"] = validation.get("quality_score", 0.0)

            # Add API usage stats for this template
            template["api_usage"] = {
                "tokens": self.total_tokens_used,
                "cost_usd": round(self.total_cost_usd, 4),
            }

            self.logger.info(
                f"Template created: {template.get('template_id')} "
                f"(quality: {template['quality_score']:.2f})"
            )
            return template

        except Exception as e:
            self.logger.error(f"Template creation failed: {e}")
            raise TemplateError(f"Failed to create template: {e}") from e

    def _analyze_learning_objective(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze learning objectives and extract key concepts.

        Args:
            inputs: Template input dictionary

        Returns:
            Analysis dictionary with concepts, operations, difficulty
        """
        learning_objectives = inputs.get("learning_objectives", [])

        # Simple analysis (TODO: Enhance with CED lookup)
        concepts = []
        operations = []

        for lo in learning_objectives:
            # Extract key concepts from LO text
            if "chain rule" in lo.lower():
                concepts.append("chain_rule")
                operations.append("differentiation")
            if "trig" in lo.lower():
                concepts.append("trigonometry")
            if "derivative" in lo.lower():
                operations.append("differentiation")

        return {
            "concepts": concepts,
            "operations": operations,
            "difficulty_factors": {
                "num_steps": len(operations),
                "abstraction_level": 2,  # TODO: Calculate from Bloom taxonomy
            },
        }

    def _design_template_structure(
        self, analysis: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Design parameterized template structure.

        Args:
            analysis: Concept analysis
            inputs: Template inputs

        Returns:
            Structure dictionary with stem and parameters
        """
        # Design based on operations
        operations = analysis.get("operations", [])

        if "differentiation" in operations:
            stem_type = "procedural"
            stem = "Let f(x) = {{function}}. Find f'(x)."
            params = {
                "function": {
                    "type": "algebraic_expression",
                    "templates": ["{{coef}}x^2", "sin({{inner}})"],
                    "constraints": {"coef": [1, 2, 3], "inner": ["x", "2x"]},
                }
            }
        else:
            # Generic structure
            stem_type = "conceptual"
            stem = "{{question_stem}}"
            params = {}

        return {
            "stem_type": stem_type,
            "stem": stem,
            "params": params,
            "solution_steps": [],  # TODO: Generate solution steps
        }

    def _create_distractor_rules(
        self, misconceptions: List[str], structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Map misconceptions to distractor generation rules.

        Args:
            misconceptions: List of common misconceptions
            structure: Template structure

        Returns:
            List of distractor rule dictionaries
        """
        rules = []

        for misc in misconceptions:
            rule_id = misc.lower().replace(" ", "_").replace("'", "")

            rule = {
                "rule_id": rule_id,
                "description": misc,
                "generation": "{{wrong_value}}",  # Placeholder
                "misconception": misc,
            }
            rules.append(rule)

        # Ensure at least 3 distractors
        while len(rules) < 3:
            rules.append({
                "rule_id": f"algebraic_error_{len(rules)}",
                "description": "Generic algebraic error",
                "generation": "{{error_value}}",
            })

        return rules[:4]  # Max 4 distractors

    def _generate_with_claude(
        self,
        inputs: Dict[str, Any],
        analysis: Dict[str, Any],
        structure: Dict[str, Any],
        distractors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Use Claude to generate template YAML with retry logic and cost tracking.

        HIGH PRIORITY features:
        - Retry logic with exponential backoff
        - Cost tracking (token usage)

        Args:
            inputs: Template inputs
            analysis: Concept analysis
            structure: Template structure
            distractors: Distractor rules

        Returns:
            Template dictionary

        Raises:
            TemplateError: After all retries exhausted
        """
        prompt = f"""You are an expert AP exam content creator. Generate a high-quality MCQ template in YAML format.

**Context:**
- Course: {inputs['course_id']}
- Topic: {inputs['topic_id']}
- Learning Objectives: {', '.join(inputs.get('learning_objectives', []))}
- Difficulty Target: {inputs.get('difficulty_target', [0.4, 0.7])}
- Calculator Policy: {inputs.get('calculator_policy', 'No-Calc')}

**Misconceptions to Address:**
{yaml.dump(inputs.get('misconceptions', []))}

**Template Structure:**
{yaml.dump(structure)}

**Distractor Rules:**
{yaml.dump(distractors)}

**Requirements:**
1. Create a parameterized stem with {{{{placeholders}}}}
2. Define parameter ranges that produce 30-50 valid variants
3. Map each distractor rule to a generation formula
4. Include symbolic solution logic
5. Add appropriate tags and metadata
6. Ensure calculator policy is enforced

Output ONLY valid YAML, no explanations. Start with template_id."""

        # Retry logic with exponential backoff (HIGH PRIORITY feature)
        retry_count = 0
        retry_delay = INITIAL_RETRY_DELAY
        last_exception = None

        while retry_count < MAX_RETRIES:
            try:
                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Cost tracking (HIGH PRIORITY feature)
                self._track_api_usage(response)

                yaml_text = response.content[0].text

                # Extract YAML from response (may have markdown code blocks)
                if "```yaml" in yaml_text:
                    yaml_text = yaml_text.split("```yaml")[1].split("```")[0]
                elif "```" in yaml_text:
                    yaml_text = yaml_text.split("```")[1].split("```")[0]

                template = yaml.safe_load(yaml_text)

                # Ensure required fields
                if "template_id" not in template:
                    template["template_id"] = self._generate_template_id(inputs)

                # Ensure metadata fields
                if "course_id" not in template:
                    template["course_id"] = inputs["course_id"]
                if "topic_id" not in template:
                    template["topic_id"] = inputs["topic_id"]
                if "unit_id" not in template and "unit_id" in inputs:
                    template["unit_id"] = inputs["unit_id"]

                # Ensure distractor_rules
                if "distractor_rules" not in template or not template["distractor_rules"]:
                    template["distractor_rules"] = distractors

                # Validate template before returning
                validation = self._validate_template(template)
                if not validation["passed"]:
                    raise ValidationError(
                        f"Generated template failed validation: {validation['checks']}"
                    )

                # Success! Return template
                self.logger.info(
                    f"Template generated successfully on attempt {retry_count + 1}"
                )
                return template

            except (ValidationError, yaml.YAMLError) as e:
                # Retry on validation or YAML parsing errors
                retry_count += 1
                last_exception = e

                if retry_count < MAX_RETRIES:
                    self.logger.warning(
                        f"Attempt {retry_count}/{MAX_RETRIES} failed: {e}. "
                        f"Retrying in {retry_delay:.1f}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= BACKOFF_MULTIPLIER
                else:
                    self.logger.error(
                        f"All {MAX_RETRIES} attempts failed. Using fallback template."
                    )

            except Exception as e:
                # Non-retryable error (API error, network issue, etc.)
                self.logger.error(f"Claude API call failed: {e}")
                last_exception = e
                break  # Don't retry on API errors

        # All retries exhausted or non-retryable error - use fallback
        self.logger.warning("Falling back to basic template generation")
        return self._create_fallback_template(inputs, structure, distractors)

    def _create_fallback_template(
        self,
        inputs: Dict[str, Any],
        structure: Dict[str, Any],
        distractors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Create basic template without Claude (fallback).

        Args:
            inputs: Template inputs
            structure: Template structure
            distractors: Distractor rules

        Returns:
            Basic template dictionary
        """
        template_id = self._generate_template_id(inputs)

        return {
            "template_id": template_id,
            "course_id": inputs["course_id"],
            "unit_id": inputs.get("unit_id"),
            "topic_id": inputs["topic_id"],
            "stem": structure["stem"],
            "params": structure["params"],
            "distractor_rules": distractors,
            "calculator": inputs.get("calculator_policy", "No-Calc"),
            "difficulty_range": inputs.get("difficulty_target", [0.4, 0.7]),
            "tags": ["generated", inputs["topic_id"]],
        }

    def _generate_template_id(self, inputs: Dict[str, Any]) -> str:
        """Generate unique template ID."""
        course = inputs["course_id"].replace("ap_", "")
        topic = inputs["topic_id"].replace("t", "")
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"{course}_{topic}_v{timestamp}"

    def _track_api_usage(self, response) -> None:
        """
        Track API token usage and costs (HIGH PRIORITY feature).

        Args:
            response: Anthropic API response object
        """
        # Extract token usage from response
        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        total_tokens = input_tokens + output_tokens

        # Cost calculation (Claude Sonnet 4.5 pricing as of 2024)
        # Input: $3.00 per 1M tokens, Output: $15.00 per 1M tokens
        input_cost = (input_tokens / 1_000_000) * 3.00
        output_cost = (output_tokens / 1_000_000) * 15.00
        total_cost = input_cost + output_cost

        # Update tracking metrics
        self.total_tokens_used += total_tokens
        self.total_cost_usd += total_cost
        self.api_call_count += 1

        # Log usage
        self.logger.info(
            f"API call #{self.api_call_count}: {total_tokens} tokens "
            f"(${total_cost:.4f}) | Total: {self.total_tokens_used} tokens "
            f"(${self.total_cost_usd:.4f})"
        )

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get API usage statistics (HIGH PRIORITY feature).

        Returns:
            Dictionary with token usage and cost metrics
        """
        return {
            "total_tokens": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "api_calls": self.api_call_count,
            "avg_tokens_per_call": (
                round(self.total_tokens_used / self.api_call_count, 1)
                if self.api_call_count > 0
                else 0
            ),
            "avg_cost_per_call": (
                round(self.total_cost_usd / self.api_call_count, 4)
                if self.api_call_count > 0
                else 0
            ),
        }

    def _validate_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run automated quality checks on template with quality scoring (HIGH PRIORITY feature).

        Args:
            template: Template dictionary

        Returns:
            Validation results with passed flag, checks, and quality score
        """
        checks = {
            "has_template_id": "template_id" in template,
            "has_stem": "stem" in template,
            "has_params": "params" in template and len(template["params"]) > 0,
            "has_distractors": "distractor_rules" in template
            and len(template["distractor_rules"]) >= 3,
            "has_metadata": "course_id" in template and "topic_id" in template,
        }

        passed = all(checks.values())

        # Quality scoring (HIGH PRIORITY feature)
        quality_score = self._calculate_quality_score(template, checks)

        return {
            "passed": passed,
            "checks": checks,
            "quality_score": quality_score,
            "ready_for_human": passed and quality_score >= 0.7,
        }

    def _calculate_quality_score(
        self, template: Dict[str, Any], checks: Dict[str, bool]
    ) -> float:
        """
        Calculate template quality score (HIGH PRIORITY feature).

        Scoring criteria:
        - Basic structure (30%): Required fields present
        - Parameterization (25%): Number and variety of parameters
        - Distractors (25%): Quality and quantity of distractor rules
        - Metadata completeness (20%): Tags, LOs, difficulty, etc.

        Args:
            template: Template dictionary
            checks: Validation checks results

        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0

        # Basic structure (30%) - all required fields present
        structure_score = sum(checks.values()) / len(checks)
        score += structure_score * 0.30

        # Parameterization (25%)
        params = template.get("params", {})
        param_count = len(params)
        if param_count >= 3:
            param_score = 1.0
        elif param_count >= 2:
            param_score = 0.7
        elif param_count >= 1:
            param_score = 0.4
        else:
            param_score = 0.0
        score += param_score * 0.25

        # Distractors (25%)
        distractors = template.get("distractor_rules", [])
        distractor_count = len(distractors)
        if distractor_count >= 4:
            distractor_score = 1.0
        elif distractor_count == 3:
            distractor_score = 0.8
        elif distractor_count == 2:
            distractor_score = 0.5
        else:
            distractor_score = 0.0
        score += distractor_score * 0.25

        # Metadata completeness (20%)
        metadata_items = [
            "learning_objectives" in template and len(template["learning_objectives"]) > 0,
            "tags" in template and len(template["tags"]) > 0,
            "difficulty_range" in template,
            "calculator" in template,
            "bloom_level" in template,
        ]
        metadata_score = sum(metadata_items) / len(metadata_items)
        score += metadata_score * 0.20

        return round(score, 2)

    def create_batch(
        self, inputs: Dict[str, Any], count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Create multiple templates for a topic.

        Args:
            inputs: Template inputs
            count: Number of templates to create

        Returns:
            List of templates
        """
        templates = []

        for i in range(count):
            try:
                # Vary inputs slightly for each template
                template_inputs = inputs.copy()
                template_inputs["task_id"] = f"{inputs['task_id']}_{i+1}"

                template = self.create_template(template_inputs)
                templates.append(template)

            except Exception as e:
                self.logger.warning(f"Failed to create template {i+1}/{count}: {e}")
                continue

        self.logger.info(f"Created {len(templates)}/{count} templates")
        return templates
