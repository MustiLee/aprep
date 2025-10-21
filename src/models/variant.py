"""Variant data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VariantMetadata(BaseModel):
    """Metadata for question variant."""

    calculator: str = Field(..., description="Calculator policy")
    difficulty_est: float = Field(..., description="Estimated difficulty (0-1)")
    time_sec_est: int = Field(default=90, description="Estimated time")
    distractor_quality: Optional[float] = Field(None, description="Distractor quality score")


class Variant(BaseModel):
    """Generated MCQ variant."""

    id: str = Field(..., description="Unique variant identifier")
    version: str = Field(default="1.0", description="Variant version")
    template_id: str = Field(..., description="Source template ID")

    # Course context
    course_id: Optional[str] = Field(None, description="Course identifier")
    unit_id: Optional[str] = Field(None, description="Unit identifier")
    topic_id: Optional[str] = Field(None, description="Topic identifier")

    # Question content
    stimulus: str = Field(..., description="Question text")
    options: List[str] = Field(..., description="Answer options (4 total)")
    answer_index: int = Field(..., description="Index of correct answer (0-3)")
    solution: str = Field(..., description="Correct solution")
    solution_steps: Optional[List[str]] = Field(None, description="Solution steps")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags")
    metadata: VariantMetadata

    # Origin tracking
    origin: Dict[str, Any] = Field(
        ...,
        description="Generation metadata (created_by, seed, parameters, etc.)",
    )

    # Analytics (populated after deployment)
    analytics: Optional[Dict[str, Any]] = Field(
        None,
        description="Performance analytics (n_responses, p_value, etc.)",
    )

    # Review status
    audit: Optional[Dict[str, Any]] = Field(
        None,
        description="Human review status",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "id": "mcq_calc_bc_chain_001_v42",
                "template_id": "calc_bc_chain_trig_v1",
                "course_id": "ap_calculus_bc",
                "stimulus": "Let f(x) = sin(2x²). Find f'(x).",
                "options": [
                    "4x cos(2x²)",
                    "cos(2x²)",
                    "2x sin(2x²) + sin(2x²) · 4x",
                    "2x cos(2x²)",
                ],
                "answer_index": 0,
                "solution": "4x cos(2x²)",
                "tags": ["chain_rule", "trigonometry"],
                "metadata": {
                    "calculator": "No-Calc",
                    "difficulty_est": 0.58,
                },
                "origin": {
                    "created_by": "agent.parametric_generator",
                    "seed": 42,
                },
            }
        }
