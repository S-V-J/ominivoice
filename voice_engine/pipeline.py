"""
Pipecat Full-Duplex Voice Pipeline with Barge-In Support.
Orchestrates STT → LLM → TTS with real-time interruption handling.
"""
import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional, Callable, List, Dict, Any
import numpy as np

from .stt import STTEngine, TranscriptSegment, create_stt_engine
from .turn_detection import TurnDetector, TurnResult, create_turn_detector
from .tts import TTSEngine, AudioChunk, create_tts_engine

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Pipeline execution states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ENDED = "ended"


@dataclass
class TurnLog:
    """Log entry for a conversation turn."""
    turn_id: str
    role: str  # "user" or "assistant"
    text: str
    timestamp: float
    duration_ms: float
    interrupted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Configuration for the voice pipeline."""
    # STT config
    stt_engine: str = "faster-whisper"
    stt_model_size: str = "small"
    stt_device: str = "auto"
    stt_compute_type: str = "int8"
    stt_language: Optional[str] = None

    # Turn detection config
    interruption_sensitivity: str = "medium"  # high/medium/low

    # TTS config
    tts_engine: str = "kokoro"
    tts_voice: str = "af_heart"
    tts_speed: float = 1.0
    tts_device: str = "auto"

    # LLM config (passed from agent)
    llm_provider: str = "nvidia_integrate"
    llm_model: str = "stepfun-ai/step-3.7-flash"

    # Pipeline behavior
    max_call_duration_s: int = 300
    silence_timeout_s: float = 30.0
    sample_rate: int = 16000
    frame_duration_ms: int = 20

    # Barge-in behavior
    barge_in_enabled: bool = True
    truncate_on_interrupt: bool = True

    # Stack B (NVIDIA NIM) specific config
    riva_grpc_endpoint: Optional[str] = None
    chatterbox_grpc_endpoint: Optional[str] = None
    riva_use_ssl: bool = False
    chatterbox_use_ssl: bool = False
    riva_metadata: Optional[list] = None
    chatterbox_metadata: Optional[list] = None
    chatterbox_emotion_exaggeration: float = 0.5
    riva_vad_threshold: float = 0.5
    tts_language: Optional[str] = None  # For Chatterbox


class VoicePipeline:
    """
    Full-duplex voice pipeline with barge-in support.

    Architecture:
    AudioInput → VAD/TurnDetector → STT → LLM (streaming) → TTS (streaming) → AudioOutput

    Barge-in handling:
    1. VAD detects user speech during TTS playback
    2. Immediately stop TTS audio output
    3. Cancel in-flight LLM stream
    4. Truncate conversation history to what was actually spoken
    5. Start fresh STT segment for the interruption
    """

    def __init__(
        self,
        config: PipelineConfig,
        llm_provider_factory: Callable[[str, str], Any],  # Returns LLMProvider
        on_audio_output: Optional[Callable[[np.ndarray], None]] = None,
        on_transcript: Optional[Callable[[TurnLog], None]] = None,
        on_state_change: Optional[Callable[[PipelineState], None]] = None,
    ):
        """
        Initialize the voice pipeline.

        Args:
            config: Pipeline configuration
            llm_provider_factory: Factory to create LLM provider (provider_name, model) -> provider
            on_audio_output: Callback for audio output chunks (for WebRTC/telephony)
            on_transcript: Callback for completed turns (for logging)
            on_state_change: Callback for pipeline state changes
        """
        self.config = config
        self.llm_provider_factory = llm_provider_factory
        self.on_audio_output = on_audio_output
        self.on_transcript = on_transcript
        self.on_state_change = on_state_change

        # Components
        self.stt: Optional[STTEngine] = None
        self.turn_detector: Optional[TurnDetector] = None
        self.tts: Optional[TTSEngine] = None
        self.llm_provider = None

        # State
        self.state = PipelineState.IDLE
        self.call_start_time: Optional[float] = None
        self.turn_logs: List[TurnLog] = []
        self.current_turn_id: Optional[str] = None
        self.current_user_text = ""
        self.current_assistant_text = ""
        self.spoken_so_far = ""  # What has actually been played to user

        # Audio buffers
        self._audio_input_queue: asyncio.Queue = asyncio.Queue()
        self._tts_audio_queue: asyncio.Queue = asyncio.Queue()
        self._stt_text_queue: asyncio.Queue = asyncio.Queue()

        # Task handles
        self._tasks: List[asyncio.Task] = []
        self._running = False

        # Barge-in tracking
        self._tts_playing = False
        self._llm_stream_task: Optional[asyncio.Task] = None
        self._tts_stream_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize all pipeline components."""
        logger.info("Initializing voice pipeline components...")

        # STT
        self.stt = create_stt_engine(
            engine=self.config.stt_engine,
            model_size=self.config.stt_model_size,
            device=self.config.stt_device,
            compute_type=self.config.stt_compute_type,
            language=self.config.stt_language,
            streaming=True,
            # Stack B params
            voice_stack="stack_b" if self.config.stt_engine == "riva-asr" else "stack_a",
            riva_grpc_endpoint=self.config.riva_grpc_endpoint,
            riva_language=self.config.stt_language,
            riva_use_ssl=self.config.riva_use_ssl,
            riva_metadata=self.config.riva_metadata,
        )

        # Turn detector
        self.turn_detector = create_turn_detector(
            sensitivity=self.config.interruption_sensitivity,
            sample_rate=self.config.sample_rate,
            # Stack B params
            voice_stack="stack_b" if self.config.tts_engine == "chatterbox" else "stack_a",
            riva_grpc_endpoint=self.config.riva_grpc_endpoint,
            riva_vad_threshold=self.config.riva_vad_threshold,
            riva_language=self.config.stt_language,
            riva_use_ssl=self.config.riva_use_ssl,
            riva_metadata=self.config.riva_metadata,
        )

        # TTS
        self.tts = create_tts_engine(
            engine=self.config.tts_engine,
            voice=self.config.tts_voice,
            speed=self.config.tts_speed,
            device=self.config.tts_device,
            # Stack B params
            voice_stack="stack_b" if self.config.tts_engine == "chatterbox" else "stack_a",
            chatterbox_grpc_endpoint=self.config.chatterbox_grpc_endpoint,
            chatterbox_voice=self.config.tts_voice,
            chatterbox_language=self.config.tts_language,
            chatterbox_emotion_exaggeration=self.config.chatterbox_emotion_exaggeration,
            chatterbox_use_ssl=self.config.chatterbox_use_ssl,
            chatterbox_metadata=self.config.chatterbox_metadata,
        )

        # LLM provider
        self.llm_provider = self.llm_provider_factory(
            self.config.llm_provider,
            self.config.llm_model,
        )

        logger.info("Voice pipeline initialized")

    def _set_state(self, new_state: PipelineState):
        """Update pipeline state and notify callback."""
        if self.state != new_state:
            logger.debug(f"Pipeline state: {self.state.value} -> {new_state.value}")
            self.state = new_state
            if self.on_state_change:
                self.on_state_change(new_state)

    async def start_call(self, system_prompt: str):
        """Start a new call session."""
        self.call_start_time = time.time()
        self.turn_logs = []
        self.current_turn_id = None
        self.current_user_text = ""
        self.current_assistant_text = ""
        self.spoken_so_far = ""

        # Initialize conversation with system prompt
        self.conversation_history = [
            {"role": "system", "content": system_prompt}
        ]

        self._running = True
        self._set_state(PipelineState.LISTENING)

        # Start processing tasks
        self._tasks = [
            asyncio.create_task(self._audio_input_processor()),
            asyncio.create_task(self._turn_detection_processor()),
            asyncio.create_task(self._stt_processor()),
            asyncio.create_task(self._llm_processor()),
            asyncio.create_task(self._tts_processor()),
            asyncio.create_task(self._audio_output_processor()),
            asyncio.create_task(self._call_timeout_monitor()),
        ]

        logger.info("Call started")

    async def push_audio(self, audio_data: np.ndarray):
        """Push audio input from WebRTC/telephony."""
        if self._running:
            await self._audio_input_queue.put(audio_data)

    async def stop_call(self):
        """Stop the call and clean up."""
        self._running = False
        self._set_state(PipelineState.ENDED)

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Close components
        if self.stt:
            await self.stt.close()
        if self.tts:
            await self.tts.close()
        if self.llm_provider:
            await self.llm_provider.close()

        logger.info("Call ended")

    async def _audio_input_processor(self):
        """Process incoming audio frames for VAD."""
        frame_samples = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
        buffer = np.array([], dtype=np.float32)

        while self._running:
            try:
                audio_chunk = await asyncio.wait_for(
                    self._audio_input_queue.get(),
                    timeout=0.1
                )

                # Convert to float32 mono
                if audio_chunk.dtype == np.int16:
                    audio_chunk = audio_chunk.astype(np.float32) / 32768.0
                elif audio_chunk.dtype != np.float32:
                    audio_chunk = audio_chunk.astype(np.float32)

                if audio_chunk.ndim > 1:
                    audio_chunk = audio_chunk.mean(axis=1)

                buffer = np.concatenate([buffer, audio_chunk])

                # Process complete frames
                while len(buffer) >= frame_samples:
                    frame = buffer[:frame_samples]
                    buffer = buffer[frame_samples:]

                    # Process through turn detector
                    turn_result = await self.turn_detector.process_frame(frame)

                    # Handle barge-in
                    if turn_result.reason == "barge_in" and self.config.barge_in_enabled:
                        await self._handle_barge_in()

                    # Update transcript for semantic endpointing
                    self.turn_detector.update_transcript(
                        self.current_user_text,
                        is_final=False
                    )

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audio input processor error: {e}")

    async def _turn_detection_processor(self):
        """Monitor turn detection results."""
        while self._running:
            try:
                await asyncio.sleep(0.05)  # Check every 50ms

                # The turn detector is called from audio processor
                # This task monitors for turn completion via state

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Turn detection processor error: {e}")

    async def _stt_processor(self):
        """Process audio through STT."""
        # Create audio generator for STT
        async def audio_generator():
            frame_samples = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
            buffer = np.array([], dtype=np.float32)

            while self._running:
                try:
                    audio_chunk = await asyncio.wait_for(
                        self._audio_input_queue.get(),
                        timeout=0.1
                    )

                    if audio_chunk.dtype == np.int16:
                        audio_chunk = audio_chunk.astype(np.float32) / 32768.0
                    elif audio_chunk.dtype != np.float32:
                        audio_chunk = audio_chunk.astype(np.float32)

                    if audio_chunk.ndim > 1:
                        audio_chunk = audio_chunk.mean(axis=1)

                    buffer = np.concatenate([buffer, audio_chunk])

                    while len(buffer) >= frame_samples:
                        frame = buffer[:frame_samples]
                        buffer = buffer[frame_samples:]
                        yield frame

                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        try:
            async for segment in self.stt.transcribe_stream(audio_generator()):
                if segment.text.strip():
                    self.current_user_text = segment.text
                    self.turn_detector.update_transcript(segment.text, segment.is_final)

                    if segment.is_final:
                        # User finished speaking, trigger LLM
                        await self._stt_text_queue.put(segment.text)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"STT processor error: {e}")

    async def _llm_processor(self):
        """Process user text through LLM and stream to TTS."""
        while self._running:
            try:
                user_text = await asyncio.wait_for(
                    self._stt_text_queue.get(),
                    timeout=0.5
                )

                if not user_text.strip():
                    continue

                logger.info(f"User: {user_text}")

                # Log user turn
                self.current_turn_id = str(uuid.uuid4())
                turn_start = time.time()

                self._set_state(PipelineState.PROCESSING)

                # Add user message to history
                self.conversation_history.append({"role": "user", "content": user_text})

                # Stream LLM response
                self.current_assistant_text = ""
                self._tts_playing = True

                try:
                    async for token in self.llm_provider.stream_reply(
                        self.conversation_history,
                        temperature=1.0,
                        top_p=0.95,
                        max_tokens=16384,
                    ):
                        if not self._running:
                            break

                        self.current_assistant_text += token

                        # Send token to TTS queue
                        await self._tts_text_queue.put(token)

                        # Check for interruption (barge-in)
                        if not self._tts_playing:
                            logger.info("LLM stream interrupted by barge-in")
                            break

                    # Signal end of LLM stream
                    await self._tts_text_queue.put(None)

                except asyncio.CancelledError:
                    logger.info("LLM stream cancelled")
                    break
                except Exception as e:
                    logger.error(f"LLM error: {e}")
                    await self._tts_text_queue.put(None)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"LLM processor error: {e}")

    async def _tts_processor(self):
        """Process LLM tokens through TTS."""
        # Create text generator for TTS
        async def text_generator():
            while self._running:
                try:
                    token = await asyncio.wait_for(
                        self._tts_text_queue.get(),
                        timeout=0.5
                    )

                    if token is None:  # End of stream
                        break

                    yield token

                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        try:
            async for chunk in self.tts.synthesize_stream(text_generator()):
                if not self._running:
                    break

                if len(chunk.audio) > 0:
                    await self._tts_audio_queue.put(chunk.audio)

                if chunk.is_final:
                    self._tts_playing = False
                    self._set_state(PipelineState.LISTENING)

                    # Log assistant turn
                    if self.current_turn_id and self.current_assistant_text.strip():
                        turn_log = TurnLog(
                            turn_id=self.current_turn_id,
                            role="assistant",
                            text=self.current_assistant_text.strip(),
                            timestamp=time.time(),
                            duration_ms=(time.time() - turn_start) * 1000,
                            interrupted=not self.spoken_so_far == self.current_assistant_text,
                        )
                        self.turn_logs.append(turn_log)
                        if self.on_transcript:
                            self.on_transcript(turn_log)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TTS processor error: {e}")

    async def _audio_output_processor(self):
        """Send TTS audio to output callback (WebRTC/telephony)."""
        while self._running:
            try:
                audio_chunk = await asyncio.wait_for(
                    self._tts_audio_queue.get(),
                    timeout=0.1
                )

                if len(audio_chunk) > 0:
                    self._tts_playing = True
                    self._set_state(PipelineState.SPEAKING)

                    # Track what's been spoken (for truncation on interrupt)
                    # Approximate: assume constant speech rate
                    self.spoken_so_far = self.current_assistant_text

                    if self.on_audio_output:
                        # Resample if needed (TTS might be 24kHz, output 16kHz)
                        if self.tts.sample_rate != self.config.sample_rate:
                            audio_chunk = self._resample(
                                audio_chunk,
                                self.tts.sample_rate,
                                self.config.sample_rate
                            )
                        self.on_audio_output(audio_chunk)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audio output processor error: {e}")

    def _resample(self, audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Simple linear resampling (for production, use scipy.signal.resample)."""
        if from_rate == to_rate:
            return audio

        ratio = to_rate / from_rate
        new_length = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, new_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    async def _handle_barge_in(self):
        """Handle user interruption (barge-in)."""
        logger.info("Barge-in detected!")

        # 1. Stop TTS playback immediately
        self._tts_playing = False

        # 2. Clear TTS audio queue
        while not self._tts_audio_queue.empty():
            try:
                self._tts_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 3. Cancel LLM stream
        if self._llm_stream_task and not self._llm_stream_task.done():
            self._llm_stream_task.cancel()

        # 4. Truncate conversation to what was actually spoken
        if self.config.truncate_on_interrupt and self.spoken_so_far:
            # Find the last complete sentence in spoken_so_far
            truncated = self._truncate_to_spoken(self.current_assistant_text, self.spoken_so_far)
            if truncated != self.current_assistant_text:
                # Update the last assistant message in history
                if self.conversation_history and self.conversation_history[-1]["role"] == "assistant":
                    self.conversation_history[-1]["content"] = truncated
                self.current_assistant_text = truncated

        # 5. Reset turn detector for new utterance
        await self.turn_detector.reset()

        # 6. Clear STT text queue
        while not self._stt_text_queue.empty():
            try:
                self._stt_text_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 7. Clear TTS text queue
        while not self._tts_text_queue.empty():
            try:
                self._tts_text_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self._set_state(PipelineState.INTERRUPTED)
        # Will transition back to LISTENING after brief moment
        await asyncio.sleep(0.1)
        self._set_state(PipelineState.LISTENING)

    def _truncate_to_spoken(self, full_text: str, spoken_text: str) -> str:
        """Truncate full text to match what was actually spoken."""
        if not spoken_text or not full_text:
            return ""

        # Find spoken_text in full_text
        idx = full_text.find(spoken_text.strip())
        if idx >= 0:
            # Return up to end of spoken portion
            end_idx = idx + len(spoken_text.strip())
            # Find next sentence boundary
            for i in range(end_idx, len(full_text)):
                if full_text[i] in '.!?。！？':
                    return full_text[:i+1]
            return full_text[:end_idx]

        return spoken_text  # Fallback

    async def _call_timeout_monitor(self):
        """Monitor for call duration and silence timeouts."""
        last_activity = time.time()

        while self._running:
            await asyncio.sleep(1)

            # Check max call duration
            if self.call_start_time:
                elapsed = time.time() - self.call_start_time
                if elapsed >= self.config.max_call_duration_s:
                    logger.info(f"Max call duration reached ({self.config.max_call_duration_s}s)")
                    break

            # Check silence timeout (no user speech for extended period)
            if self.state == PipelineState.LISTENING:
                if time.time() - last_activity >= self.config.silence_timeout_s:
                    logger.info(f"Silence timeout reached ({self.config.silence_timeout_s}s)")
                    break
            else:
                last_activity = time.time()

        # End call
        await self.stop_call()

    def get_transcript(self) -> List[Dict[str, Any]]:
        """Get full conversation transcript as JSON-serializable list."""
        return [
            {
                "turn_id": log.turn_id,
                "role": log.role,
                "text": log.text,
                "timestamp": log.timestamp,
                "duration_ms": log.duration_ms,
                "interrupted": log.interrupted,
                "metadata": log.metadata,
            }
            for log in self.turn_logs
        ]


class PipelineFactory:
    """Factory for creating configured voice pipelines."""

    @staticmethod
    def create_from_agent(agent, llm_provider_factory) -> VoicePipeline:
        """Create pipeline from agent configuration."""

        # Get voice stack (default to STACK_A for backwards compatibility)
        voice_stack = getattr(agent, 'voice_stack', None)
        if voice_stack and hasattr(voice_stack, 'value'):
            voice_stack = voice_stack.value
        voice_stack = voice_stack or "stack_a"

        # Common config
        config = PipelineConfig(
            max_call_duration_s=agent.max_call_duration_s or 300,
            silence_timeout_s=agent.silence_timeout_s or 30.0,
            sample_rate=16000,
            frame_duration_ms=20,
            interruption_sensitivity=agent.interruption_sensitivity or "medium",
            llm_provider=agent.llm_provider or "nvidia_integrate",  # Default to NVIDIA Integrate
            llm_model=agent.llm_model or "stepfun-ai/step-3.7-flash",
        )

        if voice_stack == "stack_b":
            # Stack B: NVIDIA NIM (Riva ASR + Riva VAD + Chatterbox TTS)
            config.stt_engine = "riva-asr"
            config.tts_engine = "chatterbox"
            config.tts_voice = getattr(agent, 'chatterbox_voice', "Chatterbox-Multilingual.en-US.Female")
            config.stt_language = getattr(agent, 'riva_asr_language', "en-US")
            config.tts_language = getattr(agent, 'riva_asr_language', "en-US")

            # Stack B specific params (stored as integers 0-100 in DB)
            chatterbox_emotion = getattr(agent, 'chatterbox_emotion_exaggeration', 50)
            config.chatterbox_emotion_exaggeration = chatterbox_emotion / 100.0

            riva_vad_threshold = getattr(agent, 'riva_vad_threshold', 50)
            config.riva_vad_threshold = riva_vad_threshold / 100.0

            # gRPC endpoints (from environment or config)
            config.riva_grpc_endpoint = os.getenv("RIVA_ASR_GRPC_ENDPOINT", "voice-riva-asr:50051")
            config.chatterbox_grpc_endpoint = os.getenv("CHATTERBOX_GRPC_ENDPOINT", "voice-chatterbox:50051")
            config.riva_use_ssl = os.getenv("RIVA_ASR_USE_SSL", "false").lower() == "true"
            config.chatterbox_use_ssl = os.getenv("CHATTERBOX_USE_SSL", "false").lower() == "true"

            # Metadata for NVCF auth
            ngc_api_key = os.getenv("NGC_API_KEY")
            if ngc_api_key:
                config.riva_metadata = [("authorization", f"Bearer {ngc_api_key}")]
                config.chatterbox_metadata = [("authorization", f"Bearer {ngc_api_key}")]
                function_id = os.getenv("RIVA_ASR_FUNCTION_ID")
                if function_id:
                    config.riva_metadata.append(("function-id", function_id))
                function_id = os.getenv("CHATTERBOX_FUNCTION_ID")
                if function_id:
                    config.chatterbox_metadata.append(("function-id", function_id))
        else:
            # Stack A: Local (faster-whisper + Silero + Kokoro/Piper)
            config.stt_engine = agent.stt_engine or "faster-whisper"
            config.stt_model_size = "small"
            config.stt_device = "auto"
            config.stt_compute_type = "int8"
            config.stt_language = agent.language or None

            config.tts_engine = agent.tts_engine or "kokoro"
            config.tts_voice = agent.tts_voice or "af_heart"
            config.tts_speed = 1.0
            config.tts_device = "auto"

        return VoicePipeline(config=config, llm_provider_factory=llm_provider_factory)