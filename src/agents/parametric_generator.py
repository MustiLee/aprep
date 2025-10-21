"""
Parametric Generator Agent - Generate MCQ variants from templates.

This agent instantiates template parameters to create thousands of unique
question variants with controlled randomness and validation.
"""

import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sympy import diff, simplify, symbols, sympify

from ..core.config import settings
from ..core.exceptions import GenerationError, ValidationError
from ..core.logger import setup_logger

logger = setup_logger(__name__)


class ParametricGenerator:
    """
    Generate MCQ variants from parametric templates.

    Features:
    - Parameter instantiation with seeded randomness
    - Distractor generation based on misconceptions
    - Symbolic computation using SymPy
    - Duplicate detection and validation
    """

    def __init__(self):
        """Initialize Parametric Generator."""
        self.logger = logger
        self.x = symbols("x")

        # Performance metrics (HIGH PRIORITY feature)
        self.generation_history = []
        self.total_variants_generated = 0
        self.total_attempts = 0
        self.total_failures = 0

    def generate_batch(
        self,
        template: Dict[str, Any],
        count: int = 50,
        seed_start: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Generate batch of variants from template with performance tracking.

        HIGH PRIORITY features:
        - Performance metrics logging
        - Generation history tracking

        Args:
            template: Template dictionary with params and rules
            count: Number of variants to generate
            seed_start: Starting seed value

        Returns:
            List of validated variant dictionaries

        Raises:
            GenerationError: If generation fails
        """
        import time
        start_time = time.time()

        self.logger.info(
            f"Generating {count} variants from template {template.get('template_id')}"
        )

        variants = []
        failed = []
        seed = seed_start

        # Generate with retry logic
        max_attempts = count * 10  # Allow up to 10x attempts
        attempts = 0

        while len(variants) < count and attempts < max_attempts:
            attempts += 1

            try:
                variant = self.generate_single_variant(template, seed)

                # Validate
                validation = self._validate_variant(variant, template, variants)

                if validation["valid"]:
                    variants.append(variant)
                    self.logger.debug(f"Generated variant {len(variants)}/{count}")
                else:
                    failed.append({
                        "seed": seed,
                        "issues": validation["issues"],
                    })

            except Exception as e:
                self.logger.warning(f"Generation failed for seed {seed}: {e}")
                failed.append({"seed": seed, "error": str(e)})

            seed += 1

        # Performance metrics (HIGH PRIORITY feature)
        duration_ms = (time.time() - start_time) * 1000
        success_rate = len(variants) / attempts if attempts > 0 else 0
        avg_time_per_variant = duration_ms / len(variants) if variants else 0

        # Update global metrics
        self.total_variants_generated += len(variants)
        self.total_attempts += attempts
        self.total_failures += len(failed)

        # Generation history tracking (HIGH PRIORITY feature)
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "template_id": template.get("template_id"),
            "requested": count,
            "generated": len(variants),
            "failed": len(failed),
            "attempts": attempts,
            "success_rate": round(success_rate, 3),
            "duration_ms": round(duration_ms, 2),
            "avg_ms_per_variant": round(avg_time_per_variant, 2),
        }
        self.generation_history.append(history_entry)

        # Log results with performance metrics
        self.logger.info(
            f"Generated {len(variants)}/{count} variants "
            f"({len(failed)} failed, {attempts} attempts) "
            f"in {duration_ms:.0f}ms ({avg_time_per_variant:.1f}ms/variant)"
        )

        if len(variants) < count * 0.8:
            self.logger.warning(
                f"Low yield: {len(variants)}/{count} ({success_rate*100:.1f}% success rate)"
            )

        return variants

    def generate_single_variant(
        self, template: Dict[str, Any], seed: int
    ) -> Dict[str, Any]:
        """
        Generate one question variant from template.

        Args:
            template: Template dictionary
            seed: Random seed for reproducibility

        Returns:
            Complete variant dictionary

        Raises:
            GenerationError: If generation fails
        """
        rng = random.Random(seed)

        try:
            self.logger.debug(f"generate_single_variant START (seed={seed})")

            # Phase 1: Instantiate parameters
            self.logger.debug("Phase 1: Instantiating parameters...")
            params = self._instantiate_parameters(template, rng)
            self.logger.debug(f"Phase 1 COMPLETE: params = {params}")

            # Phase 2: Generate stem and solution
            self.logger.debug("Phase 2: Generating question text...")
            stem, solution, derived = self._generate_question_text(
                template, params
            )
            self.logger.debug(f"Phase 2 COMPLETE: stem = {stem}, solution = {solution}")

            # Phase 3: Generate distractors
            self.logger.debug("Phase 3: Generating distractors...")
            distractors = self._generate_distractors(
                template, params, solution, derived, rng
            )
            self.logger.debug(f"Phase 3 COMPLETE: distractors = {distractors}")

            # Phase 4: Shuffle answers
            self.logger.debug("Phase 4: Shuffling answer choices...")
            options, correct_index = self._shuffle_answer_choices(
                solution, distractors, rng
            )
            self.logger.debug(f"Phase 4 COMPLETE: options = {options}, correct_index = {correct_index}")

            # Phase 5: Build variant
            self.logger.debug("Phase 5: Building variant...")
            variant_id = f"{template['template_id']}_v{seed}"

            # Critical Blocker #3: Pass through template metadata for Difficulty Calibrator
            variant = {
                "id": variant_id,
                "version": "1.0",
                "template_id": template["template_id"],
                "course_id": template.get("course_id"),
                "unit_id": template.get("unit_id"),
                "topic_id": template.get("topic_id"),
                "stimulus": stem,
                "options": options,
                "answer_index": correct_index,
                "solution": solution,
                "tags": template.get("tags", []),
                "metadata": {
                    "calculator": template.get("calculator", "No-Calc"),
                    "difficulty_est": template.get("difficulty_range", [0.5, 0.5])[0],
                    # Pass through template metadata for accurate difficulty calibration
                    "template_id": template["template_id"],
                    "template_difficulty": template.get("estimated_difficulty"),
                    "bloom_level": template.get("bloom_level"),
                    "cognitive_complexity": template.get("cognitive_complexity"),
                },
                "origin": {
                    "created_by": "agent.parametric_generator",
                    "created_at": datetime.now().isoformat(),
                    "seed": seed,
                    "parameter_instantiation": params,
                    "derived_values": derived,
                },
            }

            self.logger.debug(f"Phase 5 COMPLETE: variant created with id {variant_id}")
            self.logger.debug(f"generate_single_variant COMPLETE (seed={seed})")
            return variant

        except Exception as e:
            self.logger.error(f"generate_single_variant FAILED (seed={seed}): {e}", exc_info=True)
            raise GenerationError(
                f"Failed to generate variant (seed={seed}): {e}"
            ) from e

    def _instantiate_parameters(
        self, template: Dict[str, Any], rng: random.Random
    ) -> Dict[str, Any]:
        """
        Instantiate template parameters with random values.

        Args:
            template: Template with params definition
            rng: Random number generator

        Returns:
            Parameter instantiation dictionary
        """
        params = {}
        param_spec = template.get("params", {})

        for param_name, spec in param_spec.items():
            param_type = spec.get("type")

            # Handle both "enum" and "choice" types
            if param_type in ["enum", "choice"]:
                # Weighted random choice
                values = spec.get("values")
                weights = spec.get("weights")

                # Default values if not specified
                if not values:
                    if param_name == "variable":
                        values = ["x", "t", "u"]
                    else:
                        values = [1, 2, 3]

                if weights:
                    params[param_name] = rng.choices(values, weights=weights)[0]
                else:
                    params[param_name] = rng.choice(values)

            elif param_type == "algebraic_expression":
                # Recursively instantiate expression template
                expr_templates = spec["templates"]
                expr_template = rng.choice(expr_templates)

                # Substitute nested parameters
                constraints = spec.get("constraints", {})
                for key, value_list in constraints.items():
                    value = rng.choice(value_list)
                    params[key] = value
                    expr_template = expr_template.replace(f"{{{{{key}}}}}", str(value))

                params[param_name] = expr_template

            # Handle both "integer_range" and "integer" types
            elif param_type in ["integer_range", "integer"]:
                # Random integer in range
                range_spec = spec.get("range")
                if range_spec and len(range_spec) == 2:
                    low, high = int(range_spec[0]), int(range_spec[1])
                    params[param_name] = rng.randint(low, high)
                else:
                    params[param_name] = rng.randint(1, 10)

            # Handle both "float_range" and "float" types
            elif param_type in ["float_range", "float"]:
                # Random float in range
                range_spec = spec.get("range")
                if range_spec and len(range_spec) == 2:
                    low, high = float(range_spec[0]), float(range_spec[1])
                    params[param_name] = rng.uniform(low, high)
                else:
                    params[param_name] = rng.uniform(1.0, 10.0)

        return params

    def _generate_question_text(
        self, template: Dict[str, Any], params: Dict[str, Any]
    ) -> tuple[str, str, Dict[str, Any]]:
        """
        Generate question stem and solution from parameters.

        Args:
            template: Template dictionary
            params: Instantiated parameters

        Returns:
            Tuple of (stem, solution, derived_values)
        """
        self.logger.debug(f"_generate_question_text START with params: {params}")

        stem = template.get("stem", "")
        solution_template = template.get("solution_template", "")

        # If solution_template is null or empty, use the last solution_step
        if not solution_template:
            solution_steps = template.get("solution_steps", [])
            if solution_steps:
                solution_template = solution_steps[-1]  # Use last step as the solution

        self.logger.debug(f"stem before substitution: {stem}")
        self.logger.debug(f"solution_template before substitution: {solution_template}")

        # Substitute direct parameters
        for key, value in params.items():
            placeholder = f"{{{{{key}}}}}"
            stem = stem.replace(placeholder, str(value))
            if solution_template:
                solution_template = solution_template.replace(placeholder, str(value))

        self.logger.debug(f"stem after param substitution: {stem}")
        self.logger.debug(f"solution_template after param substitution: {solution_template}")

        # Compute derived values (e.g., derivatives)
        self.logger.debug("Computing derived values...")
        derived = self._compute_derived_values(params, template)
        self.logger.debug(f"derived values: {derived}")

        # Substitute derived values
        for key, value in derived.items():
            placeholder = f"{{{{{key}}}}}"
            stem = stem.replace(placeholder, str(value))
            if solution_template:
                solution_template = solution_template.replace(placeholder, str(value))

        self.logger.debug(f"stem after derived substitution: {stem}")
        self.logger.debug(f"solution_template after derived substitution: {solution_template}")

        # Evaluate Python expressions in the solution template (e.g., {{coefficient * exponent}})
        if solution_template:
            self.logger.debug("Starting expression evaluation...")
            # Find all Python expressions like {{coefficient * exponent}}
            expr_pattern = r'\{\{([^}]+)\}\}'
            matches = re.findall(expr_pattern, solution_template)
            self.logger.debug(f"Found {len(matches)} expressions to evaluate: {matches}")

            # Limit to first 10 matches to prevent infinite loops
            for idx, match in enumerate(matches[:10]):
                self.logger.debug(f"Evaluating expression {idx+1}/{min(len(matches), 10)}: {match}")
                try:
                    # Skip if match contains nested braces (avoid infinite loops)
                    if '{{' in match or '}}' in match:
                        self.logger.debug(f"Skipping nested braces in: {match}")
                        continue

                    # Create a safe evaluation context with params
                    result = eval(match, {"__builtins__": {}}, params)
                    self.logger.debug(f"Expression {match} evaluated to: {result}")
                    solution_template = solution_template.replace(f"{{{{{match}}}}}", str(result), 1)
                    self.logger.debug(f"solution_template after replacement: {solution_template}")
                except Exception as e:
                    self.logger.debug(f"Could not evaluate expression {match}: {e}")

        self.logger.debug("Simplifying expression...")
        # Simplify solution
        solution = self._simplify_expression(solution_template) if solution_template else ""
        self.logger.debug(f"Final solution: {solution}")

        # Ensure stem and solution are not None
        if not stem:
            stem = f"Question with parameters: {params}"
        if not solution:
            solution = "Answer not available"

        self.logger.debug(f"_generate_question_text COMPLETE - stem: {stem}, solution: {solution}")
        return stem, solution, derived

    def _compute_derived_values(
        self, params: Dict[str, Any], template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute derived values (derivatives, integrals, etc.).

        Args:
            params: Parameter values
            template: Template definition

        Returns:
            Dictionary of derived values
        """
        derived = {}

        # Compute inner function derivative
        if "inner_func" in params:
            try:
                inner_expr = sympify(params["inner_func"])
                inner_deriv = diff(inner_expr, self.x)
                derived["inner_func_derivative"] = str(simplify(inner_deriv))
            except Exception as e:
                self.logger.warning(f"Failed to compute derivative: {e}")
                derived["inner_func_derivative"] = "ERR"

        # Trig function derivatives
        if "trig_func" in params:
            trig_deriv_map = {
                "sin": "cos",
                "cos": "-sin",
                "tan": "sec^2",
            }
            derived["trig_func_derivative"] = trig_deriv_map.get(
                params["trig_func"], ""
            )

        # Wrong trig derivative (for distractors)
        if "trig_func" in params:
            wrong_trig_map = {
                "sin": "sin",  # Should be cos
                "cos": "cos",  # Should be -sin
                "tan": "tan",  # Should be sec^2
            }
            derived["wrong_trig_deriv"] = wrong_trig_map.get(params["trig_func"], "")

        return derived

    def _generate_distractors(
        self,
        template: Dict[str, Any],
        params: Dict[str, Any],
        correct_answer: str,
        derived: Dict[str, Any],
        rng: random.Random,
    ) -> List[str]:
        """
        Generate distractor options based on misconception rules.

        Args:
            template: Template with distractor_rules
            params: Parameter values
            correct_answer: Correct answer string
            derived: Derived values
            rng: Random generator

        Returns:
            List of 3 distractors
        """
        self.logger.debug(f"_generate_distractors START with correct_answer: {correct_answer}")

        distractors = []
        all_values = {**params, **derived}
        self.logger.debug(f"all_values: {all_values}")

        distractor_rules = template.get("distractor_rules", [])
        self.logger.debug(f"Found {len(distractor_rules)} distractor rules")

        for idx, rule in enumerate(distractor_rules):
            self.logger.debug(f"Processing distractor rule {idx+1}/{len(distractor_rules)}: {rule.get('rule_id')}")
            distractor_formula = rule.get("generation", "")
            self.logger.debug(f"Original formula: {distractor_formula}")

            # Substitute parameters
            for key, value in all_values.items():
                placeholder = f"{{{{{key}}}}}"
                distractor_formula = distractor_formula.replace(
                    placeholder, str(value)
                )

            self.logger.debug(f"Formula after param substitution: {distractor_formula}")

            # Handle special placeholders
            if "{{wrong_coef}}" in distractor_formula:
                correct_coef = self._extract_coefficient(correct_answer)
                wrong_coef = self._generate_wrong_coefficient(correct_coef, rng)
                distractor_formula = distractor_formula.replace(
                    "{{wrong_coef}}", str(wrong_coef)
                )
                self.logger.debug(f"Formula after wrong_coef substitution: {distractor_formula}")

            # Skip if there are still unresolved placeholders
            if "{{" in distractor_formula:
                self.logger.debug(f"Skipping distractor with unresolved placeholders: {distractor_formula}")
                continue

            # Simplify
            self.logger.debug(f"Simplifying: {distractor_formula}")
            distractor = self._simplify_expression(distractor_formula)
            self.logger.debug(f"Simplified to: {distractor}")

            # Ensure distinct from correct and other distractors
            if (
                distractor
                and distractor != correct_answer
                and distractor not in distractors
            ):
                distractors.append(distractor)
                self.logger.debug(f"Added distractor: {distractor}")
            else:
                self.logger.debug(f"Skipped distractor (duplicate or matches correct): {distractor}")

        self.logger.debug(f"Generated {len(distractors)} distractors from rules, need 3 total")

        # Fill remaining slots with algebraic errors if needed
        attempts = 0
        max_attempts = 100  # Prevent infinite loops
        while len(distractors) < 3 and attempts < max_attempts:
            attempts += 1
            self.logger.debug(f"Generating algebraic error {len(distractors)+1}/3 (attempt {attempts}/{max_attempts})")
            algebraic_error = self._generate_algebraic_error(
                correct_answer, len(distractors), rng
            )
            self.logger.debug(f"Generated algebraic error: {algebraic_error}")
            if algebraic_error not in distractors and algebraic_error != correct_answer:
                distractors.append(algebraic_error)
                self.logger.debug(f"Added algebraic error: {algebraic_error}")
            else:
                self.logger.debug(f"Skipped algebraic error (duplicate): {algebraic_error}")

        if len(distractors) < 3:
            self.logger.warning(f"Could not generate 3 unique distractors after {attempts} attempts, only got {len(distractors)}")
            # Add generic fallback distractors
            for i in range(3 - len(distractors)):
                fallback = f"Option {chr(65 + len(distractors) + i)}"
                distractors.append(fallback)
                self.logger.debug(f"Added fallback distractor: {fallback}")

        self.logger.debug(f"_generate_distractors COMPLETE with {len(distractors)} distractors: {distractors}")
        return distractors[:3]  # Exactly 3 distractors

    def _extract_coefficient(self, expression: str) -> int:
        """Extract leading coefficient from expression."""
        # Simple pattern matching
        match = re.match(r"^(-?\d+)", expression)
        if match:
            return int(match.group(1))
        return 1

    def _generate_wrong_coefficient(
        self, correct: int, rng: random.Random
    ) -> int:
        """Generate plausible wrong coefficient."""
        options = [
            correct // 2,
            correct * 2,
            correct + 1,
            correct - 1,
            abs(correct),
        ]
        options = [opt for opt in options if opt != correct and opt > 0]
        return rng.choice(options) if options else 1

    def _generate_algebraic_error(
        self, correct_answer: str, index: int, rng: random.Random
    ) -> str:
        """Generate generic algebraic error."""
        # Handle None or empty answers
        if not correct_answer:
            return f"Option {index + 1}"

        # Simple error patterns
        errors = [
            f"2{correct_answer}",  # Double the answer
            correct_answer.replace("x", "2x") if "x" in correct_answer else f"{correct_answer}x",  # Change variable
            correct_answer.replace("+", "-") if "+" in correct_answer else correct_answer.replace("-", "+"),  # Sign error
        ]

        if index < len(errors):
            return errors[index]

        # Random coefficient change
        try:
            coef = self._extract_coefficient(correct_answer)
            new_coef = rng.choice([c for c in [1, 2, 3, 4] if c != coef])
            return correct_answer.replace(str(coef), str(new_coef), 1)
        except Exception:
            return f"{index}x"  # Fallback

    def _shuffle_answer_choices(
        self, correct: str, distractors: List[str], rng: random.Random
    ) -> tuple[List[str], int]:
        """
        Randomize answer positions.

        Args:
            correct: Correct answer
            distractors: List of distractors
            rng: Random generator

        Returns:
            Tuple of (shuffled_options, correct_index)
        """
        options = [correct] + distractors
        rng.shuffle(options)
        correct_index = options.index(correct)
        return options, correct_index

    def _simplify_expression(self, expr: str) -> str:
        """
        Simplify mathematical expression (basic string cleanup).

        Args:
            expr: Expression string

        Returns:
            Cleaned expression string
        """
        # Don't try to simplify if expression is None or too long
        if not expr or len(expr) > 200:
            return expr

        # Just return as-is for now - SymPy was causing infinite loops
        # TODO: Implement safe simplification later
        return expr.strip()

    def _validate_variant(
        self,
        variant: Dict[str, Any],
        template: Dict[str, Any],
        existing: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validate generated variant.

        Args:
            variant: Generated variant
            template: Source template
            existing: Previously generated variants

        Returns:
            Validation result with valid flag and issues
        """
        issues = []

        # Check options are distinct
        if len(set(variant["options"])) < len(variant["options"]):
            issues.append("duplicate_options")

        # Check answer index is valid
        if not (0 <= variant["answer_index"] < len(variant["options"])):
            issues.append("invalid_answer_index")

        # Check for duplicates
        if existing:
            similarity = max(
                self._calculate_similarity(variant, ex) for ex in existing
            )
            if similarity > 0.90:
                issues.append("duplicate_detected")

        # Check stem not empty
        if not variant["stimulus"].strip():
            issues.append("empty_stem")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }

    def _calculate_similarity(
        self, v1: Dict[str, Any], v2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity between variants.

        Args:
            v1: First variant
            v2: Second variant

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Simple string similarity
        stem1 = v1["stimulus"]
        stem2 = v2["stimulus"]

        if stem1 == stem2:
            return 1.0

        # Levenshtein-like distance
        if not stem1 or not stem2:
            return 0.0

        matches = sum(c1 == c2 for c1, c2 in zip(stem1, stem2))
        max_len = max(len(stem1), len(stem2))

        return matches / max_len if max_len > 0 else 0.0

    def estimate_variant_difficulty(self, variant: Dict[str, Any]) -> float:
        """
        Estimate difficulty for a single variant (HIGH PRIORITY feature).

        Uses heuristics based on:
        - Complexity of mathematical expressions
        - Number of steps required
        - Presence of nested operations

        Args:
            variant: Variant dictionary

        Returns:
            Estimated difficulty (0.0 = easy, 1.0 = hard)
        """
        # Start with template difficulty if available
        base_difficulty = variant.get("metadata", {}).get("difficulty_est", 0.5)

        # Complexity factors
        complexity_score = 0.0

        # Check stimulus complexity
        stimulus = variant.get("stimulus", "")

        # Factor 1: Length (longer questions tend to be harder)
        if len(stimulus) > 150:
            complexity_score += 0.1
        elif len(stimulus) > 100:
            complexity_score += 0.05

        # Factor 2: Mathematical operations
        operations = ["derivative", "integral", "limit", "chain rule", "implicit"]
        for op in operations:
            if op in stimulus.lower():
                complexity_score += 0.05

        # Factor 3: Solution complexity
        solution = variant.get("solution", "")
        if len(str(solution)) > 20:
            complexity_score += 0.05

        # Factor 4: Number of parameters
        params = variant.get("origin", {}).get("parameter_instantiation", {})
        if len(params) >= 3:
            complexity_score += 0.1
        elif len(params) >= 2:
            complexity_score += 0.05

        # Combine base difficulty with complexity adjustments
        estimated_difficulty = base_difficulty + complexity_score

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, estimated_difficulty))

    def get_generation_stats(self) -> Dict[str, Any]:
        """
        Get generation statistics (HIGH PRIORITY feature).

        Returns:
            Dictionary with performance metrics
        """
        overall_success_rate = (
            self.total_variants_generated / self.total_attempts
            if self.total_attempts > 0
            else 0.0
        )

        return {
            "total_variants_generated": self.total_variants_generated,
            "total_attempts": self.total_attempts,
            "total_failures": self.total_failures,
            "overall_success_rate": round(overall_success_rate, 3),
            "batches_processed": len(self.generation_history),
            "recent_history": self.generation_history[-5:],  # Last 5 batches
        }

    def get_generation_history(
        self, template_id: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get generation history (HIGH PRIORITY feature).

        Args:
            template_id: Optional filter by template ID
            limit: Maximum number of entries to return

        Returns:
            List of history entries
        """
        history = self.generation_history

        # Filter by template_id if provided
        if template_id:
            history = [h for h in history if h["template_id"] == template_id]

        # Return most recent entries
        return history[-limit:] if limit else history
