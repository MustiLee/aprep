"""
FRQ Author Agent - Free Response Question Generation

Spec: Aprep/.claude/agents/frq-author.md
Version: 1.0
Model: Claude Opus 4 (creative writing, pedagogical reasoning)

This agent generates original AP-style Free Response Questions (FRQs) with:
- Multi-part scaffolded questions
- Authentic real-world contexts
- Sample student responses (strong, medium, weak)
- Pedagogical analysis
- CED alignment

Key Features:
- Context generation with cultural sensitivity
- Bloom's taxonomy alignment
- Difficulty progression across parts
- Sample response generation
- Quality validation
"""

from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import anthropic
from datetime import datetime
import logging
import json
import hashlib

from src.core.config import settings
from src.core.logger import get_logger
from src.core.exceptions import AprepError
from src.models.frq import (
    FRQ,
    FRQPart,
    ResponseType,
    FRQType,
    ValidationStatus,
    FRQGenerationRequest,
    FRQGenerationResponse,
    ExpectedSolution,
    SolutionStep,
    RubricPreview
)

logger = get_logger(__name__)


# ============================================================================
# Configuration Models
# ============================================================================

class FRQAuthorConfig(BaseModel):
    """Configuration for FRQ Author agent"""
    model_name: str = Field(
        default="claude-opus-4-20250514",
        description="Claude model for generation"
    )
    max_retries: int = Field(default=3, description="Max retries for generation")
    generation_timeout: int = Field(default=120, description="Timeout in seconds")
    validation_enabled: bool = Field(default=True, description="Enable validation")
    context_min_length: int = Field(default=50, description="Min context length")
    context_max_length: int = Field(default=500, description="Max context length")
    readability_max_grade: float = Field(
        default=14.0,
        description="Max acceptable readability grade"
    )


class ContextPreferences(BaseModel):
    """Preferences for context generation"""
    real_world: bool = Field(default=True, description="Use real-world scenarios")
    avoid_topics: List[str] = Field(
        default_factory=lambda: ["luxury_items", "weapons", "alcohol", "gambling"],
        description="Topics to avoid"
    )
    cultural_sensitivity: str = Field(
        default="high",
        description="Cultural sensitivity level (low/medium/high)"
    )


class PedagogicalGuidelines(BaseModel):
    """Pedagogical guidelines for FRQ generation"""
    bloom_taxonomy_levels: List[str] = Field(
        default_factory=lambda: ["apply", "analyze", "evaluate"],
        description="Bloom's taxonomy levels to target"
    )
    mathematical_practices: List[str] = Field(
        default_factory=lambda: ["modeling", "reasoning", "communicating"],
        description="Mathematical practices to assess"
    )
    common_misconceptions: List[str] = Field(
        default_factory=list,
        description="Common student misconceptions to address"
    )


# ============================================================================
# FRQ Author Agent
# ============================================================================

