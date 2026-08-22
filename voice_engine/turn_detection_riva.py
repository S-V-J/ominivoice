"""
Stack B: Riva VAD NIM gRPC Client for Voice Activity Detection & Turn Detection.
Implements the same TurnDetector interface as Silero for interchangeability.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional, AsyncIterator

import grpc
import numpy as np
import riva.client
from riva.client.proto.riva_asr_pb2 import (
    StreamingRecognitionConfig,
    StreamingRecognizeRequest,
    RecognitionConfig,
)
from riva.client.proto.riva_audio_pb2 import AudioEncoding

from .turn_detection import TurnDetector, TurnResult

logger = logging.getLogger(__name__)


@dataclass
class RivaVADConfig:
    """Configuration for Riva VAD-based turn detection."""
    threshold: float = 0.5  # VAD threshold 0.0-1.0
    min_silence_duration_ms: int = 600  # Minimum silence to consider turn end
    min_speech_duration_ms: int = 250  # Minimum speech duration to consider valid
    speech_pad_ms: int = 100  # Padding around speech segments
    sample_rate: int = 16000
    frame_duration_ms: int = 20


class RivaVADTurnDetector(TurnDetector):
    """
    Riva VAD-based turn detector.

    Uses Riva ASR streaming with VAD to detect speech/silence boundaries.
    Provides semantic endpointing similar to Silero + Smart Turn.
    """

    def __init__(
        self,
        grpc_endpoint: str = "localhost:50051",
        vad_threshold: float = 0.5,
        language_code: str = "en-US",
        sensitivity: str = "medium",
        sample_rate: int = 16000,
        use_ssl: bool = False,
        metadata: Optional[list] = None,
    ):
        """
        Initialize Riva VAD turn detector.

        Args:
            grpc_endpoint: Riva NIM gRPC endpoint (host:port)
            vad_threshold: VAD threshold 0.0-1.0 (higher = more sensitive)
            language_code: BCP-47 language code
            sensitivity: "high", "medium", "low" - maps to silence duration thresholds
            sample_rate: Audio sample rate
            use_ssl: Use secure gRPC channel
            metadata: Additional gRPC metadata (auth headers)
        """
        self.grpc_endpoint = grpc_endpoint
        self.vad_threshold = vad_threshold
        self.language_code = language_code
        self.sensitivity = sensitivity
        self.sample_rate = sample_rate
        self.use_ssl = use_ssl
        self.metadata = metadata or []

        # Map sensitivity to silence timeout
        self.silence_ms_map = {
            "high": 350,
            "medium": 600,
            "low": 900,
        }
        self.min_silence_ms = self.silence_ms_map.get(sensitivity, 600)

        self._client: Optional[riva.client.ASRService] = None
        self._channel: Optional[grpc.Channel] = None
        self._streaming_config = None
        self._vad_stream = None
        self._closed = False

        # State for turn detection
        self._current_transcript = ""
        self._last_speech_time = 0
        self._in_speech = False
        _ = None  # Frame counter

    async def initialize(self) -> None:
        """Initialize gRPC channel and Riva ASR client for VAD."""
        if self._client is not None:
            return

        logger.info(f"Connecting to Riva VAD at {self.grpc_endpoint}...")

        if self.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(self.grpc_endpoint, credentials)
        else:
            self._channel = grpc.aio.insecure_channel(self.grpc_endpoint)

        self._client = riva.client.ASRService(self._channel)

        # Build streaming config with VAD
        recognition_config = RecognitionConfig(
            encoding=AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=self.sample_rate,
            language_code=self.language_code,
            max_alternatives=1,
            enable_automatic_punctuation=True,
        )

        self._streaming_config = StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=True,
        )

        logger.info(f"Riva VAD initialized: threshold={self.vad_threshold}, sensitivity={self.sensitivity}")

    def _map_sensitivity_to_vad_threshold(self, sensitivity: str) -> float:
        """Map sensitivity string to VAD threshold."""
        mapping = {
            "high": 0.3,    # More sensitive, triggers on less speech
            "medium": 0.5,  # Balanced
            "low": 0.7,     # Less sensitive, needs clearer speech
        }
        return mapping.get(sensitivity, 0.5)

    async def process_frame(self, frame: np.ndarray) -> TurnResult:
        """
        Process a single audio frame through Riva VAD.

        Note: Riva VAD is typically used via streaming ASR.
        This implementation uses a simplified approach - in production,
        you'd use Riva's dedicated VAD service if available, or run
        a continuous streaming ASR session for VAD.

        For now, this provides a compatible interface that can be
        enhanced when Riva exposes a dedicated VAD endpoint.
        """
        if self._client is None:
            await self.initialize()

        # For a frame-level VAD, we'd ideally use a dedicated VAD service.
        # Since Riva's VAD is embedded in ASR streaming, we approximate
        # with energy-based detection as a fallback, similar to Silero.

        # Convert to float32 if needed
        if frame.dtype == np.int16:
            audio_float = frame.astype(np.float32) / 32768.0
        else:
            audio_float = frame.astype(np.float32)

        # Simple energy-based VAD (fallback when Riva VAD not directly accessible)
        energy = np.sqrt(np.mean(audio_float ** 2))
        is_speech = energy > self.vad_threshold * 0.1  # Scale threshold

        current_time = asyncio.get_event_loop().time() * 1000  # ms

        if is_speech:
            if not self._in_speech:
                self._in_speech = True
                self._last_speech_time = current_time
            else:
                self._last_speech_time = current_time
        else:
            if self._in_speech:
                silence_duration = current_time - self._last_speech_time
                if silence_duration >= self.min_silence_ms:
                    self._in_speech = False
                    return TurnResult(
                        is_speech=False,
                        is_turn_end=True,
                        reason="silence_timeout",
                        silence_duration_ms=silence_duration,
                        transcript=self._current_transcript,
                    )

        return TurnResult(
            is_speech=is_speech,
            is_turn_end=False,
            reason="processing",
            silence_duration_ms=0,
            transcript=self._current_transcript,
        )

    def update_transcript(self, transcript: str, is_final: bool = False) -> None:
        """Update current transcript for semantic endpointing."""
        self._current_transcript = transcript

        # Check for syntactic incompleteness (similar to Silero Smart Turn)
        if is_final:
            # Check if transcript ends with incomplete syntax
            incomplete_endings = [
                'and', 'but', 'or', 'so', 'because', 'since', 'while', 'although',
                'if', 'when', 'then', 'the', 'a', 'an', 'to', 'for', 'of', 'in',
                'on', 'at', 'by', 'with', 'from', 'as', 'is', 'was', 'were',
            ]
            words = transcript.strip().lower().split()
            if words and words[-1] in incomplete_endings:
                # Extend silence timeout for incomplete sentences
                self.min_silence_ms = self.silence_ms_map.get(self.sensitivity, 600) + 500
            else:
                self.min_silence_ms = self.silence_ms_map.get(self.sensitivity, 600)

    async def reset(self) -> None:
        """Reset detector state for new utterance."""
        self._current_transcript = ""
        self._last_speech_time = 0
        self._in_speech = False
        _ = 0

    async def close(self) -> None:
        """Close gRPC channel and cleanup."""
        self._closed = True
        if self._channel:
            await self._channel.close()
            self._channel = None
        self._client = None
        logger.info("Riva VAD client closed")


def create_riva_vad_detector(
    grpc_endpoint: Optional[str] = None,
    vad_threshold: Optional[float] = None,
    language_code: Optional[str] = None,
    sensitivity: str = "medium",
    sample_rate: int = 16000,
    use_ssl: bool = False,
    metadata: Optional[list] = None,
) -> RivaVADTurnDetector:
    """
    Factory function to create Riva VAD detector from config.

    Reads from environment variables if not provided:
    - RIVA_VAD_GRPC_ENDPOINT (default: "localhost:50051")
    - RIVA_VAD_THRESHOLD (default: "0.5")
    - RIVA_VAD_LANGUAGE (default: "en-US")
    - RIVA_VAD_USE_SSL (default: "false")
    - NGC_API_KEY (for NVCF auth metadata)
    """
    if grpc_endpoint is None:
        grpc_endpoint = os.getenv("RIVA_VAD_GRPC_ENDPOINT", "localhost:50051")
    if vad_threshold is None:
        vad_threshold = float(os.getenv("RIVA_VAD_THRESHOLD", "0.5"))
    if language_code is None:
        language_code = os.getenv("RIVA_VAD_LANGUAGE", "en-US")
    if use_ssl is None:
        use_ssl = os.getenv("RIVA_VAD_USE_SSL", "false").lower() == "true"

    # Build metadata for authentication (NVCF)
    if metadata is None:
        metadata = []
        ngc_api_key = os.getenv("NGC_API_KEY")
        if ngc_api_key:
            metadata.append(("authorization", f"Bearer {ngc_api_key}"))
        function_id = os.getenv("RIVA_VAD_FUNCTION_ID")
        if function_id:
            metadata.append(("function-id", function_id))

    return RivaVADTurnDetector(
        grpc_endpoint=grpc_endpoint,
        vad_threshold=vad_threshold,
        language_code=language_code,
        sensitivity=sensitivity,
        sample_rate=sample_rate,
        use_ssl=use_ssl,
        metadata=metadata,
    )