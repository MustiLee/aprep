"""Variant API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from pydantic import BaseModel

from ...agents.parametric_generator import ParametricGenerator
from ...models.variant import Variant
from ...utils.database import TemplateDatabase, VariantDatabase
from ...core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


# Request/Response models
class VariantGenerateRequest(BaseModel):
    """Request model for generating variants."""

    template_id: str
    count: int = 10
    seed_start: int = 0


class VariantResponse(BaseModel):
    """Response model for variant."""

    id: str
    template_id: str
    stimulus: str
    options: List[str]
    answer_index: int
    solution: str
    parameter_values: dict
    seed: int


# Dependencies
def get_template_db():
    """Get template database instance."""
    return TemplateDatabase()


def get_variant_db():
    """Get variant database instance."""
    return VariantDatabase()


@router.post("/generate", response_model=List[VariantResponse], status_code=201)
async def generate_variants(
    request: VariantGenerateRequest,
    template_db: TemplateDatabase = Depends(get_template_db),
    variant_db: VariantDatabase = Depends(get_variant_db),
):
    """Generate question variants from a template.

    This endpoint uses the Parametric Generator agent to create
    multiple unique question instances from a template.

    Args:
        request: Generation parameters (template_id, count, seed)

    Returns:
        List of generated variants
    """
    try:
        logger.info(
            f"Generating {request.count} variants for template: {request.template_id}"
        )

        # Load template
        template = template_db.load(request.template_id)

        # Generate variants
        generator = ParametricGenerator()
        variant_dicts = generator.generate_batch(
            template.model_dump(),
            count=request.count,
            seed_start=request.seed_start,
        )

        # Normalize and save variants
        normalized_variants = []
        for v in variant_dicts:
            # Ensure options is a list of strings without None
            if "options" in v and v["options"]:
                v["options"] = [str(opt) if opt is not None else "" for opt in v["options"]]

            # Ensure solution is a string
            if "solution" not in v or v["solution"] is None:
                v["solution"] = ""

            # Ensure required fields exist
            if "id" not in v or not v["id"]:
                # Generate ID if missing
                import hashlib
                v["id"] = f"{v['template_id']}_v{v.get('seed', 0)}_{hashlib.md5(str(v).encode()).hexdigest()[:8]}"

            # Extract parameter_values and seed from origin (for API response)
            if "origin" in v:
                origin = v["origin"]
                # Extract values but keep origin field (it's required by Variant model)
                v["parameter_values"] = origin.get("parameter_instantiation", {})
                v["seed"] = origin.get("seed", 0)
            else:
                # If origin doesn't exist, create it
                v["origin"] = {
                    "created_by": "agent.parametric_generator",
                    "created_at": datetime.now().isoformat(),
                    "seed": v.get("seed", 0),
                }
                v["parameter_values"] = {}
                v["seed"] = 0

            normalized_variants.append(v)

        variants = [Variant(**v) for v in normalized_variants]
        variant_db.save_batch(variants)

        logger.info(f"Generated and saved {len(variants)} variants")

        return [
            VariantResponse(
                id=v.id,
                template_id=v.template_id,
                stimulus=v.stimulus,
                options=v.options,
                answer_index=v.answer_index,
                solution=v.solution,
                parameter_values=v.origin.get("parameter_instantiation", {}),
                seed=v.origin.get("seed", 0),
            )
            for v in variants
        ]

    except Exception as e:
        logger.error(f"Variant generation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Variant generation failed: {str(e)}"
        )


@router.get("/{variant_id}", response_model=VariantResponse)
async def get_variant(
    variant_id: str,
    db: VariantDatabase = Depends(get_variant_db),
):
    """Get a variant by ID.

    Args:
        variant_id: Variant identifier

    Returns:
        Variant details
    """
    try:
        variant = db.load(variant_id)

        return VariantResponse(
            id=variant["id"],
            template_id=variant["template_id"],
            stimulus=variant["stimulus"],
            options=variant["options"],
            answer_index=variant["answer_index"],
            solution=variant["solution"],
            parameter_values=variant["parameter_values"],
            seed=variant["seed"],
        )

    except Exception as e:
        logger.error(f"Failed to load variant {variant_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")


@router.get("/", response_model=List[VariantResponse])
async def list_variants(
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: VariantDatabase = Depends(get_variant_db),
):
    """List variants with optional filters.

    Args:
        template_id: Optional template ID filter
        course_id: Optional course ID filter
        limit: Maximum number of results (1-1000)
        offset: Offset for pagination

    Returns:
        List of variants
    """
    try:
        variants = db.list_variants(
            template_id=template_id,
            course_id=course_id,
        )

        # Apply pagination
        variants = variants[offset : offset + limit]

        return [
            VariantResponse(
                id=v["id"],
                template_id=v["template_id"],
                stimulus=v["stimulus"],
                options=v["options"],
                answer_index=v["answer_index"],
                solution=v["solution"],
                parameter_values=v["parameter_values"],
                seed=v["seed"],
            )
            for v in variants
        ]

    except Exception as e:
        logger.error(f"Failed to list variants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list variants: {str(e)}")


@router.delete("/{variant_id}", status_code=204)
async def delete_variant(
    variant_id: str,
    db: VariantDatabase = Depends(get_variant_db),
):
    """Delete a variant.

    Args:
        variant_id: Variant identifier

    Returns:
        No content on success
    """
    try:
        db.delete(variant_id)
        logger.info(f"Variant deleted: {variant_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to delete variant {variant_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
