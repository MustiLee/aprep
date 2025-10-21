"""Template API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from pydantic import BaseModel

from ...agents.template_crafter import TemplateCrafter
from ...models.template import Template
from ...utils.database import TemplateDatabase
from ...core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


# Request/Response models
class TemplateCreateRequest(BaseModel):
    """Request model for creating a template."""

    task_id: str
    course_id: str
    unit_id: str
    topic_id: str
    learning_objectives: List[str]
    difficulty_target: List[float]
    calculator_policy: str
    misconceptions: List[str]


class TemplateResponse(BaseModel):
    """Response model for template."""

    template_id: str
    course_id: str
    topic_id: str
    stem: str
    params: dict
    distractor_rules: List[dict]
    created_by: str


# Dependency for template database
def get_template_db():
    """Get template database instance."""
    return TemplateDatabase()


@router.post("/", response_model=TemplateResponse, status_code=201)
async def create_template(
    request: TemplateCreateRequest,
    db: TemplateDatabase = Depends(get_template_db),
):
    """Create a new question template.

    This endpoint uses the Template Crafter agent to generate a new
    parametric question template based on learning objectives and
    misconceptions.

    Args:
        request: Template creation parameters

    Returns:
        Created template with generated parameters and distractor rules
    """
    try:
        logger.info(f"Creating template for course: {request.course_id}")

        # Use Template Crafter to create template
        crafter = TemplateCrafter()
        template_dict = crafter.create_template(request.dict())

        # Normalize data for Pydantic model
        # Ensure learning_objectives is a list
        if "learning_objectives" in template_dict and isinstance(template_dict["learning_objectives"], str):
            template_dict["learning_objectives"] = [template_dict["learning_objectives"]]

        # Ensure solution_steps are strings, not dicts
        if "solution_steps" in template_dict and template_dict["solution_steps"]:
            solution_steps = []
            for step in template_dict["solution_steps"]:
                if isinstance(step, dict):
                    # Extract step description from dict
                    solution_steps.append(step.get("step", str(step)))
                else:
                    solution_steps.append(str(step))
            template_dict["solution_steps"] = solution_steps

        # Fix params: ensure constraints is a dict, not a string
        if "params" in template_dict:
            for param_name, param_spec in template_dict["params"].items():
                if isinstance(param_spec, dict) and "constraints" in param_spec:
                    if isinstance(param_spec["constraints"], str):
                        # Convert string constraint to dict (just ignore invalid formats)
                        param_spec["constraints"] = {}

        # Convert to model and save
        template = Template(**template_dict)
        db.save(template)

        logger.info(f"Template created successfully: {template.template_id}")

        return TemplateResponse(
            template_id=template.template_id,
            course_id=template.course_id,
            topic_id=template.topic_id,
            stem=template.stem,
            params=template.params,
            distractor_rules=[r.model_dump() if hasattr(r, 'model_dump') else r for r in template.distractor_rules],
            created_by=template.created_by,
        )

    except Exception as e:
        logger.error(f"Template creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Template creation failed: {str(e)}")


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    course_id: Optional[str] = None,
    db: TemplateDatabase = Depends(get_template_db),
):
    """Get a template by ID.

    Args:
        template_id: Template identifier
        course_id: Optional course ID filter

    Returns:
        Template details
    """
    try:
        template = db.load(template_id, course_id=course_id)

        return TemplateResponse(
            template_id=template.template_id,
            course_id=template.course_id,
            topic_id=template.topic_id,
            stem=template.stem,
            params=template.params,
            distractor_rules=[r.model_dump() if hasattr(r, 'model_dump') else r for r in template.distractor_rules],
            created_by=template.created_by,
        )

    except Exception as e:
        logger.error(f"Failed to load template {template_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    topic_id: Optional[str] = Query(None, description="Filter by topic ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: TemplateDatabase = Depends(get_template_db),
):
    """List templates with optional filters.

    Args:
        course_id: Optional course ID filter
        topic_id: Optional topic ID filter
        limit: Maximum number of results (1-1000)
        offset: Offset for pagination

    Returns:
        List of templates
    """
    try:
        templates = db.list_templates(course_id=course_id)

        # Filter by topic if specified
        if topic_id:
            templates = [t for t in templates if t.topic_id == topic_id]

        # Apply pagination
        templates = templates[offset : offset + limit]

        return [
            TemplateResponse(
                template_id=t.template_id,
                course_id=t.course_id,
                topic_id=t.topic_id,
                stem=t.stem,
                params=t.params,
                distractor_rules=t.distractor_rules,
                created_by=t.created_by,
            )
            for t in templates
        ]

    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    course_id: Optional[str] = None,
    db: TemplateDatabase = Depends(get_template_db),
):
    """Delete a template.

    Args:
        template_id: Template identifier
        course_id: Optional course ID for verification

    Returns:
        No content on success
    """
    try:
        db.delete(template_id, course_id=course_id)
        logger.info(f"Template deleted: {template_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
