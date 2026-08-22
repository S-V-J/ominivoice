"""
FastRTC Demo Server for OminiVoice Simulated Calls.
Provides WebRTC endpoint for in-browser voice agent testing.
Also provides WebSocket endpoint for external dialer integrations.
"""
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyQuery
import numpy as np

from .telephony_adapter import (
    SimulatedCallAdapter,
    BrowserSimulatedCallSession,
    create_telephony_adapter,
)
from .prompt_builder import AgentPromptConfig, AgentDirection, create_config_from_agent
from .pipeline import PipelineState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
active_sessions: Dict[str, BrowserSimulatedCallSession] = {}
llm_provider_factory = None

# API Key authentication for WebSocket
api_key_query = APIKeyQuery(name="api_key", auto_error=False)
test_token_query = APIKeyQuery(name="token", auto_error=False)


def set_llm_provider_factory(factory):
    """Set the LLM provider factory (called from main app)."""
    global llm_provider_factory
    llm_provider_factory = factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting OminiVoice Demo Server")
    yield
    logger.info("Shutting down Demo Server")
    # Cleanup active sessions
    for session in active_sessions.values():
        try:
            await session.end()
        except Exception as e:
            logger.error(f"Error closing session: {e}")


app = FastAPI(
    title="OminiVoice Demo Server",
    description="WebRTC endpoint for simulated voice agent calls",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
@dataclass
class StartCallRequest:
    agent_id: str
    direction: str  # "inbound" or "outbound"
    voice_stack: str = "stack_a"  # "stack_a" (local) or "stack_b" (NVIDIA NIM)
    # Agent config fields (from database)
    system_prompt: str = ""
    opening_line: str = ""
    objective_prompt: str = ""
    objection_handling_prompt: str = ""
    voicemail_prompt: str = ""
    closing_prompt: str = ""
    escalation_rule: str = ""
    greeting_prompt: str = ""
    qualification_prompt: str = ""
    knowledge_prompt: str = ""
    fallback_prompt: str = ""
    handoff_prompt: str = ""
    interruption_sensitivity: str = "medium"
    max_call_duration_s: int = 300
    silence_timeout_s: float = 30.0
    language: str = "en"
    # Stack A (Local) engines
    stt_engine: str = "faster-whisper"
    tts_engine: str = "kokoro"
    tts_voice: str = "af_heart"
    # Stack B (NVIDIA NIM) engines
    chatterbox_voice: str = "Chatterbox-Multilingual.en-US.Female"
    chatterbox_emotion_exaggeration: float = 0.5
    riva_asr_language: str = "en-US"
    riva_vad_threshold: float = 0.5
    llm_provider: str = "nvidia_integrate"
    llm_model: str = "stepfun-ai/step-3.7-flash"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "omnivoice-demo"}


