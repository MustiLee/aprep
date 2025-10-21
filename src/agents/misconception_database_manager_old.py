"""
Misconception Database Manager Agent

This agent manages a database of common student misconceptions in mathematics,
organized by topic and course. It provides CRUD operations and integrates with
the Distractor Designer to generate pedagogically sound wrong answer choices.

Responsibilities:
- Store and retrieve misconceptions by topic/course
- Categorize misconceptions (algebraic, conceptual, procedural)
- Tag misconceptions with difficulty levels
- Search and filter misconceptions
- Track misconception usage and effectiveness
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError

logger = setup_logger(__name__)


class MisconceptionCategory:
    """Category types for misconceptions"""
    ALGEBRAIC = "algebraic"  # Algebraic manipulation errors
    CONCEPTUAL = "conceptual"  # Misunderstanding of concepts
    PROCEDURAL = "procedural"  # Incorrect procedure application
    NOTATIONAL = "notational"  # Notation-related errors
    COMPUTATIONAL = "computational"  # Calculation errors


class DistractorRule(BaseModel):
    """
    Rules for generating distractors from this misconception.
    Used by Distractor Designer agent.
    """

    transformation_rule: str = Field(..., description="Rule name (e.g., REMOVE_INNER_DERIVATIVE)")
    template: str = Field(..., description="Template string with placeholders")
    example_usage: Optional[str] = Field(None, description="Example of how to use this rule")
    plausibility_score: float = Field(default=7.0, ge=0.0, le=10.0, description="How plausible 0-10")
    recommended_question_types: List[str] = Field(default_factory=list, description="Question types to use with")

    # Additional parameters for transformation
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional transformation parameters")


class Misconception(BaseModel):
    """A single misconception entry"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str = Field(..., description="Course identifier (e.g., ap_calculus_bc)")
    topic_id: str = Field(..., description="Topic identifier (e.g., derivatives)")
    unit_id: Optional[str] = Field(None, description="Unit identifier")

    title: str = Field(..., description="Short title of misconception")
    description: str = Field(..., description="Detailed description")
    category: str = Field(..., description="Category type")

    example: Optional[str] = Field(None, description="Example of misconception")
    correct_approach: Optional[str] = Field(None, description="Correct approach explanation")

    difficulty_level: int = Field(default=2, ge=1, le=5, description="Difficulty 1-5")
    prevalence: str = Field(default="medium", description="common, medium, rare")

    tags: List[str] = Field(default_factory=list, description="Additional tags")
    related_los: List[str] = Field(default_factory=list, description="Related learning objectives")

    # NEW: Distractor generation rules for Distractor Designer integration
    distractor_generation: Optional[DistractorRule] = Field(None, description="Rules for generating distractors")

    usage_count: int = Field(default=0, description="Times used in questions")
    effectiveness_score: Optional[float] = Field(None, description="0-1 effectiveness score")

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    metadata: Dict[str, Any] = Field(default_factory=dict)


