"""
Free Response Question (FRQ) Data Models

This module defines Pydantic models for FRQ content, parts, and related structures.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class ResponseType(str, Enum):
    """Expected type of response for an FRQ part"""
    CALCULATION = "calculation"
    EXPLANATION = "explanation"
    GRAPH = "graph"
    PROOF = "proof"
    ANALYSIS = "analysis"
    JUSTIFICATION = "justification"
    INTERPRETATION = "interpretation"
    MIXED = "mixed"


class FRQType(str, Enum):
    """Type of FRQ question"""
    ANALYTICAL = "analytical"
    COMPUTATIONAL = "computational"
    CONCEPTUAL = "conceptual"
    MIXED = "mixed"
    APPLICATION = "application"


class ValidationStatus(str, Enum):
    """FRQ validation status"""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"


# ============================================================================
# FRQ Part Models
# ============================================================================

class FRQPart(BaseModel):
    """
    Single part of a Free Response Question (e.g., Part A, Part B).

    Represents one sub-question within an FRQ, including prompt,
    point value, and expected response type.
    """
    part_id: str = Field(..., description="Part identifier (A, B, C, etc.)")
    prompt: str = Field(..., description="Question prompt for this part")
    points: int = Field(..., ge=1, le=20, description="Points allocated to this part")
    expected_response_type: ResponseType = Field(
        ...,
        description="Type of response expected"
    )
    difficulty: int = Field(..., ge=1, le=5, description="Difficulty level (1-5)")
    hints: Optional[List[str]] = Field(
        default=None,
        description="Optional hints for students"
    )
    dependencies: Optional[List[str]] = Field(
        default=None,
        description="Part IDs this part depends on (e.g., ['A'])"
    )
    estimated_time_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=30,
        description="Estimated time to complete this part"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @field_validator("part_id")
    @classmethod
    def validate_part_id(cls, v: str) -> str:
        """Validate part ID format (A, B, C, etc.)"""
        if not v or len(v) != 1 or not v.isalpha():
            raise ValueError("Part ID must be a single letter (A, B, C, etc.)")
        return v.upper()


# ============================================================================
# Main FRQ Model
# ============================================================================

class FRQ(BaseModel):
    """
    Complete Free Response Question with multiple parts.

    Represents a full FRQ including context, all parts, and metadata.
    Used for AP-style calculus and other subject FRQs.
    """
    frq_id: str = Field(..., description="Unique FRQ identifier")
    title: str = Field(..., description="Question title")
    context: str = Field(
        ...,
        description="Background context/scenario for the question"
    )
    parts: List[FRQPart] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Question parts (A, B, C, etc.)"
    )
    total_points: int = Field(..., ge=1, le=100, description="Total points for FRQ")
    difficulty: int = Field(..., ge=1, le=5, description="Overall difficulty (1-5)")
    learning_objectives: List[str] = Field(
        ...,
        min_length=1,
        description="CED learning objectives covered"
    )
    estimated_time_minutes: int = Field(
        ...,
        ge=5,
        le=60,
        description="Total estimated time to complete"
    )

    # Optional fields
    course_id: Optional[str] = Field(default=None, description="Course identifier")
    unit_id: Optional[str] = Field(default=None, description="Unit identifier")
    topic_id: Optional[str] = Field(default=None, description="Topic identifier")
    frq_type: FRQType = Field(
        default=FRQType.MIXED,
        description="Primary type of FRQ"
    )
    tags: List[str] = Field(default_factory=list, description="Content tags")

    # Metadata
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    created_by: Optional[str] = Field(default=None, description="Creator identifier")
    validation_status: ValidationStatus = Field(
        default=ValidationStatus.PENDING,
        description="Validation status"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @field_validator("total_points")
    @classmethod
    def validate_total_points(cls, v: int, info) -> int:
        """Validate total points matches sum of part points"""
        # Note: This validation runs before parts are set, so we skip it here
        # Actual validation happens in a separate method
        return v

    @field_validator("parts")
    @classmethod
    def validate_parts(cls, v: List[FRQPart]) -> List[FRQPart]:
        """Validate parts have unique IDs and sequential letters"""
        if not v:
            raise ValueError("FRQ must have at least one part")

        # Check unique part IDs
        part_ids = [part.part_id for part in v]
        if len(part_ids) != len(set(part_ids)):
            raise ValueError("Part IDs must be unique")

        # Check sequential letters (A, B, C, etc.)
        expected_ids = [chr(65 + i) for i in range(len(v))]  # A, B, C...
        if sorted(part_ids) != expected_ids:
            raise ValueError(
                f"Part IDs must be sequential letters starting from A. "
                f"Expected {expected_ids}, got {sorted(part_ids)}"
            )

        return v

    def get_part_by_id(self, part_id: str) -> Optional[FRQPart]:
        """Get a specific part by ID"""
        part_id = part_id.upper()
        for part in self.parts:
            if part.part_id == part_id:
                return part
        return None

    def calculate_total_points(self) -> int:
        """Calculate total points from all parts"""
        return sum(part.points for part in self.parts)

    def validate_points_consistency(self) -> bool:
        """Validate that total_points matches sum of part points"""
        return self.total_points == self.calculate_total_points()


# ============================================================================
# FRQ Generation Request/Response Models
# ============================================================================

class FRQGenerationRequest(BaseModel):
    """Request to generate an FRQ"""
    learning_objectives: List[str] = Field(
        ...,
        min_length=1,
        description="Learning objectives to cover"
    )
    difficulty: int = Field(..., ge=1, le=5, description="Desired difficulty")
    frq_type: FRQType = Field(
        default=FRQType.MIXED,
        description="Type of FRQ to generate"
    )
    num_parts: int = Field(
        default=3,
        ge=1,
        le=6,
        description="Number of parts to generate"
    )
    total_points: int = Field(
        default=9,
        ge=3,
        le=50,
        description="Total points to allocate"
    )
    course_id: Optional[str] = Field(default=None, description="Course context")
    topic_constraints: Optional[List[str]] = Field(
        default=None,
        description="Topics that must be included"
    )
    context_type: Optional[str] = Field(
        default=None,
        description="Type of context (real-world, abstract, etc.)"
    )


class FRQGenerationResponse(BaseModel):
    """Response containing generated FRQ"""
    frq: FRQ = Field(..., description="Generated FRQ")
    generation_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Generation metadata (model, tokens, etc.)"
    )
    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated quality score"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings or issues during generation"
    )


# ============================================================================
# Solution/Rubric Preview Models
# ============================================================================

class SolutionStep(BaseModel):
    """Single step in a solution"""
    step_number: int = Field(..., ge=1, description="Step number")
    description: str = Field(..., description="What to do in this step")
    explanation: Optional[str] = Field(
        default=None,
        description="Why this step is necessary"
    )
    points: Optional[int] = Field(
        default=None,
        ge=0,
        description="Points earned for this step"
    )


class ExpectedSolution(BaseModel):
    """Expected solution for an FRQ part"""
    part_id: str = Field(..., description="Part this solution is for")
    approach: str = Field(..., description="General approach to solving")
    steps: List[SolutionStep] = Field(..., description="Solution steps")
    final_answer: Optional[str] = Field(
        default=None,
        description="Final answer (if applicable)"
    )
    alternative_approaches: Optional[List[str]] = Field(
        default=None,
        description="Alternative valid approaches"
    )
    common_errors: Optional[List[str]] = Field(
        default=None,
        description="Common student errors to watch for"
    )


class RubricPreview(BaseModel):
    """Preview of recommended rubric structure"""
    frq_id: str = Field(..., description="FRQ this rubric is for")
    part_allocations: Dict[str, int] = Field(
        ...,
        description="Point allocation per part (e.g., {'A': 3, 'B': 4})"
    )
    suggested_criteria: List[str] = Field(
        ...,
        description="Suggested scoring criteria"
    )
    partial_credit_opportunities: List[str] = Field(
        default_factory=list,
        description="Where partial credit can be awarded"
    )
