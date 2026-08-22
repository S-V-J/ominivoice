"""
Voice Activity Detection (VAD) and Turn/Endpoint Detection.
Supports Stack A (Silero VAD local) and Stack B (Riva VAD NIM gRPC).
"""
import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Optional
import numpy as np

logger = logging.getLogger(__name__)


class VADState(Enum):
    """VAD state machine states."""
    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEECH = "speech"
    SPEECH_END = "speech_end"


@dataclass
class VADResult:
    """Result of VAD processing on an audio frame."""
    is_speech: bool
    confidence: float
    state: VADState
    timestamp: float


@dataclass
class TurnResult:
    """Result of turn/endpoint detection."""
    is_turn_end: bool
    reason: str  # "silence_timeout", "semantic_complete", "barge_in"
    partial_transcript: str = ""


class VADBase(ABC):
    """Abstract base for VAD engines."""

    @abstractmethod
    async def process_frame(self, audio_frame: np.ndarray) -> VADResult:
        """Process a single audio frame (20-30ms at 16kHz)."""
        pass

    @abstractmethod
    async def reset(self) -> None:
        """Reset VAD state."""
        pass


class SileroVAD(VADBase):
    """
    Silero VAD implementation using ONNX Runtime for fast inference.
    Classifies 20-30ms frames as speech/silence with ~1-2ms latency.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
        speech_pad_ms: int = 400,
    ):
        """
        Initialize Silero VAD.

        Args:
            threshold: Speech probability threshold (0-1)
            sample_rate: Audio sample rate (8000 or 16000)
            frame_duration_ms: Frame size in ms (20, 30, or 60 for 16kHz)
            min_speech_duration_ms: Minimum speech duration to trigger
            min_silence_duration_ms: Minimum silence to end speech
            speech_pad_ms: Padding around detected speech
        """
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms

        self._model = None
        self._initialized = False

        # State tracking
        self._state = VADState.SILENCE
        self._speech_frames = 0
        self._silence_frames = 0
        self._frame_samples = int(sample_rate * frame_duration_ms / 1000)
        self._min_speech_frames = min_speech_duration_ms // frame_duration_ms
        self._min_silence_frames = min_silence_duration_ms // frame_duration_ms

    async def _initialize(self):
        """Load Silero VAD ONNX model."""
        if self._initialized:
            return

        try:
            import onnxruntime as ort
            # Silero VAD model from torch hub, exported to ONNX
            # We'll use a local copy or download on first run
            model_path = await self._get_model_path()
            self._model = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            self._initialized = True
            logger.info("Silero VAD loaded successfully")
        except ImportError:
            logger.error("onnxruntime not installed. Install with: pip install onnxruntime")
            raise
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            raise

    async def _get_model_path(self) -> str:
        """Get path to Silero VAD ONNX model, downloading if needed."""
        import os
        import urllib.request

        model_dir = os.path.expanduser("~/.cache/silero_vad")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "silero_vad.onnx")

        if not os.path.exists(model_path):
            logger.info("Downloading Silero VAD ONNX model...")
            url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx"
            urllib.request.urlretrieve(url, model_path)
            logger.info("Silero VAD model downloaded")

        return model_path

    async def process_frame(self, audio_frame: np.ndarray) -> VADResult:
        """
        Process a single audio frame through Silero VAD.

        Args:
            audio_frame: numpy array of shape (frame_samples,) with float32 audio [-1, 1]

        Returns:
            VADResult with speech detection and state
        """
        await self._initialize()

        # Ensure correct shape and type
        if audio_frame.dtype != np.float32:
            audio_frame = audio_frame.astype(np.float32)

        # Normalize if needed
        if np.max(np.abs(audio_frame)) > 1.0:
            audio_frame = audio_frame / 32768.0

        # Ensure correct length
        if len(audio_frame) != self._frame_samples:
            # Pad or truncate
            if len(audio_frame) < self._frame_samples:
                audio_frame = np.pad(audio_frame, (0, self._frame_samples - len(audio_frame)))
            else:
                audio_frame = audio_frame[:self._frame_samples]

        # Run inference
        loop = asyncio.get_event_loop()
        speech_prob = await loop.run_in_executor(
            None,
            lambda: self._model.run(None, {"input": audio_frame.reshape(1, -1), "sr": np.array([self.sample_rate], dtype=np.int64)})[0][0][0]
        )

        is_speech = speech_prob > self.threshold

        # State machine
        prev_state = self._state

        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0

            if self._state == VADState.SILENCE:
                if self._speech_frames >= self._min_speech_frames:
                    self._state = VADState.SPEECH_START
            elif self._state == VADState.SPEECH_START:
                self._state = VADState.SPEECH
            elif self._state == VADState.SPEECH_END:
                self._state = VADState.SPEECH
        else:
            self._silence_frames += 1

            if self._state in (VADState.SPEECH, VADState.SPEECH_START):
                if self._silence_frames >= self._min_silence_frames:
                    self._state = VADState.SPEECH_END
            elif self._state == VADState.SPEECH_END:
                self._state = VADState.SILENCE
                self._speech_frames = 0

        return VADResult(
            is_speech=is_speech,
            confidence=float(speech_prob),
            state=self._state,
            timestamp=asyncio.get_event_loop().time(),
        )

    async def reset(self) -> None:
        """Reset VAD state for new utterance."""
        self._state = VADState.SILENCE
        self._speech_frames = 0
        self._silence_frames = 0


class TurnDetector:
    """
    Turn/Endpoint detector combining VAD with semantic analysis.
    Determines when user has finished speaking (not just paused).
    """

    def __init__(
        self,
        vad: VADBase,
        silence_timeout_ms: int = 600,
        semantic_check_enabled: bool = True,
        semantic_extension_ms: int = 500,
    ):
        """
        Initialize turn detector.

        Args:
            vad: VAD engine instance
            silence_timeout_ms: Silence duration to consider turn complete
            semantic_check_enabled: Check partial transcript for completeness
            semantic_extension_ms: Extra wait time if transcript looks incomplete
        """
        self.vad = vad
        self.silence_timeout_ms = silence_timeout_ms
        self.semantic_check_enabled = semantic_check_enabled
        self.semantic_extension_ms = semantic_extension_ms

        self._silence_start_time: Optional[float] = None
        self._current_transcript = ""
        self._last_final_transcript = ""

    def update_transcript(self, transcript: str, is_final: bool):
        """Update the current transcript from STT."""
        if is_final:
            self._last_final_transcript = transcript
            self._current_transcript = ""
        else:
            self._current_transcript = transcript

    def _is_semantically_complete(self, text: str) -> bool:
        """
        Heuristic: check if text looks like a complete utterance.
        Returns True if text appears complete (ends with punctuation, no trailing conjunctions).
        """
        if not text or not text.strip():
            return False

        text = text.strip()

        # Complete if ends with sentence-ending punctuation
        if text.endswith(('.', '!', '?', '。', '！', '？')):
            return True

        # Incomplete if ends with conjunction/preposition/comma
        incomplete_endings = (
            ' and', ' or', ' but', ' so', ' because', ' since', ' as', ' if',
            ' when', ' while', ' although', ' though', ' however', ' therefore',
            ' then', ' also', ' plus', ' with', ' for', ' to', ' in', ' on',
            ' at', ' by', ' from', ' up', ' down', ' out', ' over', ' under',
            ' the', ' a', ' an', ' my', ' your', ' his', ' her', ' its', ' our',
            ' their', ' this', ' that', ' these', ' those', ' what', ' which',
            ' who', ' whom', ' whose', ' how', ' why', ' where', ' when',
            ',', ';', ':',
        )

        text_lower = text.lower()
        for ending in incomplete_endings:
            if text_lower.endswith(ending):
                return False

        # If it's reasonably long and doesn't end badly, consider complete
        if len(text.split()) > 8:
            return True

        return False

    async def process_frame(self, audio_frame: np.ndarray) -> TurnResult:
        """
        Process audio frame and determine if turn has ended.

        Args:
            audio_frame: Audio frame for VAD

        Returns:
            TurnResult indicating if turn ended and why
        """
        vad_result = await self.vad.process_frame(audio_frame)

        # Check for barge-in (user started speaking while we were speaking)
        if vad_result.state == VADState.SPEECH_START:
            return TurnResult(
                is_turn_end=False,
                reason="barge_in",
                partial_transcript=self._current_transcript,
            )

        # Track silence for endpointing
        current_time = asyncio.get_event_loop().time()

        if vad_result.is_speech:
            self._silence_start_time = None
            return TurnResult(
                is_turn_end=False,
                reason="speaking",
                partial_transcript=self._current_transcript,
            )

        # In silence
        if self._silence_start_time is None:
            self._silence_start_time = current_time

        silence_duration_ms = (current_time - self._silence_start_time) * 1000

        # Check semantic completion if enabled
        if self.semantic_check_enabled and self._current_transcript:
            if self._is_semantically_complete(self._current_transcript):
                # Text looks complete, use shorter timeout
                effective_timeout = min(self.silence_timeout_ms, 300)
            else:
                # Text looks incomplete, extend wait
                effective_timeout = self.silence_timeout_ms + self.semantic_extension_ms
        else:
            effective_timeout = self.silence_timeout_ms

        if silence_duration_ms >= effective_timeout:
            # Turn complete
            self._silence_start_time = None
            full_transcript = (self._last_final_transcript + " " + self._current_transcript).strip()
            return TurnResult(
                is_turn_end=True,
                reason="silence_timeout" if not self._is_semantically_complete(self._current_transcript) else "semantic_complete",
                partial_transcript=full_transcript,
            )

        return TurnResult(
            is_turn_end=False,
            reason="silence",
            partial_transcript=self._current_transcript,
        )

    async def reset(self):
        """Reset turn detector state."""
        await self.vad.reset()
        self._silence_start_time = None
        self._current_transcript = ""
        self._last_final_transcript = ""


def create_turn_detector(
    sensitivity: str = "medium",
    sample_rate: int = 16000,
    # Stack B (Riva VAD) parameters
    voice_stack: str = "stack_a",
    riva_grpc_endpoint: Optional[str] = None,
    riva_vad_threshold: Optional[float] = None,
    riva_language: Optional[str] = None,
    riva_use_ssl: bool = False,
    riva_metadata: Optional[list] = None,
) -> TurnDetector:
    """
    Factory function to create turn detector for either stack.

    Args:
        sensitivity: "high" (350ms), "medium" (600ms), "low" (900ms) - Stack A
        sample_rate: Audio sample rate
        voice_stack: "stack_a" (local) or "stack_b" (NVIDIA NIM)
        riva_grpc_endpoint: Riva VAD gRPC endpoint (Stack B)
        riva_vad_threshold: Riva VAD threshold 0.0-1.0 (Stack B)
        riva_language: Riva VAD language code (Stack B)
        riva_use_ssl: Use SSL for Riva gRPC (Stack B)
        riva_metadata: Auth metadata for Riva (Stack B)

    Returns:
        TurnDetector instance
    """
    # Stack B: Riva VAD NIM
    if voice_stack == "stack_b":
        from .turn_detection_riva import create_riva_vad_detector
        riva_detector = create_riva_vad_detector(
            grpc_endpoint=riva_grpc_endpoint,
            vad_threshold=riva_vad_threshold,
            language_code=riva_language,
            sensitivity=sensitivity,
            sample_rate=sample_rate,
            use_ssl=riva_use_ssl,
            metadata=riva_metadata,
        )
        # Wrap Riva detector in TurnDetector interface
        return TurnDetector(
            vad=riva_detector,
            silence_timeout_ms=0,  # Riva handles its own timeout
            semantic_extension_ms=0,
            semantic_check_enabled=True,
        )

    # Stack A: Silero VAD (default)
    sensitivity_map = {
        "high": {"silence_timeout_ms": 350, "semantic_extension_ms": 300},
        "medium": {"silence_timeout_ms": 600, "semantic_extension_ms": 500},
        "low": {"silence_timeout_ms": 900, "semantic_extension_ms": 700},
    }

    params = sensitivity_map.get(sensitivity, sensitivity_map["medium"])

    vad = SileroVAD(
        sample_rate=sample_rate,
        frame_duration_ms=30,
        threshold=0.5,
    )

    return TurnDetector(
        vad=vad,
        silence_timeout_ms=params["silence_timeout_ms"],
        semantic_extension_ms=params["semantic_extension_ms"],
        semantic_check_enabled=True,
    )