@app.post("/start-call")
async def start_demo_call(request: StartCallRequest):
    """
    Start a simulated call session.
    Returns session ID and WebSocket URL for audio streaming.
    """
    if not llm_provider_factory:
        raise HTTPException(status_code=503, detail="LLM provider factory not configured")

    # Determine engine config based on voice_stack
    if request.voice_stack == "stack_b":
        stt_engine = "riva-asr"
        tts_engine = "chatterbox"
        tts_voice = request.chatterbox_voice
        stt_language = request.riva_asr_language
    else:
        stt_engine = request.stt_engine
        tts_engine = request.tts_engine
        tts_voice = request.tts_voice
        stt_language = request.language

    # Build agent config
    agent_config = AgentPromptConfig(
        agent_id=request.agent_id,
        system_prompt=request.system_prompt,
        opening_line=request.opening_line,
        objective_prompt=request.objective_prompt,
        objection_handling_prompt=request.objection_handling_prompt,
        voicemail_prompt=request.voicemail_prompt,
        closing_prompt=request.closing_prompt,
        escalation_rule=request.escalation_rule,
        greeting_prompt=request.greeting_prompt,
        qualification_prompt=request.qualification_prompt,
        knowledge_prompt=request.knowledge_prompt,
        fallback_prompt=request.fallback_prompt,
        handoff_prompt=request.handoff_prompt,
        interruption_sensitivity=request.interruption_sensitivity,
        max_call_duration_s=request.max_call_duration_s,
        silence_timeout_s=request.silence_timeout_s,
        language=stt_language,
        stt_engine=stt_engine,
        tts_engine=tts_engine,
        tts_voice=tts_voice,
        llm_provider=request.llm_provider,
        llm_model=request.llm_model,
        # Stack B specific
        chatterbox_voice=request.chatterbox_voice,
        chatterbox_emotion_exaggeration=request.chatterbox_emotion_exaggeration,
        riva_asr_language=request.riva_asr_language,
        riva_vad_threshold=request.riva_vad_threshold,
    )

    direction = AgentDirection(request.direction)

    # Create telephony adapter
    adapter = create_telephony_adapter(
        "simulated",
        llm_provider_factory=llm_provider_factory,
        sample_rate=16000,
    )

    # Create browser session
    session = BrowserSimulatedCallSession(adapter, agent_config, direction)

    # Start call
    call_session = await session.start()

    # Store session
    active_sessions[call_session.session_id] = session

    # Return session info with WebSocket URL
    # Since demo server is mounted at /demo, the WS path is /demo/ws/audio/...
    ws_url = f"/demo/ws/audio/{call_session.session_id}"

    return {
        "session_id": call_session.session_id,
        "ws_url": ws_url,
        "agent_id": request.agent_id,
        "direction": request.direction,
        "status": "started",
    }


