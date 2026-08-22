"""
Stack B: Chatterbox TTS NIM gRPC Client for Streaming Text-to-Speech.
Implements the same TTSEngine interface as Kokoro/Piper for interchangeability.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import AsyncIterator, Optional, List

import grpc
import numpy as np
import riva.client
from riva.client.proto.riva_tts_pb2 import (
    SynthesizeSpeechRequest,
)
from riva.client.proto.riva_audio_pb2 import AudioEncoding as RivaAudioEncoding

from .tts import TTSEngine, AudioChunk

logger = logging.getLogger(__name__)


@dataclass
class ChatterboxVoice:
    """Chatterbox TTS voice configuration."""
    name: str
    language_code: str
    gender: str  # "Male" or "Female"
    description: str = ""


# Known Chatterbox Multilingual voices (23 languages)
CHATTERBOX_VOICES = {
    # English
    "Chatterbox-Multilingual.en-US.Female": ChatterboxVoice(
        "Chatterbox-Multilingual.en-US.Female", "en-US", "Female", "US English Female"
    ),
    "Chatterbox-Multilingual.en-US.Male": ChatterboxVoice(
        "Chatterbox-Multilingual.en-US.Male", "en-US", "Male", "US English Male"
    ),
    # Spanish
    "Chatterbox-Multilingual.es-US.Female": ChatterboxVoice(
        "Chatterbox-Multilingual.es-US.Female", "es-US", "Female", "US Spanish Female"
    ),
    "Chatterbox-Multilingual.es-US.Male": ChatterboxVoice(
        "Chatterbox-Multilingual.es-US.Male", "es-US", "Male", "US Spanish Male"
    ),
    # Hindi
    "Chatterbox-Multilingual.hi-IN.Female": ChatterboxVoice(
        "Chatterbox-Multilingual.hi-IN.Female", "hi-IN", "Female", "Hindi Female"
    ),
    "Chatterbox-Multilingual.hi-IN.Male": ChatterboxVoice(
        "Chatterbox-Multilingual.hi-IN.Male", "hi-IN", "Male", "Hindi Male"
    ),
    # Add more as needed - full list from `talk.py --list-voices`
}


class ChatterboxTTSEngine(TTSEngine):
    """
    Chatterbox TTS NIM streaming client.

    Connects to Chatterbox TTS NIM gRPC endpoint for real-time speech synthesis.
    Uses the same interface as Kokoro/Piper for seamless stack switching.
    """

    def __init__(
        self,
        grpc_endpoint: str = "localhost:50051",
        voice_name: str = "Chatterbox-Multilingual.en-US.Female",
        language_code: str = "en-US",
        sample_rate: int = 24000,  # Chatterbox outputs 24kHz
        emotion_exaggeration: float = 0.5,  # 0.0-1.0, recommended 0.4-0.7
        use_ssl: bool = False,
        metadata: Optional[list] = None,
    ):
        """
        Initialize Chatterbox TTS client.

        Args:
            grpc_endpoint: Chatterbox NIM gRPC endpoint (host:port)
            voice_name: Chatterbox voice identifier
            language_code: BCP-47 language code
            sample_rate: Output sample rate (24000 for Chatterbox)
            emotion_exaggeration: Emotion control 0.0-1.0 (recommended 0.4-0.7)
            use_ssl: Use secure gRPC channel (for NVCF)
            metadata: Additional gRPC metadata (e.g., auth headers for NVCF)
        """
        self.grpc_endpoint = grpc_endpoint
        self.voice_name = voice_name
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.emotion_exaggeration = max(0.0, min(1.0, emotion_exaggeration))
        self.use_ssl = use_ssl
        self.metadata = metadata or []

        self._client: Optional[riva.client.TTSService] = None
        self._channel: Optional[grpc.Channel] = None
        self._closed = False

        # Validate voice
        if voice_name not in CHATTERBOX_VOICES:
            logger.warning(f"Voice '{voice_name}' not in known voices list. Using anyway.")

    async def initialize(self) -> None:
        """Initialize gRPC channel and Riva TTS client."""
        if self._client is not None:
            return

        logger.info(f"Connecting to Chatterbox TTS at {self.grpc_endpoint}...")

        # Create gRPC channel
        if self.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(self.grpc_endpoint, credentials)
        else:
            self._channel = grpc.aio.insecure_channel(self.grpc_endpoint)

        # Create Riva TTS client
        self._client = riva.client.TTSService(self._channel)

        logger.info(f"Chatterbox TTS initialized: {self.voice_name} @ {self.sample_rate}Hz")

    async def synthesize_stream(
        self,
        text_generator,
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream text to Chatterbox TTS and yield audio chunks.

        Args:
            text_generator: Async iterator yielding text tokens (strings)

        Yields:
            AudioChunk with audio (numpy float32), sample_rate, is_final
        """
        if self._client is None:
            await self.initialize()

        if self._closed:
            raise RuntimeError("Chatterbox TTS engine is closed")

        # Collect all text first (Chatterbox streaming works best with full sentences)
        # For true streaming, we'd use SynthesizeOnline, but Chatterbox may not support it fully yet
        text_parts = []
        async for token in text_generator:
            if token is None:  # End of stream signal
                break
            if token:
                text_parts.append(token)

        full_text = "".join(text_parts).strip()
        if not full_text:
            return

        logger.debug(f"Chatterbox synthesizing: {full_text[:100]}...")

        # Build request with direct fields (Riva TTS uses voice_name, not VoiceSelectionParams)
        request = SynthesizeSpeechRequest(
            text=full_text,
            voice_name=self.voice_name,
            language_code=self.language_code,
            encoding=RivaAudioEncoding.LINEAR_PCM,
            sample_rate_hz=self.sample_rate,
            # Chatterbox-specific parameters via custom fields if supported
            # emotion_exaggeration would be a custom parameter
        )

        # Use non-streaming synthesis and chunk results for streaming feel
        async for chunk in self._synthesize_non_streaming(full_text, self.voice_name, self.language_code):
            yield chunk

    async def _synthesize_non_streaming(
        self,
        text: str,
        voice_name: str,
        language_code: str,
    ) -> AsyncIterator[AudioChunk]:
        """Fallback to non-streaming synthesis, chunk the result."""
        request = SynthesizeSpeechRequest(
            text=text,
            voice_name=voice_name,
            language_code=language_code,
            encoding=RivaAudioEncoding.LINEAR_PCM,
            sample_rate_hz=self.sample_rate,
        )

        response = await self._client.stub.SynthesizeSpeech(
            request,
            metadata=self.metadata,
        )

        if response.audio:
            audio_int16 = np.frombuffer(response.audio, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Chunk into ~100ms pieces for smoother streaming feel
            chunk_size = int(self.sample_rate * 0.1)  # 100ms
            for i in range(0, len(audio_float32), chunk_size):
                if self._closed:
                    break
                chunk = audio_float32[i:i + chunk_size]
                is_final = (i + chunk_size) >= len(audio_float32)
                yield AudioChunk(
                    audio=chunk,
                    sample_rate=self.sample_rate,
                    is_final=is_final,
                )

    async def close(self) -> None:
        """Close gRPC channel and cleanup."""
        self._closed = True
        if self._channel:
            await self._channel.close()
            self._channel = None
        self._client = None
        logger.info("Chatterbox TTS client closed")

    @property
    def voices(self) -> List[str]:
        """Get list of available voices."""
        return list(CHATTERBOX_VOICES.keys())


def create_chatterbox_tts_engine(
    grpc_endpoint: Optional[str] = None,
    voice_name: Optional[str] = None,
    language_code: Optional[str] = None,
    emotion_exaggeration: Optional[float] = None,
    use_ssl: bool = False,
    metadata: Optional[list] = None,
) -> ChatterboxTTSEngine:
    """
    Factory function to create Chatterbox TTS engine from config.

    Reads from environment variables if not provided:
    - CHATTERBOX_GRPC_ENDPOINT (default: "localhost:50051")
    - CHATTERBOX_VOICE (default: "Chatterbox-Multilingual.en-US.Female")
    - CHATTERBOX_LANGUAGE (default: "en-US")
    - CHATTERBOX_EMOTION_EXAGGERATION (default: "0.5")
    - CHATTERBOX_USE_SSL (default: "false")
    - NGC_API_KEY (for NVCF auth metadata)
    """
    if grpc_endpoint is None:
        grpc_endpoint = os.getenv("CHATTERBOX_GRPC_ENDPOINT", "localhost:50051")
    if voice_name is None:
        voice_name = os.getenv("CHATTERBOX_VOICE", "Chatterbox-Multilingual.en-US.Female")
    if language_code is None:
        language_code = os.getenv("CHATTERBOX_LANGUAGE", "en-US")
    if emotion_exaggeration is None:
        emotion_exaggeration = float(os.getenv("CHATTERBOX_EMOTION_EXAGGERATION", "0.5"))
    if use_ssl is None:
        use_ssl = os.getenv("CHATTERBOX_USE_SSL", "false").lower() == "true"

    # Build metadata for authentication (NVCF)
    if metadata is None:
        metadata = []
        ngc_api_key = os.getenv("NGC_API_KEY")
        if ngc_api_key:
            metadata.append(("authorization", f"Bearer {ngc_api_key}"))
        function_id = os.getenv("CHATTERBOX_FUNCTION_ID")
        if function_id:
            metadata.append(("function-id", function_id))

    return ChatterboxTTSEngine(
        grpc_endpoint=grpc_endpoint,
        voice_name=voice_name,
        language_code=language_code,
        emotion_exaggeration=emotion_exaggeration,
        use_ssl=use_ssl,
        metadata=metadata,
    )