class MisconceptionDatabaseManager:
    """
    Manages the misconception database with CRUD operations and search capabilities.
    """

    def __init__(self, data_dir: str = "data/misconceptions"):
        """
        Initialize the Misconception Database Manager.

        Args:
            data_dir: Directory to store misconception data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Schema file for validation
        self.schema_file = self.data_dir / "schema.json"
        self._ensure_schema()

        logger.info(f"Initialized MisconceptionDatabaseManager with data_dir={data_dir}")

    def _ensure_schema(self) -> None:
        """Ensure schema file exists"""
        if not self.schema_file.exists():
            schema = {
                "version": "1.0.0",
                "categories": [
                    "algebraic",
                    "conceptual",
                    "procedural",
                    "notational",
                    "computational"
                ],
                "difficulty_levels": [1, 2, 3, 4, 5],
                "prevalence_levels": ["common", "medium", "rare"]
            }
            with open(self.schema_file, 'w') as f:
                json.dump(schema, f, indent=2)
            logger.info("Created misconception schema file")

    def create(self, misconception_data: Dict[str, Any]) -> Misconception:
        """
        Create a new misconception entry.

        Args:
            misconception_data: Dictionary with misconception details

        Returns:
            Created Misconception object

        Raises:
            AprepError: If creation fails
        """
        try:
            # Validate and create
            misconception = Misconception(**misconception_data)

            # Save to file
            self._save_misconception(misconception)

            logger.info(f"Created misconception: {misconception.id} - {misconception.title}")
            return misconception

        except Exception as e:
            logger.error(f"Failed to create misconception: {e}")
            raise AprepError(f"Misconception creation failed: {e}")

    def read(self, misconception_id: str) -> Optional[Misconception]:
        """
        Read a misconception by ID.

        Args:
            misconception_id: Misconception ID

        Returns:
            Misconception object or None if not found
        """
        try:
            file_path = self._get_misconception_file(misconception_id)

            if not file_path.exists():
                logger.warning(f"Misconception not found: {misconception_id}")
                return None

            with open(file_path, 'r') as f:
                data = json.load(f)

            return Misconception(**data)

        except Exception as e:
            logger.error(f"Failed to read misconception {misconception_id}: {e}")
            return None

    def update(self, misconception_id: str, updates: Dict[str, Any]) -> Optional[Misconception]:
        """
        Update a misconception.

        Args:
            misconception_id: Misconception ID
            updates: Dictionary of fields to update

        Returns:
            Updated Misconception or None if not found
        """
        try:
            misconception = self.read(misconception_id)

            if not misconception:
                return None

            # Update fields
            for key, value in updates.items():
                if hasattr(misconception, key):
                    setattr(misconception, key, value)

            # Update timestamp
            misconception.updated_at = datetime.now().isoformat()

            # Save
            self._save_misconception(misconception)

            logger.info(f"Updated misconception: {misconception_id}")
            return misconception

        except Exception as e:
            logger.error(f"Failed to update misconception {misconception_id}: {e}")
            raise AprepError(f"Misconception update failed: {e}")

    def delete(self, misconception_id: str) -> bool:
        """
        Delete a misconception.

        Args:
            misconception_id: Misconception ID

        Returns:
            True if deleted, False if not found
        """
        try:
            file_path = self._get_misconception_file(misconception_id)

            if not file_path.exists():
                return False

            file_path.unlink()
            logger.info(f"Deleted misconception: {misconception_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete misconception {misconception_id}: {e}")
            raise AprepError(f"Misconception deletion failed: {e}")

    def search(
        self,
        course_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        category: Optional[str] = None,
        difficulty_level: Optional[int] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Misconception]:
        """
        Search for misconceptions with filters.

        Args:
            course_id: Filter by course
            topic_id: Filter by topic
            unit_id: Filter by unit
            category: Filter by category
            difficulty_level: Filter by difficulty
            tags: Filter by tags (must match all)
            limit: Maximum results

        Returns:
            List of matching Misconception objects
        """
        try:
            results = []

            # Iterate through all misconception files
            for file_path in self.data_dir.glob("*.json"):
                if file_path.name == "schema.json":
                    continue

                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)

                    misconception = Misconception(**data)

                    # Apply filters
                    if course_id and misconception.course_id != course_id:
                        continue
                    if topic_id and misconception.topic_id != topic_id:
                        continue
                    if unit_id and misconception.unit_id != unit_id:
                        continue
                    if category and misconception.category != category:
                        continue
                    if difficulty_level and misconception.difficulty_level != difficulty_level:
                        continue
                    if tags and not all(tag in misconception.tags for tag in tags):
                        continue

                    results.append(misconception)

                    if limit and len(results) >= limit:
                        break

                except Exception as e:
                    logger.warning(f"Skipping invalid file {file_path}: {e}")
                    continue

            # Sort by usage count (most used first)
            results.sort(key=lambda m: m.usage_count, reverse=True)

            logger.info(f"Search returned {len(results)} misconceptions")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise AprepError(f"Misconception search failed: {e}")

    def list_by_course(self, course_id: str) -> List[Misconception]:
        """Get all misconceptions for a course"""
        return self.search(course_id=course_id)

    def list_by_topic(self, course_id: str, topic_id: str) -> List[Misconception]:
        """Get all misconceptions for a specific topic"""
        return self.search(course_id=course_id, topic_id=topic_id)

    def get_by_category(self, category: str, course_id: Optional[str] = None) -> List[Misconception]:
        """Get misconceptions by category"""
        return self.search(course_id=course_id, category=category)

    def increment_usage(self, misconception_id: str) -> None:
        """Increment usage count for a misconception"""
        misconception = self.read(misconception_id)
        if misconception:
            misconception.usage_count += 1
            misconception.updated_at = datetime.now().isoformat()
            self._save_misconception(misconception)
            logger.debug(f"Incremented usage count for {misconception_id}")

    def update_effectiveness(self, misconception_id: str, score: float) -> None:
        """
        Update effectiveness score (0-1) based on student performance.

        Args:
            misconception_id: Misconception ID
            score: Effectiveness score 0-1 (higher = more effective distractor)
        """
        misconception = self.read(misconception_id)
        if misconception:
            # Running average if score exists
            if misconception.effectiveness_score is not None:
                misconception.effectiveness_score = (
                    0.7 * misconception.effectiveness_score + 0.3 * score
                )
            else:
                misconception.effectiveness_score = score

            misconception.updated_at = datetime.now().isoformat()
            self._save_misconception(misconception)
            logger.debug(f"Updated effectiveness for {misconception_id}: {score:.2f}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            all_misconceptions = self.search()

            stats = {
                "total_count": len(all_misconceptions),
                "by_category": {},
                "by_difficulty": {},
                "by_prevalence": {},
                "by_course": {},
                "avg_usage": 0,
                "avg_effectiveness": 0
            }

            total_usage = 0
            effectiveness_scores = []

            for m in all_misconceptions:
                # Category
                stats["by_category"][m.category] = stats["by_category"].get(m.category, 0) + 1

                # Difficulty
                stats["by_difficulty"][m.difficulty_level] = stats["by_difficulty"].get(m.difficulty_level, 0) + 1

                # Prevalence
                stats["by_prevalence"][m.prevalence] = stats["by_prevalence"].get(m.prevalence, 0) + 1

                # Course
                stats["by_course"][m.course_id] = stats["by_course"].get(m.course_id, 0) + 1

                # Usage
                total_usage += m.usage_count

                # Effectiveness
                if m.effectiveness_score is not None:
                    effectiveness_scores.append(m.effectiveness_score)

            if len(all_misconceptions) > 0:
                stats["avg_usage"] = total_usage / len(all_misconceptions)

            if effectiveness_scores:
                stats["avg_effectiveness"] = sum(effectiveness_scores) / len(effectiveness_scores)

            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def _save_misconception(self, misconception: Misconception) -> None:
        """Save misconception to file"""
        file_path = self._get_misconception_file(misconception.id)

        with open(file_path, 'w') as f:
            json.dump(misconception.model_dump(), f, indent=2)

    def _get_misconception_file(self, misconception_id: str) -> Path:
        """Get file path for a misconception"""
        return self.data_dir / f"{misconception_id}.json"


# Example misconceptions for seeding
EXAMPLE_MISCONCEPTIONS = [
    {
        "course_id": "ap_calculus_bc",
        "topic_id": "derivatives",
        "title": "Forgot to multiply by exponent in power rule",
        "description": "Student applies d/dx[x^n] = x^(n-1) instead of n*x^(n-1)",
        "category": "procedural",
        "example": "d/dx[x^3] = x^2 (missing the 3 coefficient)",
        "correct_approach": "Power rule: d/dx[x^n] = n*x^(n-1)",
        "difficulty_level": 2,
        "prevalence": "common",
        "tags": ["power_rule", "derivatives", "algebraic_error"],
        "distractor_generation": {
            "transformation_rule": "OMIT_COEFFICIENT",
            "template": "{{base}}^{{exponent_minus_one}}",
            "example_usage": "For d/dx[x^3], generate distractor x^2 (omit coefficient 3)",
            "plausibility_score": 8.5,
            "recommended_question_types": ["power_rule_basic", "polynomial_derivatives"],
            "parameters": {
                "apply_to": "power_terms",
                "preserve_base": True,
                "decrease_exponent": True
            }
        }
    },
    {
        "course_id": "ap_calculus_bc",
        "topic_id": "derivatives",
        "title": "Incorrect chain rule application",
        "description": "Student forgets to multiply by inner derivative",
        "category": "procedural",
        "example": "d/dx[sin(2x)] = cos(2x) instead of 2cos(2x)",
        "correct_approach": "Chain rule: d/dx[f(g(x))] = f'(g(x)) * g'(x)",
        "difficulty_level": 3,
        "prevalence": "common",
        "tags": ["chain_rule", "derivatives", "composition"],
        "distractor_generation": {
            "transformation_rule": "REMOVE_INNER_DERIVATIVE",
            "template": "{{outer_derivative}}({{inner_function}})",
            "example_usage": "For d/dx[sin(2x)], generate distractor cos(2x) (omit the 2)",
            "plausibility_score": 9.0,
            "recommended_question_types": ["chain_rule", "composite_functions", "trigonometric_derivatives"],
            "parameters": {
                "apply_to": "composite_functions",
                "keep_outer_derivative": True,
                "omit_inner_derivative": True
            }
        }
    },
    {
        "course_id": "ap_calculus_bc",
        "topic_id": "integration",
        "title": "Forgot +C constant",
        "description": "Student omits constant of integration",
        "category": "conceptual",
        "example": "∫x dx = x^2/2 (missing +C)",
        "correct_approach": "Indefinite integrals must include +C",
        "difficulty_level": 1,
        "prevalence": "very_common",
        "tags": ["integration", "constant", "indefinite_integral"],
        "distractor_generation": {
            "transformation_rule": "OMIT_CONSTANT",
            "template": "{{integral_result}}",
            "example_usage": "For ∫x dx, generate distractor x^2/2 (omit +C)",
            "plausibility_score": 7.0,
            "recommended_question_types": ["indefinite_integrals", "antiderivatives"],
            "parameters": {
                "apply_to": "indefinite_integrals",
                "remove_constant": True
            }
        }
    }
]


def seed_database(manager: MisconceptionDatabaseManager) -> None:
    """Seed database with example misconceptions"""
    logger.info("Seeding misconception database...")

    for misconception_data in EXAMPLE_MISCONCEPTIONS:
        try:
            manager.create(misconception_data)
        except Exception as e:
            logger.warning(f"Failed to seed misconception: {e}")

    logger.info(f"Seeded {len(EXAMPLE_MISCONCEPTIONS)} misconceptions")
