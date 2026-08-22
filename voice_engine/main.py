"""
Voice Engine Main Entry Point.
Provides health check and pipeline component verification.
The demo server is now mounted in the main API (backend/app/main.py).
"""
import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting OminiVoice Voice Engine")
    # Verify all components can be imported
    try:
        from voice_engine import (
            VoicePipeline,
            PipelineConfig,
            PipelineFactory,
            create_stt_engine,
            create_tts_engine,
            create_turn_detector,
        )
        logger.info("Voice Engine components verified")
    except Exception as e:
        logger.error(f"Voice Engine component verification failed: {e}")
    yield
    logger.info("Shutting down OminiVoice Voice Engine")


app = FastAPI(
    title="OminiVoice Voice Engine",
    description="Real-time voice pipeline components (STT, VAD, TTS, Pipeline)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Quick component verification
    try:
        from voice_engine import create_stt_engine, create_tts_engine, create_turn_detector
        # Try to instantiate (will fail if dependencies missing)
        stt = create_stt_engine(engine="faster-whisper", streaming=False)
        tts = create_tts_engine(engine="kokoro")
        vad = create_turn_detector(sensitivity="medium")
        return {"status": "healthy", "service": "omnivoice-voice-engine", "components": {"stt": "ok", "tts": "ok", "vad": "ok"}}
    except Exception as e:
        return {"status": "degraded", "service": "omnivoice-voice-engine", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("VOICE_ENGINE_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")