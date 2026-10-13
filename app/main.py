import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.logger import logger
from app.config.settings import get_settings
from app.api.routes import api_router
from app.services.assistant_service import get_assistant_service

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Starting FOXSI Voice Assistant server...")
    service = get_assistant_service()
    service.startup()
    yield
    # Shutdown actions
    logger.info("Shutting down FOXSI Voice Assistant server...")
    try:
        service.stop_wakeword()
        service.engine.unload_model()
        service.tts.stop()
        service.stt.stop_recording()
    except Exception as e:
        logger.warning(f"Error during shutdown cleanup: {e}")


app = FastAPI(
    title="FOXSI Local AI Voice Assistant",
    description="Privacy-First Local Voice Assistant for Windows PC",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount Frontend static directory
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    @app.get("/index.html")
    @app.get("/dashboard")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/docs", include_in_schema=False)
    @app.get("/redoc", include_in_schema=False)
    async def redirect_to_dashboard():
        return RedirectResponse(url="/")


def run():
    settings = get_settings()
    host = settings.server.host
    port = settings.server.port
    print(f"\n=======================================================")
    print(f"  FOXSI Local AI Voice Assistant is starting up...")
    print(f"  Web Dashboard: http://{host}:{port}")
    print(f"=======================================================\n")
    uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    run()
