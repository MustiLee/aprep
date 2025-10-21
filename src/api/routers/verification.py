"""Verification API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel

from ...agents.solution_verifier import SolutionVerifier, verify_batch
from ...utils.database import VariantDatabase
from ...core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


# Request/Response models
class VerificationRequest(BaseModel):
    """Request model for variant verification."""

    variant_id: str


class BatchVerificationRequest(BaseModel):
    """Request model for batch verification."""

    variant_ids: List[str]


class VerificationResponse(BaseModel):
    """Response model for verification result."""

    variant_id: str
    verification_status: str
    correctness: dict
    consensus: dict
    distractor_analysis: List[dict]
    performance: dict


# Dependencies
def get_variant_db():
    """Get variant database instance."""
    return VariantDatabase()


def get_verifier():
    """Get solution verifier instance."""
    return SolutionVerifier()


@router.post("/verify", response_model=VerificationResponse)
async def verify_variant(
    request: VerificationRequest,
    variant_db: VariantDatabase = Depends(get_variant_db),
    verifier: SolutionVerifier = Depends(get_verifier),
):
    """Verify a single variant's mathematical correctness.

    This endpoint uses the Solution Verifier agent to check if the
    answer is correct using multiple methods: symbolic, numerical,
    and Claude Opus reasoning.

    Args:
        request: Verification request with variant ID

    Returns:
        Verification result with status and detailed analysis
    """
    try:
        logger.info(f"Verifying variant: {request.variant_id}")

        # Load variant
        variant = variant_db.load(request.variant_id)

        # Verify (convert Pydantic model to dict)
        result = verifier.verify_variant(variant.model_dump() if hasattr(variant, 'model_dump') else variant)

        logger.info(
            f"Verification complete: {request.variant_id} - "
            f"Status: {result['verification_status']}"
        )

        return VerificationResponse(
            variant_id=result["variant_id"],
            verification_status=result["verification_status"],
            correctness=result["correctness"],
            consensus=result["consensus"],
            distractor_analysis=result["distractor_analysis"],
            performance=result["performance"],
        )

    except Exception as e:
        logger.error(f"Verification failed for {request.variant_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Verification failed: {str(e)}"
        )


@router.post("/verify/batch", response_model=dict)
async def verify_variants_batch(
    request: BatchVerificationRequest,
    variant_db: VariantDatabase = Depends(get_variant_db),
):
    """Verify multiple variants in batch.

    Args:
        request: Batch verification request with variant IDs

    Returns:
        Batch verification summary with passed/failed/needs_review counts
    """
    try:
        logger.info(f"Batch verifying {len(request.variant_ids)} variants")

        # Load variants
        variants = [variant_db.load(vid) for vid in request.variant_ids]

        # Batch verify (convert Pydantic models to dicts)
        variant_dicts = [v.model_dump() if hasattr(v, 'model_dump') else v for v in variants]
        results = verify_batch(variant_dicts)

        logger.info(
            f"Batch verification complete: "
            f"{results['summary']['passed']} passed, "
            f"{results['summary']['failed']} failed, "
            f"{results['summary']['needs_review']} need review"
        )

        return {
            "total": results["summary"]["total"],
            "passed": results["summary"]["passed"],
            "failed": results["summary"]["failed"],
            "needs_review": results["summary"]["needs_review"],
            "pass_rate": results["summary"]["pass_rate"],
        }

    except Exception as e:
        logger.error(f"Batch verification failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Batch verification failed: {str(e)}"
        )