class FRQAuthor:
    """
    Generates high-quality Free Response Questions for AP exams.

    Features:
    - Multi-part question generation (Part A, B, C)
    - Authentic context creation
    - Difficulty calibration and scaffolding
    - Sample student responses
    - Pedagogical analysis
    """

    def __init__(
        self,
        config: Optional[FRQAuthorConfig] = None,
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize FRQ Author agent.

        Args:
            config: Optional configuration
            anthropic_api_key: Optional API key (defaults to settings)
        """
        self.config = config or FRQAuthorConfig()

        # Initialize Anthropic client
        api_key = anthropic_api_key or settings.ANTHROPIC_API_KEY
        if not api_key:
            raise AprepError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=api_key)

        # Statistics
        self.stats = {
            "total_generated": 0,
            "total_validated": 0,
            "total_failed": 0,
            "avg_generation_time_ms": 0,
            "context_cache_hits": 0,
            "context_cache_misses": 0
        }

        # Context cache (to avoid regenerating similar contexts)
        self._context_cache: Dict[str, str] = {}

        logger.info(
            f"Initialized FRQ Author (model={self.config.model_name}, "
            f"validation={'enabled' if self.config.validation_enabled else 'disabled'})"
        )

    # ========================================================================
    # Main Generation Method
    # ========================================================================

    def generate_frq(
        self,
        request: FRQGenerationRequest,
        context_preferences: Optional[ContextPreferences] = None,
        pedagogical_guidelines: Optional[PedagogicalGuidelines] = None
    ) -> FRQGenerationResponse:
        """
        Generate a complete FRQ with all parts and sample responses.

        Args:
            request: Generation request with requirements
            context_preferences: Optional context preferences
            pedagogical_guidelines: Optional pedagogical guidelines

        Returns:
            FRQGenerationResponse with generated FRQ

        Raises:
            AprepError: If generation fails
        """
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"Generating FRQ: {len(request.learning_objectives)} LOs, "
                f"{request.num_parts} parts, difficulty={request.difficulty}"
            )

            # Set defaults
            context_prefs = context_preferences or ContextPreferences()
            ped_guidelines = pedagogical_guidelines or PedagogicalGuidelines()

            # Step 1: Generate authentic context
            context = self._generate_context(
                course_id=request.course_id or "ap_calculus_bc",
                learning_objectives=request.learning_objectives,
                preferences=context_prefs
            )

            # Step 2: Design scaffolded parts
            parts = self._design_scaffolded_parts(
                context=context,
                learning_objectives=request.learning_objectives,
                num_parts=request.num_parts,
                total_points=request.total_points,
                difficulty=request.difficulty,
                frq_type=request.frq_type
            )

            # Step 3: Create FRQ model
            frq = self._create_frq_model(
                context=context,
                parts=parts,
                request=request
            )

            # Step 4: Generate sample responses (optional, for rich output)
            # This is done in a separate method to keep generation fast

            # Step 5: Validate (if enabled)
            warnings = []
            if self.config.validation_enabled:
                passed, issues = self._validate_frq(frq)
                if not passed:
                    critical_issues = [i for i in issues if i.get("severity") == "critical"]
                    if critical_issues:
                        self.stats["total_failed"] += 1
                        raise AprepError(
                            f"FRQ validation failed: {critical_issues[0]['message']}"
                        )
                warnings = [i["message"] for i in issues if i.get("severity") != "critical"]

            # Update statistics
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.stats["total_generated"] += 1
            self.stats["avg_generation_time_ms"] = (
                (self.stats["avg_generation_time_ms"] * (self.stats["total_generated"] - 1) + duration_ms)
                / self.stats["total_generated"]
            )

            logger.info(
                f"FRQ generated successfully: {frq.frq_id} "
                f"({duration_ms:.0f}ms, {len(warnings)} warnings)"
            )

            return FRQGenerationResponse(
                frq=frq,
                generation_metadata={
                    "model": self.config.model_name,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat()
                },
                quality_score=self._estimate_quality_score(frq),
                warnings=warnings
            )

        except Exception as e:
            self.stats["total_failed"] += 1
            logger.error(f"FRQ generation failed: {e}")
            raise AprepError(f"Failed to generate FRQ: {e}")

    # ========================================================================
    # Context Generation (Spec Step 1)
    # ========================================================================

    def _generate_context(
        self,
        course_id: str,
        learning_objectives: List[str],
        preferences: ContextPreferences
    ) -> str:
        """
        Generate authentic context for FRQ.

        Implements spec lines 236-282 (Context Generation).

        Args:
            course_id: Course identifier
            learning_objectives: Learning objectives to cover
            preferences: Context preferences

        Returns:
            Generated context string
        """
        # Check cache first
        cache_key = self._get_context_cache_key(
            course_id, learning_objectives, preferences
        )

        if cache_key in self._context_cache:
            self.stats["context_cache_hits"] += 1
            logger.debug("Context cache hit")
            return self._context_cache[cache_key]

        self.stats["context_cache_misses"] += 1

        # Context categories by course (spec lines 241-251)
        context_categories = {
            "ap_calculus_bc": [
                "physics_motion", "rate_problems", "accumulation",
                "optimization", "growth_decay", "related_rates", "area_volume"
            ],
            "ap_statistics": [
                "medical_studies", "social_science", "quality_control",
                "polling", "environmental", "sports_analytics"
            ],
            "ap_physics_c": [
                "experimental_design", "data_analysis", "mechanics",
                "electromagnetism"
            ]
        }

        categories = context_categories.get(course_id, ["general_application"])

        # Generate context with LLM (spec lines 257-269)
        prompt = self._build_context_generation_prompt(
            course_id=course_id,
            categories=categories,
            learning_objectives=learning_objectives,
            preferences=preferences
        )

        # Retry logic for validation (spec lines 271-275)
        for attempt in range(self.config.max_retries):
            try:
                context = self._call_claude(
                    prompt=prompt,
                    max_tokens=300,
                    temperature=0.8  # Higher for creativity
                )

                # Validate context
                if self._is_valid_context(context, preferences):
                    # Cache successful generation
                    self._context_cache[cache_key] = context
                    logger.debug(f"Generated context ({len(context)} chars, attempt {attempt + 1})")
                    return context
                else:
                    logger.warning(f"Context validation failed (attempt {attempt + 1})")

            except Exception as e:
                logger.error(f"Context generation error (attempt {attempt + 1}): {e}")

        # Fallback to template-based context
        logger.warning("Using fallback template context")
        return self._get_fallback_context(course_id, learning_objectives)

    def _build_context_generation_prompt(
        self,
        course_id: str,
        categories: List[str],
        learning_objectives: List[str],
        preferences: ContextPreferences
    ) -> str:
        """Build prompt for context generation"""
        avoid_topics_str = ", ".join(preferences.avoid_topics)
        lo_str = "\n".join(f"- {lo}" for lo in learning_objectives)

        prompt = f"""Create an authentic, engaging context for an AP {course_id} Free Response Question.

Requirements:
- Context category: Choose from [{', '.join(categories)}]
- Learning objectives to address:
{lo_str}

Guidelines:
- Use a real-world scenario that motivates mathematical analysis
- Provide clear, specific data or mathematical functions
- 2-3 sentences maximum
- Grade level: 11-12 (AP students)
- Culturally neutral and inclusive
- Avoid these topics: {avoid_topics_str}
{"- Use real-world applications" if preferences.real_world else "- Abstract mathematical scenario acceptable"}

Example format (for calculus):
"A water tank is being filled at a variable rate. The rate of water flowing into the tank, in gallons per minute, is given by R(t) = 5 + 2sin(πt/6) for 0 ≤ t ≤ 12, where t is measured in minutes."

Generate the context now:"""

        return prompt

    def _is_valid_context(self, context: str, preferences: ContextPreferences) -> bool:
        """
        Validate generated context.

        Implements spec lines 278-282 (validation check).
        """
        # Length check
        if len(context) < self.config.context_min_length:
            logger.debug(f"Context too short: {len(context)} chars")
            return False

        if len(context) > self.config.context_max_length:
            logger.debug(f"Context too long: {len(context)} chars")
            return False

        # Check for avoided topics
        context_lower = context.lower()
        for topic in preferences.avoid_topics:
            if topic.lower() in context_lower:
                logger.debug(f"Context contains avoided topic: {topic}")
                return False

        # Basic bias check (simplified - full bias detector would be used in production)
        bias_keywords = ["he", "she", "his", "her"]  # Simplified check
        if preferences.cultural_sensitivity == "high":
            # More strict checking would be done by Bias Detector agent
            pass

        return True

    def _get_context_cache_key(
        self,
        course_id: str,
        learning_objectives: List[str],
        preferences: ContextPreferences
    ) -> str:
        """Generate cache key for context"""
        key_str = f"{course_id}:{'-'.join(sorted(learning_objectives))}:{preferences.json()}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_fallback_context(self, course_id: str, learning_objectives: List[str]) -> str:
        """Get fallback template context if generation fails"""
        fallbacks = {
            "ap_calculus_bc": "A particle moves along a line with velocity v(t) = 3t² - 12t + 9 for t ≥ 0, where t is measured in seconds and v(t) is measured in meters per second.",
            "ap_statistics": "A researcher is studying the relationship between study time and test scores among high school students. A random sample of 100 students was surveyed.",
            "ap_physics_c": "An object of mass m is subject to a time-varying force F(t) = F₀sin(ωt) in one dimension."
        }
        return fallbacks.get(course_id, "Consider the following mathematical problem.")

    # ========================================================================
    # Multi-Part Question Design (Spec Step 2)
    # ========================================================================

    def _design_scaffolded_parts(
        self,
        context: str,
        learning_objectives: List[str],
        num_parts: int,
        total_points: int,
        difficulty: int,
        frq_type: FRQType
    ) -> List[FRQPart]:
        """
        Design scaffolded question parts that build in complexity.

        Implements spec lines 284-351 (Multi-Part Question Design).

        Args:
            context: Generated context
            learning_objectives: Learning objectives to assess
            num_parts: Number of parts to generate
            total_points: Total points to distribute
            difficulty: Overall difficulty (1-5)
            frq_type: Type of FRQ

        Returns:
            List of FRQ parts
        """
        logger.debug(f"Designing {num_parts} scaffolded parts")

        # Distribute points (spec lines 297-298)
        points_per_part = self._distribute_points(num_parts, total_points)

        # Generate each part
        parts = []
        for i in range(num_parts):
            part_letter = chr(65 + i)  # A, B, C, ...

            # Calculate part difficulty (spec lines 318-326)
            part_difficulty = self._calculate_part_difficulty(
                part_index=i,
                total_parts=num_parts,
                base_difficulty=difficulty
            )

            # Select learning objective for this part
            lo_index = min(i, len(learning_objectives) - 1)
            part_lo = learning_objectives[lo_index]

            # Generate part question
            part_prompt = self._generate_part_question(
                context=context,
                part_id=part_letter,
                learning_objective=part_lo,
                difficulty=part_difficulty,
                frq_type=frq_type,
                part_number=i + 1,
                total_parts=num_parts
            )

            # Determine response type
            response_type = self._determine_response_type(part_lo, frq_type)

            # Create FRQ part
            part = FRQPart(
                part_id=part_letter,
                prompt=part_prompt,
                points=points_per_part[i],
                expected_response_type=response_type,
                difficulty=part_difficulty,
                dependencies=[chr(65 + j) for j in range(i)] if i > 0 else None,
                estimated_time_minutes=self._estimate_part_time(points_per_part[i]),
                metadata={
                    "learning_objective": part_lo,
                    "scaffold_level": i + 1
                }
            )

            parts.append(part)
            logger.debug(
                f"Part {part_letter}: {points_per_part[i]}pts, "
                f"difficulty={part_difficulty}, type={response_type}"
            )

        return parts

    def _distribute_points(self, num_parts: int, total_points: int) -> List[int]:
        """
        Distribute points across parts.

        Typically equal distribution or slightly increasing.
        """
        if total_points % num_parts == 0:
            # Equal distribution
            return [total_points // num_parts] * num_parts
        else:
            # Distribute with slight increase
            base = total_points // num_parts
            remainder = total_points % num_parts

            points = [base] * num_parts
            # Add remainder to later parts (harder parts get more points)
            for i in range(remainder):
                points[-(i + 1)] += 1

            return points

    def _calculate_part_difficulty(
        self,
        part_index: int,
        total_parts: int,
        base_difficulty: int
    ) -> int:
        """
        Calculate difficulty for a specific part.

        Implements spec lines 318-326 (difficulty progression).
        Parts increase in difficulty: A < B < C

        Args:
            part_index: Index of part (0, 1, 2, ...)
            total_parts: Total number of parts
            base_difficulty: Base difficulty level (1-5)

        Returns:
            Difficulty for this part (1-5)
        """
        # Progressive difficulty
        if total_parts == 1:
            return base_difficulty

        # Scale from base-1 to base+1
        min_diff = max(1, base_difficulty - 1)
        max_diff = min(5, base_difficulty + 1)

        # Linear progression
        difficulty_range = max_diff - min_diff
        increment = difficulty_range / (total_parts - 1) if total_parts > 1 else 0

        return min(5, max(1, int(min_diff + (part_index * increment))))

    # Continued in next message due to length...
    # This is a solid foundation! We'll continue with:
    # - _generate_part_question()
    # - _create_frq_model()
    # - _validate_frq()
    # - _call_claude() helper
    # - Statistics methods
