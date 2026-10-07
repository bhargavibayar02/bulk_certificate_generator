"""
FastAPI Application Entrypoint.

Initializes the application, sets up the lifespan (database initialization,
storage directory creation), registers routers, and provides health check endpoints.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db
from app.routers.jobs import router as jobs_router
from app.routers.certificates import router as certificates_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Runs startup tasks (initializing DB tables, ensuring storage directories)
    and clean teardown if needed.
    """
    # 1. Initialize database tables
    init_db()

    # 2. Ensure output directory for certificates exists
    settings.CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-quality backend service for generating personalized "
        "PDF certificates in bulk with asynchronous job tracking, failure isolation, "
        "and individual certificate retrieval."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Serve the browser interface and its assets from the same application.
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Register routers
app.include_router(jobs_router)
app.include_router(certificates_router)


@app.get("/app", include_in_schema=False)
def frontend():
    """Serve the bulk certificate generator browser interface."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/", tags=["Health"])
def root(request: Request):
    """
    Serve the browser interface to browsers and retain JSON service info for API clients.
    """
    if "text/html" in request.headers.get("accept", ""):
        return FileResponse(STATIC_DIR / "index.html")
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint for monitoring service availability.
    """
    return {"status": "healthy"}
