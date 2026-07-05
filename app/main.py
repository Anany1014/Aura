"""
FastAPI Server Entrypoint — Phase 5
====================================
Launches the FastAPI application for the Aura MVP.
Includes lifespan management to bootstrap the database and extensions on startup.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.core.database import init_db
from app.api.router import router as api_router

# Setup basic logging config for app lifecycle
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager replacing deprecated startup/shutdown events."""
    logger.info("Starting up Aura MVP...")
    try:
        await init_db()
        logger.info("Database bootstrap completed successfully.")
    except Exception as e:
        logger.exception("Database bootstrap failed on startup!")
        raise e
    yield
    logger.info("Shutting down Aura MVP...")


app = FastAPI(
    title="Aura API",
    description="Automated graph-based startup discovery engine using lateral path traversal.",
    version="1.0.0",
    lifespan=lifespan
)

# Wire up the unified API router prefixing it with /api
app.include_router(api_router)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi import HTTPException
import os

# Create static directory if not exists
os.makedirs("static", exist_ok=True)

# Expose static files but with no-cache headers so JS/CSS changes
# are always picked up by the browser without a hard refresh.
_static_dir = os.path.abspath("static")


@app.get("/static/{filename:path}", include_in_schema=False)
async def static_files(filename: str):
    """Serves static files with no-cache headers."""
    file_path = os.path.join(_static_dir, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Static file not found")
    return FileResponse(
        file_path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/", tags=["UI"])
async def root():
    """Serves the dashboard front-end UI with no-cache headers."""
    index_path = "static/index.html"
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )
    return {
        "status": "healthy",
        "service": "Aura MVP API",
        "version": "1.0.0",
        "message": "Frontend files missing. Place them in static/ directory."
    }
