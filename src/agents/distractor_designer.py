"""
Distractor Designer Agent

This agent generates pedagogically sound wrong answer choices (distractors) for
multiple-choice questions based on common student misconceptions. It uses
transformation rules from the Misconception Database Manager to create plausible
but incorrect answers that help identify specific student errors.

Responsibilities:
- Generate distractors from misconception-driven transformation rules
- Evaluate distractor quality and plausibility
- Ensure distractors are pedagogically valuable
- Avoid trivial or obviously wrong distractors
- Integrate with Template Crafter and Parametric Generator
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from itertools import combinations
import anthropic

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError
from src.agents.misconception_database_manager import (
    MisconceptionDatabaseManager,
    MisconceptionRecord
)

# Try to import SymPy for enhanced mathematical transformations
try:
    from sympy import sympify, simplify, diff, integrate
    from sympy.parsing.sympy_parser import parse_expr
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    logger.warning("SymPy not available - mathematical transformations will be limited")

logger = setup_logger(__name__)


class DistractorCandidate(BaseModel):
    """A candidate distractor with metadata (aligned with spec)"""

    value: str = Field(..., description="The distractor value/expression")
    misconception_id: str = Field(..., description="Source misconception ID")
    misconception: str = Field(..., description="Misconception type")
    transformation_rule: str = Field(..., description="Transformation rule used")

    # Spec-aligned scoring
    target_ability: str = Field(default="medium", description="Target ability: low, medium, high, low-medium, medium-high")
    plausibility_score: float = Field(..., ge=0.0, le=10.0, description="Plausibility 0-10")
    quality_score: float = Field(..., ge=0.0, le=10.0, description="Overall quality 0-10")
    estimated_selection_rate: float = Field(default=0.12, ge=0.0, le=1.0, description="Estimated % who select")

    explanation: str = Field(..., description="Why this distractor is pedagogically valuable")
    is_trivial: bool = Field(default=False, description="Whether distractor is trivial")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class DistractorSet(BaseModel):
    """A complete set of distractors for a question"""

    correct_answer: str = Field(..., description="The correct answer")
    distractors: List[DistractorCandidate] = Field(..., description="Generated distractors")

    question_id: Optional[str] = Field(None, description="Question/variant ID")
    topic_id: Optional[str] = Field(None, description="Topic ID")
    course_id: Optional[str] = Field(None, description="Course ID")

    avg_quality_score: float = Field(..., description="Average quality score")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    metadata: Dict[str, Any] = Field(default_factory=dict)


class DistractorDesigner:
    """
    Generates pedagogically sound distractors using misconception-driven
    transformation rules.
    """

    def __init__(
        self,
        misconception_manager: Optional[MisconceptionDatabaseManager] = None,
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize the Distractor Designer.

        Args:
            misconception_manager: Misconception database manager instance
            anthropic_api_key: Optional API key for Claude-based quality evaluation
        """
        self.misconception_manager = misconception_manager or MisconceptionDatabaseManager()

        # Initialize Claude client for quality evaluation if API key provided
        self.client = None
        if anthropic_api_key:
            self.client = anthropic.Anthropic(api_key=anthropic_api_key)

        # Performance tracking
        self.total_distractors_generated = 0
        self.total_distractors_rejected = 0
        self.generation_history = []

        logger.info("Initialized DistractorDesigner")

    def generate_distractors(
        self,
        correct_answer: str,
        question_context: Dict[str, Any],
        count: int = 3,
        min_quality: float = 8.0
    ) -> DistractorSet:
        """
        Generate a set of distractors for a question.

        Args:
            correct_answer: The correct answer to the question
            question_context: Context dict with topic_id, course_id, parameters, etc.
            count: Number of distractors to generate (default 3)
            min_quality: Minimum quality score threshold (default 8.0)

        Returns:
            DistractorSet with generated distractors

        Raises:
            AprepError: If distractor generation fails
        """
        try:
            logger.info(f"Generating {count} distractors for question")

            # Extract context
            topic_id = question_context.get("topic_id")
            course_id = question_context.get("course_id")
            difficulty_level = question_context.get("difficulty_level", 2)

            # Find relevant misconceptions
            misconceptions = self._find_relevant_misconceptions(
                course_id=course_id,
                topic_id=topic_id,
                difficulty_level=difficulty_level
            )

            if not misconceptions:
                logger.warning("No misconceptions found, using fallback generation")
                return self._generate_fallback_distractors(
                    correct_answer, question_context, count
                )

            # Generate candidate distractors
            candidates = []
            for misconception in misconceptions:
                if misconception.distractor_generation:
                    distractor_candidates = self._apply_transformation_rule(
                        correct_answer=correct_answer,
                        misconception=misconception,
                        question_context=question_context
                    )
                    candidates.extend(distractor_candidates)

            # Evaluate quality of candidates
            evaluated_candidates = []
            for candidate in candidates:
                quality_score = self._evaluate_distractor_quality(
                    candidate, correct_answer, question_context
                )
                candidate.quality_score = quality_score

                # Assign ability target based on misconception difficulty
                candidate.target_ability = self._assign_ability_target(
                    candidate, difficulty_level
                )

                # Estimate selection rate based on plausibility and ability
                candidate.estimated_selection_rate = self._estimate_selection_rate(
                    candidate
                )

                # Check if trivial
                candidate.is_trivial = self._is_trivial_distractor(
                    candidate.value, correct_answer
                )

                # Check if dead distractor (estimated selection rate < 5%)
                if candidate.estimated_selection_rate < 0.05:
                    logger.warning(
                        f"Dead distractor detected: {candidate.value} "
                        f"(estimated selection rate: {candidate.estimated_selection_rate:.2%})"
                    )
                    candidate.is_trivial = True  # Mark as trivial to reject

                if not candidate.is_trivial and quality_score >= min_quality:
                    evaluated_candidates.append(candidate)
                else:
                    self.total_distractors_rejected += 1

            # Use set optimization to select best combination
            if len(evaluated_candidates) > count:
                selected_distractors = self._optimize_distractor_set(
                    evaluated_candidates, correct_answer, count
                )
            else:
                # Not enough candidates for optimization, use what we have
                evaluated_candidates.sort(key=lambda c: c.quality_score, reverse=True)
                selected_distractors = evaluated_candidates[:count]

            # If not enough high-quality distractors, use fallback
            if len(selected_distractors) < count:
                logger.warning(
                    f"Only found {len(selected_distractors)} high-quality distractors, "
                    f"using fallback for remaining {count - len(selected_distractors)}"
                )
                fallback_set = self._generate_fallback_distractors(
                    correct_answer, question_context, count - len(selected_distractors)
                )

                # Add fallback distractors, avoiding duplicates
                existing_values = {d.value for d in selected_distractors}
                for fallback_distractor in fallback_set.distractors:
                    if fallback_distractor.value not in existing_values:
                        selected_distractors.append(fallback_distractor)
                        existing_values.add(fallback_distractor.value)
                    if len(selected_distractors) >= count:
                        break

            # Track metrics
            self.total_distractors_generated += len(selected_distractors)

            # Create distractor set
            avg_quality = (
                sum(d.quality_score for d in selected_distractors) / len(selected_distractors)
                if selected_distractors else 0.0
            )

            distractor_set = DistractorSet(
                correct_answer=correct_answer,
                distractors=selected_distractors,
                question_id=question_context.get("question_id"),
                topic_id=topic_id,
                course_id=course_id,
                avg_quality_score=round(avg_quality, 2),
                metadata={
                    "total_candidates": len(candidates),
                    "rejected_count": len(candidates) - len(selected_distractors),
                    "difficulty_level": difficulty_level
                }
            )

            # Record in history
            self._record_generation(distractor_set)

            logger.info(
                f"Generated {len(selected_distractors)} distractors "
                f"(avg quality: {avg_quality:.2f})"
            )

            return distractor_set

        except Exception as e:
            logger.error(f"Distractor generation failed: {e}")
            raise AprepError(f"Failed to generate distractors: {e}")

    def _find_relevant_misconceptions(
        self,
        course_id: Optional[str],
        topic_id: Optional[str],
        difficulty_level: int
    ) -> List[MisconceptionRecord]:
        """Find misconceptions relevant to the question context."""
        try:
            # Search for misconceptions matching context
            misconceptions = self.misconception_manager.search_misconceptions(
                course_id=course_id,
                topic_id=topic_id,
                limit=10
            )

            # Filter to only those with distractor generation rules
            misconceptions = [
                m for m in misconceptions
                if m.distractor_generation is not None
            ]

            logger.debug(f"Found {len(misconceptions)} relevant misconceptions")
            return misconceptions

        except Exception as e:
            logger.error(f"Failed to find misconceptions: {e}")
            return []

    def _apply_transformation_rule(
        self,
        correct_answer: str,
        misconception: MisconceptionRecord,
        question_context: Dict[str, Any]
    ) -> List[DistractorCandidate]:
        """
        Apply transformation rule from misconception to generate distractor.

        Args:
            correct_answer: The correct answer
            misconception: MisconceptionRecord with transformation rule
            question_context: Question context with parameters

        Returns:
            List of DistractorCandidate objects
        """
        try:
            rule = misconception.distractor_generation
            if not rule:
                return []

            candidates = []

            # Apply rule based on transformation type
            if rule.transformation_rule == "OMIT_COEFFICIENT":
                distractor_value = self._apply_omit_coefficient(
                    correct_answer, question_context
                )
            elif rule.transformation_rule == "REMOVE_INNER_DERIVATIVE":
                distractor_value = self._apply_remove_inner_derivative(
                    correct_answer, question_context
                )
            elif rule.transformation_rule == "OMIT_CONSTANT":
                distractor_value = self._apply_omit_constant(
                    correct_answer, question_context
                )
            elif rule.transformation_rule == "WRONG_SIGN":
                distractor_value = self._apply_wrong_sign(
                    correct_answer, question_context
                )
            elif rule.transformation_rule == "OFF_BY_ONE":
                distractor_value = self._apply_off_by_one(
                    correct_answer, question_context
                )
            else:
                # Generic template-based transformation
                distractor_value = self._apply_generic_template(
                    correct_answer, rule.template, question_context
                )

            if distractor_value and distractor_value != correct_answer:
                candidate = DistractorCandidate(
                    value=distractor_value,
                    misconception_id=misconception.misconception_id,
                    misconception=misconception.classification.category,
                    transformation_rule=rule.transformation_rule,
                    plausibility_score=rule.plausibility_score,
                    quality_score=0.0,  # Will be evaluated later
                    explanation=misconception.description.detailed,
                    metadata={
                        "misconception_short": misconception.description.short,
                        "category": misconception.classification.category
                    }
                )
                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.warning(f"Failed to apply transformation rule: {e}")
            return []

    def _apply_omit_coefficient(
        self, correct_answer: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """Apply OMIT_COEFFICIENT transformation."""
        # Pattern: n*x^m -> x^m (remove leading coefficient)
        pattern = r'^(\d+)\s*\*?\s*(.+)$'
        match = re.match(pattern, correct_answer)
        if match:
            return match.group(2).strip()

        # Pattern: nx^m -> x^m
        pattern = r'^(\d+)([a-zA-Z].*)$'
        match = re.match(pattern, correct_answer)
        if match:
            return match.group(2)

        return None

    def _apply_remove_inner_derivative(
        self, correct_answer: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """Apply REMOVE_INNER_DERIVATIVE transformation."""
        # Pattern: n*f(x) -> f(x) (remove coefficient from chain rule)
        pattern = r'^(\d+)\s*\*?\s*(.+)$'
        match = re.match(pattern, correct_answer)
        if match:
            return match.group(2).strip()

        return None

    def _apply_omit_constant(
        self, correct_answer: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """Apply OMIT_CONSTANT transformation."""
        # Pattern: expression + C -> expression
        if "+ C" in correct_answer:
            return correct_answer.replace(" + C", "").replace("+C", "")

        return None

    def _apply_wrong_sign(
        self, correct_answer: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """Apply WRONG_SIGN transformation."""
        # Flip sign of leading term
        if correct_answer.startswith("-"):
            return correct_answer[1:].strip()
        elif correct_answer[0].isdigit():
            return "-" + correct_answer

        return None

    def _apply_off_by_one(
        self, correct_answer: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """Apply OFF_BY_ONE transformation."""
        # Find numbers and modify by ±1
        pattern = r'\d+'
        numbers = re.findall(pattern, correct_answer)

        if numbers:
            # Replace first number with +1 or -1
            first_num = numbers[0]
            new_num = str(int(first_num) + 1)
            return correct_answer.replace(first_num, new_num, 1)

        return None

    def _apply_generic_template(
        self, correct_answer: str, template: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """Apply generic template-based transformation."""
        try:
            # Try to substitute context parameters into template
            result = template
            for key, value in context.get("parameters", {}).items():
                placeholder = "{{" + key + "}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))

            # If template still has placeholders, return None
            if "{{" in result:
                return None

            return result

        except Exception:
            return None

    def _evaluate_distractor_quality(
        self,
        candidate: DistractorCandidate,
        correct_answer: str,
        question_context: Dict[str, Any]
    ) -> float:
        """
        Evaluate quality of a distractor candidate.

        Returns:
            Quality score 0.0-10.0
        """
        try:
            # Start with plausibility score from misconception
            quality = candidate.plausibility_score

            # Factor 1: Similarity to correct answer (want moderate similarity)
            similarity = self._calculate_similarity(candidate.value, correct_answer)
            if 0.3 <= similarity <= 0.7:
                quality += 1.0  # Good similarity range
            elif similarity < 0.1 or similarity > 0.9:
                quality -= 2.0  # Too different or too similar

            # Factor 2: Complexity matching (should have similar complexity)
            correct_complexity = self._estimate_complexity(correct_answer)
            distractor_complexity = self._estimate_complexity(candidate.value)
            complexity_diff = abs(correct_complexity - distractor_complexity)

            if complexity_diff <= 1:
                quality += 0.5
            elif complexity_diff > 3:
                quality -= 1.0

            # Factor 3: If we have Claude API, use it for deeper evaluation
            if self.client:
                claude_quality = self._evaluate_with_claude(
                    candidate, correct_answer, question_context
                )
                quality = 0.7 * quality + 0.3 * claude_quality

            # Ensure within bounds
            return max(0.0, min(10.0, quality))

        except Exception as e:
            logger.warning(f"Quality evaluation failed: {e}")
            return candidate.plausibility_score

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0.0-1.0)."""
        # Simple character-based similarity
        str1 = str1.lower().replace(" ", "")
        str2 = str2.lower().replace(" ", "")

        if not str1 or not str2:
            return 0.0

        # Use set intersection / union
        set1 = set(str1)
        set2 = set(str2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def _estimate_complexity(self, expression: str) -> int:
        """
        Estimate complexity of an expression (0-10).

        Factors:
        - Length
        - Number of operators
        - Parentheses depth
        - Special characters
        """
        complexity = 0

        # Length factor
        complexity += min(3, len(expression) // 10)

        # Operators
        operators = ['+', '-', '*', '/', '^', '√']
        complexity += sum(expression.count(op) for op in operators)

        # Parentheses depth
        max_depth = 0
        current_depth = 0
        for char in expression:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1
        complexity += max_depth

        # Functions (sin, cos, log, etc.)
        functions = ['sin', 'cos', 'tan', 'log', 'ln', 'exp', 'sqrt']
        complexity += sum(expression.lower().count(func) for func in functions)

        return min(10, complexity)

    def _evaluate_with_claude(
        self,
        candidate: DistractorCandidate,
        correct_answer: str,
        question_context: Dict[str, Any]
    ) -> float:
        """
        Use Claude to evaluate distractor quality.

        Returns:
            Quality score 0.0-10.0
        """
        try:
            prompt = f"""Evaluate the quality of this distractor for a multiple-choice question.

Correct Answer: {correct_answer}
Distractor: {candidate.value}
Misconception: {candidate.explanation}

Rate the distractor on a scale of 0-10 based on:
1. Pedagogical value (does it reveal a specific student error?)
2. Plausibility (would a student reasonably choose this?)
3. Not trivially wrong (not obviously incorrect)
4. Appropriate difficulty level

Return ONLY a number between 0.0 and 10.0.
"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=50,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract score from response
            content = response.content[0].text.strip()
            score = float(content)

            return max(0.0, min(10.0, score))

        except Exception as e:
            logger.warning(f"Claude evaluation failed: {e}")
            return candidate.plausibility_score

    def _is_trivial_distractor(self, distractor: str, correct_answer: str) -> bool:
        """
        Check if distractor is trivially wrong.

        A distractor is trivial if:
        - It's empty or just whitespace
        - It's identical to correct answer
        - It's dramatically different in length/complexity
        - It contains obvious errors (like "???" or "ERROR")
        """
        # Empty or whitespace
        if not distractor or not distractor.strip():
            return True

        # Identical to correct answer
        if distractor.strip() == correct_answer.strip():
            return True

        # Contains obvious error markers
        error_markers = ["???", "ERROR", "INVALID", "N/A", "undefined"]
        if any(marker in distractor.upper() for marker in error_markers):
            return True

        # Dramatically different length (>3x difference)
        if len(distractor) > 3 * len(correct_answer) or len(correct_answer) > 3 * len(distractor):
            return True

        return False

    def _generate_fallback_distractors(
        self,
        correct_answer: str,
        question_context: Dict[str, Any],
        count: int
    ) -> DistractorSet:
        """
        Generate fallback distractors when misconception-based generation fails.

        Uses simple heuristics:
        - Numerical modifications
        - Sign flips
        - Off-by-one errors
        """
        logger.info("Using fallback distractor generation")

        candidates = []

        # Strategy 1: Sign flip
        sign_flip = self._apply_wrong_sign(correct_answer, question_context)
        if sign_flip and sign_flip != correct_answer:
            candidates.append(DistractorCandidate(
                value=sign_flip,
                misconception_id="fallback_sign_flip",
                misconception="wrong_sign",
                transformation_rule="WRONG_SIGN",
                plausibility_score=7.0,
                quality_score=7.0,
                explanation="Common sign error"
            ))

        # Strategy 2: Off by one
        off_by_one = self._apply_off_by_one(correct_answer, question_context)
        if off_by_one and off_by_one != correct_answer:
            candidates.append(DistractorCandidate(
                value=off_by_one,
                misconception_id="fallback_off_by_one",
                misconception="off_by_one",
                transformation_rule="OFF_BY_ONE",
                plausibility_score=6.5,
                quality_score=6.5,
                explanation="Off-by-one error"
            ))

        # Strategy 3: Omit coefficient
        omit_coef = self._apply_omit_coefficient(correct_answer, question_context)
        if omit_coef and omit_coef != correct_answer:
            candidates.append(DistractorCandidate(
                value=omit_coef,
                misconception_id="fallback_omit_coefficient",
                misconception="omit_coefficient",
                transformation_rule="OMIT_COEFFICIENT",
                plausibility_score=7.5,
                quality_score=7.5,
                explanation="Forgot to include coefficient"
            ))

        # Select up to count distractors
        selected = candidates[:count]

        # If still not enough, generate generic distractors
        while len(selected) < count:
            generic = self._generate_generic_distractor(correct_answer, len(selected))
            if generic:
                selected.append(DistractorCandidate(
                    value=generic,
                    misconception_id="fallback_generic",
                    misconception="generic",
                    transformation_rule="GENERIC",
                    plausibility_score=6.0,
                    quality_score=6.0,
                    explanation="Generic distractor"
                ))

        avg_quality = (
            sum(d.quality_score for d in selected) / len(selected)
            if selected else 0.0
        )

        return DistractorSet(
            correct_answer=correct_answer,
            distractors=selected,
            question_id=question_context.get("question_id"),
            topic_id=question_context.get("topic_id"),
            course_id=question_context.get("course_id"),
            avg_quality_score=round(avg_quality, 2),
            metadata={"generation_method": "fallback"}
        )

    def _generate_generic_distractor(self, correct_answer: str, index: int) -> Optional[str]:
        """Generate a generic distractor as last resort."""
        # Extract numbers from correct answer
        numbers = re.findall(r'-?\d+\.?\d*', correct_answer)

        if numbers:
            # Modify first number based on index
            modifications = [
                lambda x: str(float(x) * 2),      # Double
                lambda x: str(float(x) / 2),      # Half
                lambda x: str(float(x) + 1),      # Plus one
                lambda x: str(float(x) - 1),      # Minus one
                lambda x: str(-float(x)),         # Negate
            ]

            if index < len(modifications):
                try:
                    first_num = numbers[0]
                    modified = modifications[index](first_num)
                    return correct_answer.replace(first_num, modified, 1)
                except Exception:
                    pass

        return None

    def _assign_ability_target(
        self,
        candidate: DistractorCandidate,
        difficulty_level: int
    ) -> str:
        """
        Assign ability target based on misconception difficulty and plausibility.

        Implements spec Phase 4: Ability-Based Targeting

        Args:
            candidate: DistractorCandidate with plausibility score
            difficulty_level: Question difficulty level (1-5)

        Returns:
            Target ability level: "low", "medium", "high", "low-medium", "medium-high"
        """
        # Use plausibility score as proxy for misconception difficulty
        # Higher plausibility = more subtle error = targets higher ability students
        plausibility = candidate.plausibility_score

        # Adjust based on question difficulty
        adjusted_score = plausibility + (difficulty_level - 3) * 0.5

        if adjusted_score < 6.0:
            return "low"  # Basic errors - obvious mistakes
        elif adjusted_score < 7.5:
            return "low-medium"  # Common procedural errors
        elif adjusted_score < 8.5:
            return "medium"  # Standard misconceptions
        elif adjusted_score < 9.5:
            return "medium-high"  # Subtle procedural errors
        else:
            return "high"  # Very subtle conceptual errors

    def _estimate_selection_rate(self, candidate: DistractorCandidate) -> float:
        """
        Estimate what percentage of students will select this distractor.

        Based on plausibility score and target ability.

        Args:
            candidate: DistractorCandidate with quality metrics

        Returns:
            Estimated selection rate (0.0-1.0)
        """
        # Base rate from plausibility (normalized to 0.05-0.25 range)
        # Higher plausibility = higher selection rate
        base_rate = 0.05 + (candidate.plausibility_score / 10.0) * 0.20

        # Adjust based on target ability
        # Low ability targets are selected more often
        if candidate.target_ability == "low":
            multiplier = 1.3
        elif candidate.target_ability == "low-medium":
            multiplier = 1.15
        elif candidate.target_ability == "medium":
            multiplier = 1.0
        elif candidate.target_ability == "medium-high":
            multiplier = 0.9
        else:  # high
            multiplier = 0.75

        estimated = base_rate * multiplier

        # Ensure within reasonable bounds (5%-30%)
        return max(0.05, min(0.30, estimated))

    def _optimize_distractor_set(
        self,
        candidates: List[DistractorCandidate],
        correct_answer: str,
        count: int
    ) -> List[DistractorCandidate]:
        """
        Select optimal set of distractors using combinatorial optimization.

        Implements spec Phase 5: Set Optimization
        Maximizes: diversity, plausibility, ability coverage

        Args:
            candidates: List of candidate distractors
            correct_answer: The correct answer
            count: Number of distractors to select

        Returns:
            Optimized list of DistractorCandidate objects
        """
        # If we have exactly the right number, return them
        if len(candidates) == count:
            return candidates

        # If we have fewer than needed, return all
        if len(candidates) < count:
            return candidates

        # Deduplicate candidates by value first
        unique_candidates = []
        seen_values = set()
        for candidate in candidates:
            if candidate.value not in seen_values:
                seen_values.add(candidate.value)
                unique_candidates.append(candidate)

        # If after dedup we don't have enough for optimization, return all
        if len(unique_candidates) <= count:
            return unique_candidates

        logger.debug(f"Optimizing distractor set: {len(unique_candidates)} candidates -> {count} selected")

        best_set = None
        best_score = -1.0

        # Try all combinations of 'count' distractors
        for combo in combinations(unique_candidates, count):
            # Calculate diversity score (different misconceptions)
            misconception_types = {d.misconception for d in combo}
            diversity = len(misconception_types) / count  # 0.0-1.0

            # Calculate average plausibility
            avg_plausibility = sum(d.plausibility_score for d in combo) / count
            plausibility_normalized = avg_plausibility / 10.0  # 0.0-1.0

            # Calculate ability coverage (how well we cover low/medium/high)
            ability_levels = {d.target_ability for d in combo}
            coverage = len(ability_levels) / 3.0  # 0.0-1.0 (assuming 3 main levels)

            # Combined score with weights from spec
            # 0.4 * diversity + 0.4 * plausibility + 0.2 * coverage
            combined_score = (
                0.4 * diversity +
                0.4 * plausibility_normalized +
                0.2 * coverage
            )

            if combined_score > best_score:
                best_score = combined_score
                best_set = list(combo)

        logger.debug(f"Selected set with score: {best_score:.3f}")

        return best_set if best_set else unique_candidates[:count]

    def _record_generation(self, distractor_set: DistractorSet) -> None:
        """Record distractor generation in history."""
        history_entry = {
            "timestamp": distractor_set.generated_at,
            "question_id": distractor_set.question_id,
            "topic_id": distractor_set.topic_id,
            "distractor_count": len(distractor_set.distractors),
            "avg_quality_score": distractor_set.avg_quality_score,
            "total_candidates": distractor_set.metadata.get("total_candidates", 0),
            "rejected_count": distractor_set.metadata.get("rejected_count", 0)
        }

        self.generation_history.append(history_entry)

        # Keep only last 100 entries
        if len(self.generation_history) > 100:
            self.generation_history = self.generation_history[-100:]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get distractor generation statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_distractors_generated": self.total_distractors_generated,
            "total_distractors_rejected": self.total_distractors_rejected,
            "acceptance_rate": (
                self.total_distractors_generated /
                (self.total_distractors_generated + self.total_distractors_rejected)
                if (self.total_distractors_generated + self.total_distractors_rejected) > 0
                else 0.0
            ),
            "generation_count": len(self.generation_history),
            "avg_quality_score": (
                sum(h["avg_quality_score"] for h in self.generation_history) /
                len(self.generation_history)
                if self.generation_history else 0.0
            )
        }

        return stats

    def get_generation_history(
        self,
        limit: Optional[int] = None,
        topic_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get distractor generation history.

        Args:
            limit: Maximum number of history entries to return
            topic_id: Filter by topic ID

        Returns:
            List of history entries
        """
        history = self.generation_history

        # Filter by topic if specified
        if topic_id:
            history = [h for h in history if h.get("topic_id") == topic_id]

        # Apply limit
        if limit:
            history = history[-limit:]

        return history
