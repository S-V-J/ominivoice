"""
OminiVoice FastAPI Application Entry Point.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from jose import JWTError

from app.core.config import settings
from app.core.database import init_db, close_db, check_db_connection
from app.core.logging import setup_logging
from app.api.routers import auth, agents, api_keys
from app.core.celery_app import celery_app
from app.services.llm_service import close_all_providers

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler - startup and shutdown."""
    # Startup
    logger.info("Starting OminiVoice API...")
    await init_db()
    logger.info("Database initialized")

    # Check database connection
    db_healthy = await check_db_connection()
    if not db_healthy:
        logger.error("Database connection check failed!")
    else:
        logger.info("Database connection healthy")

    yield

    # Shutdown
    logger.info("Shutting down OminiVoice API...")
    await close_all_providers()
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="OminiVoice API",
    description="Multi-tenant SaaS platform for configuring and testing AI voice agents",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Upgrade-Required"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors (unique constraints, etc.)."""
    logger.warning(f"Integrity error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Resource already exists or constraint violation"},
    )


@app.exception_handler(JWTError)
async def jwt_error_handler(request: Request, exc: JWTError):
    """Handle JWT errors."""
    logger.warning(f"JWT error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid or expired token"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    db_healthy = await check_db_connection()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": "0.1.0",
        "services": {
            "database": "healthy" if db_healthy else "unhealthy",
        },
    }


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(api_keys.router, prefix="/api", tags=["API Keys"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT != "production",
    )