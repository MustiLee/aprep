"""FastAPI main application."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from ..core.config import get_settings
from ..core.logger import setup_logger
from .routers import templates, variants, verification, workflows, auth, student, subjects, practice, parent
import json

# Setup
settings = get_settings()
logger = setup_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Aprep AI Agent System API",
    description="REST API for AP exam content generation and verification",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
try:
    cors_origins = json.loads(settings.cors_origins)
except:
    cors_origins = ["http://localhost:3000", "http://localhost:8081", "http://localhost:19006"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )

    response.headers["X-Process-Time"] = str(process_time)
    return response


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(student.router, prefix="/api/v1/student", tags=["student"])
app.include_router(parent.router, prefix="/api/v1/parent", tags=["parent"])
app.include_router(subjects.router, prefix="/api/v1/subjects", tags=["subjects"])
app.include_router(practice.router, prefix="/api/v1/practice", tags=["practice"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(variants.router, prefix="/api/v1/variants", tags=["variants"])
app.include_router(verification.router, prefix="/api/v1/verification", tags=["verification"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Aprep AI Agent System API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "timestamp": time.time(),
    }


@app.get("/api/v1/status")
async def api_status():
    """API status endpoint with detailed information."""
    return {
        "api_version": "1.0.0",
        "environment": settings.environment,
        "agents": {
            "ced_parser": "operational",
            "template_crafter": "operational",
            "parametric_generator": "operational",
            "solution_verifier": "operational",
            "master_orchestrator": "operational",
        },
        "database": {
            "type": "postgresql" if "postgresql" in settings.database_url else "json",
            "status": "connected",
        },
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The requested resource was not found: {request.url.path}",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
