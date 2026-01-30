from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.api.v1.router import api_router
from app.db.session import init_db, close_db
from app.db.redis import init_redis, close_redis
from app.core.firebase import init_firebase
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
)
import app.models  # Register models for create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await init_db()
    await init_redis()
    init_firebase()
    print(f"{settings.APP_NAME} started in {settings.ENVIRONMENT} mode")

    yield

    # Shutdown
    await close_db()
    await close_redis()
    print(f"{settings.APP_NAME} shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered Muslim matrimonial platform with compatibility scoring and safety features",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS middleware - Restricted to allowed origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin"],
    expose_headers=["X-Request-ID"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Request size limit middleware (10 MB max)
app.add_middleware(RequestSizeLimitMiddleware)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
async def health_check():
    """
    Detailed health check that actually verifies connectivity.
    Returns status of all critical services.
    """
    from app.db.session import async_session
    from app.db.redis import get_redis

    health_status = {
        "status": "healthy",
        "services": {
            "database": {"status": "unknown", "latency_ms": None},
            "redis": {"status": "unknown", "latency_ms": None},
            "firebase": {"status": "unknown"},
        },
    }

    import time

    # Check Database
    try:
        start = time.time()
        async with async_session() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        latency = round((time.time() - start) * 1000, 2)
        health_status["services"]["database"] = {
            "status": "healthy",
            "latency_ms": latency,
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)[:100],
        }
        health_status["status"] = "degraded"

    # Check Redis
    try:
        start = time.time()
        redis = get_redis()
        redis.ping()
        latency = round((time.time() - start) * 1000, 2)
        health_status["services"]["redis"] = {
            "status": "healthy",
            "latency_ms": latency,
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)[:100],
        }
        health_status["status"] = "degraded"

    # Check Firebase (just check if initialized)
    try:
        from app.core.firebase import firebase_service
        if firebase_service and firebase_service.db:
            health_status["services"]["firebase"] = {"status": "initialized"}
        else:
            health_status["services"]["firebase"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["firebase"] = {
            "status": "error",
            "error": str(e)[:100],
        }

    return health_status
