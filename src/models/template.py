"""Template data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TemplateParameter(BaseModel):
    """Parameter specification for template."""

    type: str = Field(..., description="Parameter type (enum, algebraic_expression, etc.)")
    values: Optional[List[Any]] = Field(None, description="Allowed values for enum type")
    weights: Optional[List[float]] = Field(None, description="Probability weights for values")
    templates: Optional[List[str]] = Field(None, description="Expression templates")
    constraints: Optional[Dict[str, List[Any]]] = Field(None, description="Constraints for variables")
    range: Optional[List[float]] = Field(None, description="Range for numeric types")


class DistractorRule(BaseModel):
    """Rule for generating distractor options."""

    rule_id: str = Field(..., description="Unique rule identifier")
    description: str = Field(..., description="Human-readable description")
    generation: str = Field(..., description="Generation formula with placeholders")
    misconception: Optional[str] = Field(None, description="Associated misconception")
    examples: Optional[List[str]] = Field(None, description="Example distractors")


class Template(BaseModel):
    """MCQ template for parametric generation."""

    template_id: str = Field(..., description="Unique template identifier")
    version: str = Field(default="1.0", description="Template version")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    created_by: str = Field(..., description="Creator identifier")

    # Metadata
    course_id: str = Field(..., description="Course identifier (e.g., ap_calculus_bc)")
    unit_id: Optional[str] = Field(None, description="Unit identifier")
    topic_id: str = Field(..., description="Topic identifier")
    learning_objectives: List[str] = Field(default_factory=list, description="Learning objectives")
    difficulty_range: List[float] = Field(default=[0.4, 0.7], description="Target difficulty range")
    calculator: str = Field(default="No-Calc", description="Calculator policy")
    estimated_time_sec: int = Field(default=90, description="Estimated time to complete")

    # Question structure
    stem: str = Field(..., description="Question stem with placeholders")
    params: Dict[str, TemplateParameter] = Field(
        default_factory=dict,
        description="Parameter specifications",
    )
    solution_template: Optional[str] = Field(None, description="Solution logic template")
    solution_steps: List[str] = Field(default_factory=list, description="Solution steps")

    # Distractors
    distractor_rules: List[DistractorRule] = Field(
        default_factory=list,
        description="Distractor generation rules",
    )

    # Metadata
    answer_format: str = Field(default="multiple_choice", description="Answer format")
    num_options: int = Field(default=4, description="Number of answer options")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    # Quality constraints
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Quality constraints")

    # Compliance
    similarity_check_required: bool = Field(default=True, description="Require similarity check")
    similarity_threshold: float = Field(default=0.80, description="Max similarity threshold")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "template_id": "calc_bc_chain_trig_v1",
                "version": "1.0",
                "created_by": "agent.template_crafter",
                "course_id": "ap_calculus_bc",
                "topic_id": "t3_chain_rule",
                "stem": "Let f(x) = {{trig_func}}({{inner_func}}). Find f'(x).",
                "params": {
                    "trig_func": {
                        "type": "enum",
                        "values": ["sin", "cos", "tan"],
                        "weights": [0.4, 0.4, 0.2],
                    }
                },
                "tags": ["chain_rule", "trigonometry"],
            }
        }
