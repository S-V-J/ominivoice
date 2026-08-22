"""
Telephony Adapter Interface for OminiVoice.
Provides a common interface for simulated calls (FastRTC/WebRTC) and future real telephony (SIP/Twilio).
"""
import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, AsyncIterator, Any, Dict
import numpy as np

from .pipeline import VoicePipeline, PipelineConfig, PipelineFactory, PipelineState
from .prompt_builder import AgentPromptConfig, create_config_from_agent, build_system_prompt, AgentDirection

logger = logging.getLogger(__name__)


@dataclass
class CallSession:
    """Represents an active call session."""
    session_id: str
    agent_id: str
    direction: AgentDirection
    state: PipelineState = PipelineState.IDLE
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    transcript: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TelephonyAdapter(ABC):
    """Abstract base class for telephony adapters."""

    @abstractmethod
    async def start_call(
        self,
        agent_config: AgentPromptConfig,
        direction: AgentDirection,
        on_audio_output: Callable[[np.ndarray], None],
        on_transcript: Callable[[dict], None],
        on_state_change: Callable[[PipelineState], None],
        on_call_end: Callable[[CallSession], None],
    ) -> CallSession:
        """Start a new call session."""
        pass

    @abstractmethod
    async def push_audio(self, session_id: str, audio_data: np.ndarray) -> None:
        """Push audio input to the call."""
        pass

    @abstractmethod
    async def end_call(self, session_id: str) -> CallSession:
        """End a call session."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[CallSession]:
        """Get call session by ID."""
        pass


class SimulatedCallAdapter(TelephonyAdapter):
    """
    Simulated call adapter using FastRTC/WebRTC for in-browser testing.
    Uses the same VoicePipeline as real telephony would.
    """

    def __init__(
        self,
        llm_provider_factory: Callable[[str, str], Any],
        sample_rate: int = 16000,
    ):
        """
        Initialize simulated call adapter.

        Args:
            llm_provider_factory: Factory to create LLM providers
            sample_rate: Audio sample rate
        """
        self.llm_provider_factory = llm_provider_factory
        self.sample_rate = sample_rate
        self._sessions: Dict[str, CallSession] = {}
        self._pipelines: Dict[str, VoicePipeline] = {}

    async def start_call(
        self,
        agent_config: AgentPromptConfig,
        direction: AgentDirection,
        on_audio_output: Callable[[np.ndarray], None],
        on_transcript: Callable[[dict], None],
        on_state_change: Callable[[PipelineState], None],
        on_call_end: Callable[[CallSession], None],
    ) -> CallSession:
        """Start a simulated call session."""
        session_id = str(uuid.uuid4())

        # Build system prompt
        system_prompt = build_system_prompt(agent_config, direction)

        # Create pipeline config
        pipeline_config = PipelineConfig(
            stt_engine=agent_config.stt_engine,
            stt_model_size="small",
            stt_device="auto",
            stt_compute_type="int8",
            stt_language=agent_config.language,
            interruption_sensitivity=agent_config.interruption_sensitivity,
            tts_engine=agent_config.tts_engine,
            tts_voice=agent_config.tts_voice,
            tts_speed=1.0,
            tts_device="auto",
            llm_provider=agent_config.llm_provider,
            llm_model=agent_config.llm_model,
            max_call_duration_s=agent_config.max_call_duration_s,
            silence_timeout_s=agent_config.silence_timeout_s,
            sample_rate=self.sample_rate,
            frame_duration_ms=20,
            barge_in_enabled=True,
            truncate_on_interrupt=True,
        )

        # Create pipeline
        pipeline = VoicePipeline(
            config=pipeline_config,
            llm_provider_factory=self.llm_provider_factory,
            on_audio_output=on_audio_output,
            on_transcript=lambda log: on_transcript({
                "turn_id": log.turn_id,
                "role": log.role,
                "text": log.text,
                "timestamp": log.timestamp,
                "duration_ms": log.duration_ms,
                "interrupted": log.interrupted,
            }),
            on_state_change=on_state_change,
        )

        # Initialize and start
        await pipeline.initialize()
        await pipeline.start_call(system_prompt)

        # Create session
        session = CallSession(
            session_id=session_id,
            agent_id=agent_config.agent_id if hasattr(agent_config, 'agent_id') else "unknown",
            direction=direction,
            state=PipelineState.LISTENING,
            start_time=asyncio.get_event_loop().time(),
        )

        self._sessions[session_id] = session
        self._pipelines[session_id] = pipeline

        # Monitor for call end
        asyncio.create_task(self._monitor_call_end(session_id, pipeline, on_call_end))

        logger.info(f"Started simulated call session: {session_id}")
        return session

    async def _monitor_call_end(
        self,
        session_id: str,
        pipeline: VoicePipeline,
        on_call_end: Callable[[CallSession], None],
    ):
        """Monitor pipeline for completion."""
        # Wait for pipeline to end
        while pipeline.state != PipelineState.ENDED:
            await asyncio.sleep(0.5)

        session = self._sessions.get(session_id)
        if session:
            session.state = PipelineState.ENDED
            session.end_time = asyncio.get_event_loop().time()
            session.transcript = pipeline.get_transcript()
            on_call_end(session)

            # Cleanup
            del self._pipelines[session_id]

    async def push_audio(self, session_id: str, audio_data: np.ndarray) -> None:
        """Push audio to the simulated call."""
        pipeline = self._pipelines.get(session_id)
        if pipeline:
            await pipeline.push_audio(audio_data)

    async def end_call(self, session_id: str) -> CallSession:
        """End a simulated call."""
        pipeline = self._pipelines.get(session_id)
        if pipeline:
            await pipeline.stop_call()

        session = self._sessions.get(session_id)
        if session:
            session.state = PipelineState.ENDED
            session.end_time = asyncio.get_event_loop().time()
            if session_id in self._pipelines:
                session.transcript = self._pipelines[session_id].get_transcript()

        return session

    async def get_session(self, session_id: str) -> Optional[CallSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)


class BrowserSimulatedCallSession:
    """
    High-level wrapper for browser-based simulated calls.
    Handles WebRTC audio I/O via FastRTC-compatible interface.
    """

    def __init__(
        self,
        adapter: SimulatedCallAdapter,
        agent_config: AgentPromptConfig,
        direction: AgentDirection,
    ):
        self.adapter = adapter
        self.agent_config = agent_config
        self.direction = direction
        self.session: Optional[CallSession] = None
        self._audio_output_buffer: asyncio.Queue = asyncio.Queue()
        self._transcript_callbacks: list = []
        self._state_callbacks: list = []
        self._end_callbacks: list = []

    async def start(self) -> CallSession:
        """Start the simulated call."""

        def on_audio_output(audio: np.ndarray):
            # Put audio in output queue for WebRTC to consume
            try:
                self._audio_output_buffer.put_nowait(audio)
            except asyncio.QueueFull:
                pass  # Drop if buffer full

        def on_transcript(turn: dict):
            for cb in self._transcript_callbacks:
                try:
                    cb(turn)
                except Exception:
                    pass

        def on_state_change(state: PipelineState):
            for cb in self._state_callbacks:
                try:
                    cb(state)
                except Exception:
                    pass

        def on_call_end(session: CallSession):
            for cb in self._end_callbacks:
                try:
                    cb(session)
                except Exception:
                    pass

        self.session = await self.adapter.start_call(
            agent_config=self.agent_config,
            direction=self.direction,
            on_audio_output=on_audio_output,
            on_transcript=on_transcript,
            on_state_change=on_state_change,
            on_call_end=on_call_end,
        )

        return self.session

    async def push_audio(self, audio_data: np.ndarray):
        """Push microphone audio from browser."""
        if self.session:
            await self.adapter.push_audio(self.session.session_id, audio_data)

    async def get_audio_output(self) -> AsyncIterator[np.ndarray]:
        """Generator yielding audio output for browser playback."""
        while self.session and self.session.state != PipelineState.ENDED:
            try:
                audio = await asyncio.wait_for(
                    self._audio_output_buffer.get(),
                    timeout=0.1
                )
                yield audio
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def end(self) -> CallSession:
        """End the call."""
        if self.session:
            return await self.adapter.end_call(self.session.session_id)
        return None

    def on_transcript(self, callback: Callable[[dict], None]):
        """Register transcript callback."""
        self._transcript_callbacks.append(callback)

    def on_state_change(self, callback: Callable[[PipelineState], None]):
        """Register state change callback."""
        self._state_callbacks.append(callback)

    def on_call_end(self, callback: Callable[[CallSession], None]):
        """Register call end callback."""
        self._end_callbacks.append(callback)


# Future: Real telephony adapters (SIP, Twilio, etc.)
# These would implement the same TelephonyAdapter interface

class SIPTelephonyAdapter(TelephonyAdapter):
    """
    Placeholder for SIP-based telephony adapter.
    Would connect to Asterisk/FreeSWITCH/Kamailio via SIP.
    """
    def __init__(self):
        raise NotImplementedError("SIP adapter not implemented yet - use SimulatedCallAdapter for testing")


class TwilioTelephonyAdapter(TelephonyAdapter):
    """
    Placeholder for Twilio-based telephony adapter.
    Would use Twilio Media Streams for realtime audio.
    """
    def __init__(self):
        raise NotImplementedError("Twilio adapter not implemented yet - use SimulatedCallAdapter for testing")


def create_telephony_adapter(
    adapter_type: str = "simulated",
    llm_provider_factory: Optional[Callable] = None,
    **kwargs
) -> TelephonyAdapter:
    """
    Factory function to create telephony adapter.

    Args:
        adapter_type: "simulated", "sip", "twilio"
        llm_provider_factory: Required for simulated adapter
        **kwargs: Additional adapter-specific config

    Returns:
        TelephonyAdapter instance
    """
    if adapter_type == "simulated":
        if not llm_provider_factory:
            raise ValueError("llm_provider_factory required for simulated adapter")
        return SimulatedCallAdapter(llm_provider_factory, **kwargs)
    elif adapter_type == "sip":
        return SIPTelephonyAdapter()
    elif adapter_type == "twilio":
        return TwilioTelephonyAdapter()
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")