@app.websocket("/ws/audio/{session_id}")
async def websocket_audio_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for realtime audio streaming.

    Protocol:
    - Client sends: binary audio frames (int16, 16kHz, mono, 20ms frames)
    - Server sends: binary audio frames (int16, 16kHz, mono)
    - Control messages as JSON text frames:
      - {"type": "transcript", "data": {...}}
      - {"type": "state", "data": "listening|speaking|..."}
      - {"type": "end", "data": {...}}
    """
    await websocket.accept()

    session = active_sessions.get(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    logger.info(f"WebSocket connected for session: {session_id}")

    # Track connection state
    connected = True
    audio_output_task = None

    async def send_audio_output():
        """Send TTS audio to WebSocket."""
        nonlocal connected
        try:
            async for audio_chunk in session.get_audio_output():
                if not connected:
                    break
                # Convert float32 [-1,1] to int16 bytes
                audio_int16 = (audio_chunk * 32767).astype(np.int16)
                await websocket.send_bytes(audio_int16.tobytes())
        except Exception as e:
            logger.error(f"Audio output error: {e}")
        finally:
            connected = False

    # Start audio output task
    audio_output_task = asyncio.create_task(send_audio_output())

    # Register callbacks
    def on_transcript(turn: dict):
        if connected:
            asyncio.create_task(websocket.send_json({
                "type": "transcript",
                "data": turn,
            }))

    def on_state_change(state: PipelineState):
        if connected:
            asyncio.create_task(websocket.send_json({
                "type": "state",
                "data": state.value,
            }))

    def on_call_end(call_session):
        if connected:
            asyncio.create_task(websocket.send_json({
                "type": "end",
                "data": {
                    "session_id": call_session.session_id,
                    "transcript": call_session.transcript,
                    "duration": call_session.end_time - call_session.start_time if call_session.end_time and call_session.start_time else 0,
                },
            }))

    session.on_transcript(on_transcript)
    session.on_state_change(on_state_change)
    session.on_call_end(on_call_end)

    try:
        while connected:
            # Receive audio from client
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

            if "bytes" in message:
                # Binary audio frame from browser
                audio_bytes = message["bytes"]
                # Convert int16 bytes to float32 numpy array
                audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                await session.push_audio(audio_float32)

            elif "text" in message:
                # Control message from client
                try:
                    import json
                    control = json.loads(message["text"])
                    if control.get("type") == "end":
                        await session.end()
                        break
                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected = False
        if audio_output_task:
            audio_output_task.cancel()
            try:
                await audio_output_task
            except asyncio.CancelledError:
                pass
        # Cleanup session
        if session_id in active_sessions:
            await active_sessions[session_id].end()
            del active_sessions[session_id]


@app.post("/end-call/{session_id}")
async def end_demo_call(session_id: str):
    """End a demo call session."""
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    call_session = await session.end()
    del active_sessions[session_id]

    return {
        "session_id": call_session.session_id,
        "status": "ended",
        "transcript": call_session.transcript,
        "duration": call_session.end_time - call_session.start_time if call_session.end_time and call_session.start_time else 0,
    }


@app.get("/sessions")
async def list_sessions():
    """List active demo sessions."""
    return {
        "sessions": [
            {
                "session_id": s.session.session_id,
                "agent_id": s.session.agent_id,
                "direction": s.session.direction.value,
                "state": s.session.state.value,
                "start_time": s.session.start_time,
            }
            for s in active_sessions.values()
        ]
    }


# =============================================================================
# Universal Voice Agent WebSocket Endpoint
# For integration with: Websites, Asterisk, FreeSWITCH, OpenSIPS, Twilio, etc.
# All configuration passed at connection time - no portal setup required
# =============================================================================

async def validate_api_key(api_key: str) -> Optional[dict]:
    """
    Validate API key and return account info.
    In production, this queries the database via the main API.
    Returns dict with account_id, rate_limit, etc. or None if invalid.
    """
    if api_key.startswith("ov_live_") and len(api_key) == 40:
        # In production: query DB to validate key_hash and get account_id
        # For now, accept any valid format key
        return {"account_id": "validated", "rate_limit": 60}
    return None


async def validate_test_token(token: str) -> Optional[dict]:
    """
    Validate JWT test token.
    """
    try:
        from jose import jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") == "websocket_test":
            return {"account_id": payload.get("account_id", "test"), "agent_id": payload.get("agent_id")}
    except Exception:
        pass
    return None


def build_agent_config_from_message(config: dict, auth_info: dict) -> AgentPromptConfig:
    """
    Build AgentPromptConfig from WebSocket config message.
    All configuration comes from the external system - no portal storage needed.
    """
    # Voice stack selection
    voice_stack = config.get("voice_stack", "stack_a")

    if voice_stack == "stack_b":
        stt_engine = config.get("stt_engine", "riva-asr")
        tts_engine = config.get("tts_engine", "chatterbox")
        tts_voice = config.get("tts_voice", "Chatterbox-Multilingual.en-US.Female")
        stt_language = config.get("language", "en-US")
    else:
        stt_engine = config.get("stt_engine", "faster-whisper")
        tts_engine = config.get("tts_engine", "kokoro")
        tts_voice = config.get("tts_voice", "af_heart")
        stt_language = config.get("language", "en-US")

    # Build config - ALL fields from external system
    return AgentPromptConfig(
        agent_id=config.get("agent_id", f"ext_{auth_info.get('account_id', 'unknown')}"),
        system_prompt=config.get("system_prompt", "You are a helpful AI assistant."),
        # Direction-specific prompts (both sets accepted, uses direction to pick)
        opening_line=config.get("opening_line", ""),
        objective_prompt=config.get("objective_prompt", ""),
        objection_handling_prompt=config.get("objection_handling_prompt", ""),
        voicemail_prompt=config.get("voicemail_prompt", ""),
        closing_prompt=config.get("closing_prompt", ""),
        escalation_rule=config.get("escalation_rule", ""),
        greeting_prompt=config.get("greeting_prompt", ""),
        qualification_prompt=config.get("qualification_prompt", ""),
        knowledge_prompt=config.get("knowledge_prompt", ""),
        fallback_prompt=config.get("fallback_prompt", ""),
        handoff_prompt=config.get("handoff_prompt", ""),
        # Shared settings
        interruption_sensitivity=config.get("interruption_sensitivity", "medium"),
        max_call_duration_s=config.get("max_call_duration_s", 300),
        silence_timeout_s=config.get("silence_timeout_s", 10.0),
        language=stt_language,
        stt_engine=stt_engine,
        tts_engine=tts_engine,
        tts_voice=tts_voice,
        llm_provider=config.get("llm_provider", "nvidia_integrate"),
        llm_model=config.get("llm_model", "stepfun-ai/step-3.7-flash"),
        # Stack B specific
        chatterbox_voice=config.get("chatterbox_voice", "Chatterbox-Multilingual.en-US.Female"),
        chatterbox_emotion_exaggeration=config.get("chatterbox_emotion_exaggeration", 0.5),
        riva_asr_language=config.get("riva_asr_language", "en-US"),
        riva_vad_threshold=config.get("riva_vad_threshold", 0.5),
    )


@app.websocket("/ws")
async def websocket_universal_agent(
    websocket: WebSocket,
    api_key: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
):
    """
    UNIVERSAL VOICE AGENT WEBSOCKET ENDPOINT

    Connect any telephony system: Asterisk, FreeSWITCH, OpenSIPS, Twilio, custom SIP, WebRTC.

    Authentication (one required):
    - ?api_key=ov_live_<32chars> (account API key)
    - ?token=<jwt_test_token> (1-hour test token)

    Protocol:
    - Audio: Binary frames, int16, 16kHz, mono, 20ms (320 samples = 640 bytes)
    - Control: JSON text frames

    Message Flow:
    1. CONNECT → Server sends: {"type": "ready", "data": {"session_id": "...", "protocol_version": "1.0"}}
    2. CLIENT → Server: {"type": "config", "data": {FULL_AGENT_CONFIG}} (REQUIRED)
    3. SERVER → Client: {"type": "started", "data": {"session_id": "...", "capabilities": [...]}}
    4. EXCHANGE: Binary audio + JSON control messages
    5. EITHER SIDE → {"type": "end"} → Server: {"type": "ended", "data": {...}}

    Config Fields (all passed at connection time - NO PORTAL SETUP NEEDED):
    {
        "agent_id": "your-internal-id",           # Optional: for your tracking
        "direction": "outbound|inbound",          # Required: call direction
        "system_prompt": "...",                    # Required: agent persona
        "voice_stack": "stack_a|stack_b",         # Optional: default "stack_a"
        "opening_line": "...",                     # Outbound: first words
        "greeting_prompt": "...",                  # Inbound: greeting
        "objective_prompt": "...",                 # Outbound: goal
        "qualification_prompt": "...",             # Inbound: qualify caller
        "knowledge_prompt": "...",                 # Knowledge base
        "objection_handling_prompt": "...",        # Handle objections
        "fallback_prompt": "...",                  # When unsure
        "voicemail_prompt": "...",                 # Voicemail message
        "closing_prompt": "...",                   # Call closing
        "escalation_rule": "...",                  # Transfer trigger
        "handoff_prompt": "...",                   # Human handoff
        "interruption_sensitivity": "low|medium|high",
        "max_call_duration_s": 300,
        "silence_timeout_s": 10,
        "language": "en-US",
        "stt_engine": "faster-whisper|riva-asr",
        "tts_engine": "kokoro|piper|chatterbox",
        "tts_voice": "af_heart|...",
        "llm_provider": "nvidia_integrate",
        "llm_model": "stepfun-ai/step-3.7-flash",
        "chatterbox_voice": "...",
        "chatterbox_emotion_exaggeration": 0.5,
        "riva_asr_language": "en-US",
        "riva_vad_threshold": 0.5,
        "metadata": {...}                          # Your custom data
    }
    """
    # Authenticate
    auth_info = None
    auth_method = None

    if token:
        auth_info = await validate_test_token(token)
        auth_method = "test_token"
        if not auth_info:
            await websocket.close(code=4001, reason="Invalid or expired test token")
            return
        logger.info(f"Universal agent WS connected via test token: {auth_info}")

    elif api_key:
        auth_info = await validate_api_key(api_key)
        auth_method = "api_key"
        if not auth_info:
            await websocket.close(code=4001, reason="Invalid API key")
            return
        logger.info(f"Universal agent WS connected via API key: {auth_info}")

    else:
        await websocket.close(code=4001, reason="Auth required: ?api_key=... or ?token=...")
        return

    # Connection state
    connected = True
    audio_output_task = None
    session = None
    adapter = None
    session_id = str(uuid.uuid4())
    call_started = False

    async def send_audio_output():
        """Stream TTS audio to client."""
        nonlocal connected, session
        try:
            if session:
                async for audio_chunk in session.get_audio_output():
                    if not connected:
                        break
                    audio_int16 = (audio_chunk * 32767).astype(np.int16)
                    await websocket.send_bytes(audio_int16.tobytes())
        except Exception as e:
            logger.error(f"Audio output error: {e}")
        finally:
            connected = False

    await websocket.accept()

    # Send ready message immediately
    await websocket.send_json({
        "type": "ready",
        "data": {
            "session_id": session_id,
            "protocol_version": "1.0",
            "auth_method": auth_method,
            "server_time": datetime.utcnow().isoformat() + "Z",
            "supported_stacks": ["stack_a", "stack_b"],
            "audio_format": {
                "sample_rate": 16000,
                "channels": 1,
                "encoding": "int16",
                "frame_ms": 20
            }
        }
    })

    try:
        while connected:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

            if "bytes" in message:
                # Binary audio from telephony system
                if session and call_started:
                    audio_bytes = message["bytes"]
                    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0
                    await session.push_audio(audio_float32)

            elif "text" in message:
                try:
                    import json
                    control = json.loads(message["text"])
                    msg_type = control.get("type")

                    if msg_type == "config":
                        if call_started:
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": "Call already started, cannot reconfigure"}
                            })
                            continue

                        config = control.get("data", {})

                        # Validate required fields
                        required = ["direction", "system_prompt"]
                        missing = [f for f in required if not config.get(f)]
                        if missing:
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": f"Missing required config fields: {missing}"}
                            })
                            continue

                        if not llm_provider_factory:
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": "LLM provider not configured on server"}
                            })
                            continue

                        # Build agent config from external system's message
                        agent_config = build_agent_config_from_message(config, auth_info)
                        direction = AgentDirection(config.get("direction", "outbound"))

                        # Create telephony adapter
                        adapter = create_telephony_adapter(
                            "simulated",
                            llm_provider_factory=llm_provider_factory,
                            sample_rate=16000,
                        )

                        # Create session
                        session = BrowserSimulatedCallSession(adapter, agent_config, direction)

                        # Start call
                        call_session = await session.start()
                        call_started = True

                        # Store session
                        active_sessions[call_session.session_id] = session

                        # Start audio output streaming
                        audio_output_task = asyncio.create_task(send_audio_output())

                        # Register event callbacks
                        def on_transcript(turn: dict):
                            if connected:
                                asyncio.create_task(websocket.send_json({
                                    "type": "transcript",
                                    "data": turn,
                                }))

                        def on_state_change(state: PipelineState):
                            if connected:
                                asyncio.create_task(websocket.send_json({
                                    "type": "state",
                                    "data": state.value,
                                }))

                        def on_call_end(call_session):
                            if connected:
                                asyncio.create_task(websocket.send_json({
                                    "type": "ended",
                                    "data": {
                                        "session_id": call_session.session_id,
                                        "transcript": call_session.transcript,
                                        "duration_seconds": call_session.end_time - call_session.start_time if call_session.end_time and call_session.start_time else 0,
                                        "ended_at": datetime.utcnow().isoformat() + "Z"
                                    },
                                }))

                        session.on_transcript(on_transcript)
                        session.on_state_change(on_state_change)
                        session.on_call_end(on_call_end)

                        # Confirm started with capabilities
                        await websocket.send_json({
                            "type": "started",
                            "data": {
                                "session_id": call_session.session_id,
                                "agent_id": agent_config.agent_id,
                                "direction": direction.value,
                                "capabilities": ["barge_in", "streaming_stt", "streaming_tts", "interruption_detection"],
                                "stack": agent_config.stt_engine,
                                "started_at": datetime.utcnow().isoformat() + "Z"
                            }
                        })

                    elif msg_type == "end":
                        if session:
                            await session.end()
                        break

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong", "data": {"timestamp": datetime.utcnow().isoformat() + "Z"}})

                    elif msg_type == "dtmf":
                        # Handle DTMF from SIP systems
                        digit = control.get("data", {}).get("digit")
                        if digit and session:
                            # Inject DTMF as special transcript or handle separately
                            await websocket.send_json({
                                "type": "dtmf_received",
                                "data": {"digit": digit}
                            })

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Control message error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": str(e), "code": "CONTROL_ERROR"}
                    })

    except WebSocketDisconnect:
        logger.info(f"Universal agent WS disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Universal agent WS error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e), "code": "SERVER_ERROR"}
            })
        except:
            pass
    finally:
        connected = False
        if audio_output_task:
            audio_output_task.cancel()
            try:
                await audio_output_task
            except asyncio.CancelledError:
                pass
        if session and session.session:
            sid = session.session.session_id
            if sid in active_sessions:
                await active_sessions[sid].end()
                del active_sessions[sid]


# Demo HTML page for testing
DEMO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OminiVoice - Simulated Call Demo</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .container { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { color: #1a1a1a; margin-top: 0; }
        .form-group { margin-bottom: 16px; }
        label { display: block; margin-bottom: 6px; font-weight: 500; color: #333; }
        input, select, textarea { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        textarea { min-height: 100px; resize: vertical; font-family: monospace; }
        button { padding: 12px 24px; border: none; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn-primary { background: #2563eb; color: white; }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-primary:disabled { background: #93c5fd; cursor: not-allowed; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-danger:hover { background: #b91c1c; }
        .status { padding: 12px; border-radius: 6px; margin: 16px 0; font-weight: 500; }
        .status.connecting { background: #fef3c7; color: #92400e; }
        .status.active { background: #dcfce7; color: #166534; }
        .status.ended { background: #fee2e2; color: #991b1b; }
        .transcript { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 13px; line-height: 1.6; }
        .transcript .turn { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0; }
        .transcript .turn:last-child { border-bottom: none; }
        .transcript .role { font-weight: 600; color: #2563eb; }
        .transcript .role.assistant { color: #059669; }
        .transcript .interrupted { color: #dc2626; font-size: 11px; }
        .audio-meter { height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin: 16px 0; }
        .audio-meter .level { height: 100%; background: #2563eb; width: 0%; transition: width 0.1s; }
        .config-section { background: #f8fafc; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
        .config-section h3 { margin-top: 0; color: #374151; }
        .row { display: flex; gap: 16px; }
        .row > * { flex: 1; }
        @media (max-width: 600px) { .row { flex-direction: column; gap: 0; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ OminiVoice Simulated Call Demo</h1>
        <p style="color: #6b7280;">Test your voice agent in the browser using WebRTC. No phone numbers needed.</p>

        <div class="config-section">
            <h3>Agent Configuration</h3>
            <div class="row">
                <div class="form-group">
                    <label>Agent ID</label>
                    <input type="text" id="agentId" value="demo-agent-1" placeholder="Enter agent ID">
                </div>
                <div class="form-group">
                    <label>Direction</label>
                    <select id="direction">
                        <option value="outbound">Outbound (Call Out)</option>
                        <option value="inbound">Inbound (Call In)</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label>System Prompt (Persona)</label>
                <textarea id="systemPrompt" placeholder="You are Sarah, a friendly sales representative...">You are Sarah, a friendly sales representative for Acme Corp. You're professional but warm. Keep responses short and conversational.</textarea>
            </div>
            <div class="row">
                <div class="form-group">
                    <label>Opening Line (Outbound)</label>
                    <textarea id="openingLine" placeholder="Hi, this is Sarah from Acme Corp...">Hi, this is Sarah from Acme Corp. I'm calling because we have a special offer on our new product line that I think you'd be interested in. Do you have a moment?</textarea>
                </div>
                <div class="form-group">
                    <label>Greeting (Inbound)</label>
                    <textarea id="greetingPrompt" placeholder="Thank you for calling Acme Corp...">Thank you for calling Acme Corp! This is Sarah. How can I help you today?</textarea>
                </div>
            </div>
            <div class="form-group">
                <label>Objective / Qualification</label>
                <textarea id="objectivePrompt" placeholder="Schedule a 15-minute demo...">Schedule a 15-minute demo call with the decision maker. Qualify their interest and availability.</textarea>
            </div>
            <div class="form-group">
                <label>LLM Provider</label>
                <select id="llmProvider">
                    <option value="ollama_local">Ollama (Local)</option>
                    <option value="nvidia_integrate">NVIDIA Integrate API</option>
                </select>
            </div>
            <div class="form-group">
                <label>LLM Model</label>
                <input type="text" id="llmModel" value="qwen3:4b" placeholder="Model name">
            </div>
        </div>

        <div>
            <button class="btn-primary" id="startBtn" onclick="startCall()">Start Test Call</button>
            <button class="btn-danger" id="endBtn" onclick="endCall()" disabled>End Call</button>
        </div>

        <div id="status" class="status" style="display: none;"></div>

        <div class="audio-meter">
            <div class="level" id="audioLevel"></div>
        </div>
        <p id="audioStatus" style="color: #6b7280; font-size: 14px;">Microphone: Not connected</p>

        <h3>Live Transcript</h3>
        <div id="transcript" class="transcript">Click "Start Test Call" to begin...</div>
    </div>

    <script>
        let ws = null;
        let audioContext = null;
        let mediaStream = null;
        let processor = null;
        let sessionId = null;
        let isRecording = false;

        const startBtn = document.getElementById('startBtn');
        const endBtn = document.getElementById('endBtn');
        const statusDiv = document.getElementById('status');
        const transcriptDiv = document.getElementById('transcript');
        const audioLevel = document.getElementById('audioLevel');
        const audioStatus = document.getElementById('audioStatus');

        function setStatus(text, className) {
            statusDiv.textContent = text;
            statusDiv.className = 'status ' + className;
            statusDiv.style.display = 'block';
        }

        function addTranscript(turn) {
            const div = document.createElement('div');
            div.className = 'turn';
            const roleClass = turn.role === 'assistant' ? 'assistant' : '';
            const interrupted = turn.interrupted ? ' <span class="interrupted">[INTERRUPTED]</span>' : '';
            div.innerHTML = `<span class="role ${roleClass}">${turn.role.toUpperCase()}</span>: ${turn.text}${interrupted}`;
            transcriptDiv.appendChild(div);
            transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
        }

        async function startCall() {
            const agentId = document.getElementById('agentId').value;
            const direction = document.getElementById('direction').value;
            const systemPrompt = document.getElementById('systemPrompt').value;
            const openingLine = document.getElementById('openingLine').value;
            const greetingPrompt = document.getElementById('greetingPrompt').value;
            const objectivePrompt = document.getElementById('objectivePrompt').value;
            const llmProvider = document.getElementById('llmProvider').value;
            const llmModel = document.getElementById('llmModel').value;

            if (!agentId) {
                alert('Please enter an Agent ID');
                return;
            }

            setStatus('Starting call...', 'connecting');
            startBtn.disabled = true;

            try {
                // Get microphone access
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioStatus.textContent = 'Microphone: Connected ✓';

                // Setup audio processing
                audioContext = new AudioContext({ sampleRate: 16000 });
                const source = audioContext.createMediaStreamSource(mediaStream);
                processor = audioContext.createScriptProcessor(4096, 1, 1);

                processor.onaudioprocess = (e) => {
                    if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
                    const inputData = e.inputBuffer.getChannelData(0);
                    // Convert float32 to int16
                    const int16 = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        const s = Math.max(-1, Math.min(1, inputData[i]));
                        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }
                    // Update visual meter
                    let sum = 0;
                    for (let i = 0; i < inputData.length; i++) sum += inputData[i] * inputData[i];
                    const rms = Math.sqrt(sum / inputData.length);
                    audioLevel.style.width = Math.min(100, rms * 200) + '%';
                    // Send audio
                    ws.send(int16.buffer);
                };

                source.connect(processor);
                processor.connect(audioContext.destination);

                // Start call via API
                const response = await fetch('/api/start-call', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        agent_id: agentId,
                        direction: direction,
                        system_prompt: systemPrompt,
                        opening_line: openingLine,
                        greeting_prompt: greetingPrompt,
                        objective_prompt: objectivePrompt,
                        llm_provider: llmProvider,
                        llm_model: llmModel,
                    })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Failed to start call');

                sessionId = data.session_id;
                const wsUrl = `ws://${window.location.host}${data.ws_url}`;

                // Connect WebSocket for audio
                ws = new WebSocket(wsUrl);
                ws.binaryType = 'arraybuffer';

                ws.onopen = () => {
                    console.log('WebSocket connected');
                    isRecording = true;
                    setStatus('Call active - Speak now!', 'active');
                    endBtn.disabled = false;
                    transcriptDiv.innerHTML = '';
                };

                ws.onmessage = (event) => {
                    if (event.data instanceof ArrayBuffer) {
                        // Incoming audio from TTS - play it
                        playAudio(event.data);
                    } else {
                        // Control message
                        const msg = JSON.parse(event.data);
                        handleControlMessage(msg);
                    }
                };

                ws.onclose = () => {
                    console.log('WebSocket closed');
                    cleanup();
                };

                ws.onerror = (err) => {
                    console.error('WebSocket error:', err);
                    setStatus('Connection error', 'ended');
                };

            } catch (err) {
                console.error('Start call error:', err);
                setStatus('Error: ' + err.message, 'ended');
                startBtn.disabled = false;
                cleanup();
            }
        }

        let audioQueue = [];
        let isPlaying = false;
        let playbackContext = null;

        function playAudio(arrayBuffer) {
            audioQueue.push(arrayBuffer);
            if (!isPlaying) playNext();
        }

        async function playNext() {
            if (audioQueue.length === 0) {
                isPlaying = false;
                return;
            }
            isPlaying = true;
            const buffer = audioQueue.shift();

            if (!playbackContext) {
                playbackContext = new AudioContext({ sampleRate: 16000 });
            }

            // Decode int16 to float32
            const int16 = new Int16Array(buffer);
            const float32 = new Float32Array(int16.length);
            for (let i = 0; i < int16.length; i++) {
                float32[i] = int16[i] / 32768.0;
            }

            const audioBuffer = playbackContext.createBuffer(1, float32.length, 16000);
            audioBuffer.copyToChannel(float32, 0);

            const source = playbackContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(playbackContext.destination);
            source.onended = () => playNext();
            source.start();
        }

        function handleControlMessage(msg) {
            switch (msg.type) {
                case 'transcript':
                    addTranscript(msg.data);
                    break;
                case 'state':
                    console.log('State:', msg.data);
                    break;
                case 'end':
                    setStatus('Call ended', 'ended');
                    addTranscript({ role: 'system', text: `Call ended. Duration: ${msg.data.duration.toFixed(1)}s`, interrupted: false });
                    cleanup();
                    break;
            }
        }

        async function endCall() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'end' }));
                ws.close();
            }
            cleanup();
        }

        function cleanup() {
            isRecording = false;
            startBtn.disabled = false;
            endBtn.disabled = true;
            audioStatus.textContent = 'Microphone: Disconnected';
            audioLevel.style.width = '0%';

            if (processor) {
                processor.disconnect();
                processor = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
            if (playbackContext) {
                playbackContext.close();
                playbackContext = null;
            }
            if (mediaStream) {
                mediaStream.getTracks().forEach(t => t.stop());
                mediaStream = null;
            }
            ws = null;
            sessionId = null;
        }
    </script>
</body>
</html>
"""


@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Serve the demo page."""
    return DEMO_HTML


@app.get("/")
async def root():
    """Root endpoint redirects to demo."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/demo")


def create_demo_app(llm_factory):
    """Create demo app with LLM provider factory."""
    set_llm_provider_factory(llm_factory)
    return app


if __name__ == "__main__":
    import uvicorn

    # For standalone testing with dummy LLM
    class DummyLLMProvider:
        async def stream_reply(self, messages, **kwargs):
            yield "Hello! This is a test response from the dummy LLM provider. "
            yield "In a real deployment, this would connect to your configured LLM. "
            yield "The voice agent is working correctly!"

        async def close(self):
            pass

    def dummy_factory(provider_name, model):
        return DummyLLMProvider()

    set_llm_provider_factory(dummy_factory)

    uvicorn.run(app, host="0.0.0.0", port=8000)