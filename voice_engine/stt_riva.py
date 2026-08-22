"""
Stack B: Riva ASR NIM gRPC Client for Streaming Speech-to-Text.
Implements the same STTEngine interface as faster-whisper for interchangeability.
"""
import asyncio
import logging
import os
from typing import AsyncIterator, Optional

import grpc
import riva.client
from riva.client.proto.riva_asr_pb2 import (
    StreamingRecognitionConfig,
    StreamingRecognizeRequest,
    RecognitionConfig,
)
from riva.client.proto.riva_audio_pb2 import AudioEncoding

from .stt import STTEngine, TranscriptSegment

logger = logging.getLogger(__name__)


class RivaASREngine(STTEngine):
    """
    Riva ASR NIM streaming client.

    Connects to Riva Speech NIM gRPC endpoint for real-time transcription.
    Uses the same interface as faster-whisper for seamless stack switching.
    """

    def __init__(
        self,
        grpc_endpoint: str = "localhost:50051",
        language_code: str = "en-US",
        sample_rate: int = 16000,
        interim_results: bool = True,
        enable_automatic_punctuation: bool = True,
        use_ssl: bool = False,
        metadata: Optional[list] = None,
    ):
        """
        Initialize Riva ASR client.

        Args:
            grpc_endpoint: Riva NIM gRPC endpoint (host:port)
            language_code: BCP-47 language code (e.g., en-US, es-US, hi-IN)
            sample_rate: Audio sample rate (16000 for 16kHz)
            interim_results: Whether to return interim (partial) results
            enable_automatic_punctuation: Add punctuation to transcripts
            use_ssl: Use secure gRPC channel (for NVCF)
            metadata: Additional gRPC metadata (e.g., auth headers for NVCF)
        """
        self.grpc_endpoint = grpc_endpoint
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.interim_results = interim_results
        self.enable_automatic_punctuation = enable_automatic_punctuation
        self.use_ssl = use_ssl
        self.metadata = metadata or []

        self._client: Optional[riva.client.ASRService] = None
        self._channel: Optional[grpc.Channel] = None
        self._streaming_config = None
        self._closed = False

    async def initialize(self) -> None:
        """Initialize gRPC channel and Riva ASR client."""
        if self._client is not None:
            return

        logger.info(f"Connecting to Riva ASR at {self.grpc_endpoint}...")

        # Create gRPC channel
        if self.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(self.grpc_endpoint, credentials)
        else:
            self._channel = grpc.aio.insecure_channel(self.grpc_endpoint)

        # Create Riva ASR client
        self._client = riva.client.ASRService(self._channel)

        # Build streaming recognition config
        recognition_config = RecognitionConfig(
            encoding=AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=self.sample_rate,
            language_code=self.language_code,
            max_alternatives=1,
            enable_automatic_punctuation=self.enable_automatic_punctuation,
            verbatim_transcripts=not self.enable_automatic_punctuation,
        )

        self._streaming_config = StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=self.interim_results,
        )

        logger.info(f"Riva ASR initialized: {self.language_code}@{self.sample_rate}Hz")

    async def transcribe_stream(
        self,
        audio_chunk_generator,
    ) -> AsyncIterator[TranscriptSegment]:
        """
        Stream audio chunks to Riva ASR and yield transcript segments.

        Args:
            audio_chunk_generator: Async iterator yielding numpy float32 arrays (16kHz mono)

        Yields:
            TranscriptSegment with text, is_final, confidence, start_time, end_time
        """
        if self._client is None:
            await self.initialize()

        if self._closed:
            raise RuntimeError("Riva ASR engine is closed")

        import time

        # Create request generator
        async def request_generator():
            # First request: config only
            yield StreamingRecognizeRequest(streaming_config=self._streaming_config)

            # Subsequent requests: audio data
            async for chunk in audio_chunk_generator:
                if self._closed:
                    break
                # Convert float32 [-1,1] to int16 bytes
                import numpy as np
                if chunk.dtype == np.float32:
                    chunk = (chunk * 32767).astype(np.int16)
                elif chunk.dtype != np.int16:
                    chunk = chunk.astype(np.int16)

                yield StreamingRecognizeRequest(audio_content=chunk.tobytes())

        try:
            # Call streaming recognize
            call = self._client.stub.StreamingRecognize(
                request_generator(),
                metadata=self.metadata,
            )

            async for response in call:
                if self._closed:
                    break

                for result in response.results:
                    if not result.alternatives:
                        continue

                    alt = result.alternatives[0]
                    text = alt.transcript.strip()

                    if not text:
                        continue

                    is_final = result.is_final
                    confidence = alt.confidence if hasattr(alt, 'confidence') else 1.0

                    # Calculate approximate timestamps
                    # Riva doesn't provide word-level timestamps in streaming mode by default
                    current_time = time.time()

                    yield TranscriptSegment(
                        text=text,
                        is_final=is_final,
                        confidence=confidence,
                        start_time=current_time - 1.0,  # Approximate
                        end_time=current_time,
                        language=self.language_code,
                    )

        except grpc.aio.AioRpcError as e:
            logger.error(f"Riva ASR streaming error: {e.code()} - {e.details()}")
            raise
        except Exception as e:
            logger.error(f"Riva ASR transcribe error: {e}")
            raise

    async def close(self) -> None:
        """Close gRPC channel and cleanup."""
        self._closed = True
        if self._channel:
            await self._channel.close()
            self._channel = None
        self._client = None
        logger.info("Riva ASR client closed")


def create_riva_asr_engine(
    grpc_endpoint: Optional[str] = None,
    language_code: Optional[str] = None,
    sample_rate: int = 16000,
    use_ssl: bool = False,
    metadata: Optional[list] = None,
) -> RivaASREngine:
    """
    Factory function to create Riva ASR engine from config.

    Reads from environment variables if not provided:
    - RIVA_ASR_GRPC_ENDPOINT (default: "localhost:50051")
    - RIVA_ASR_LANGUAGE (default: "en-US")
    - RIVA_ASR_USE_SSL (default: "false")
    - NGC_API_KEY (for NVCF auth metadata)
    """
    if grpc_endpoint is None:
        grpc_endpoint = os.getenv("RIVA_ASR_GRPC_ENDPOINT", "localhost:50051")
    if language_code is None:
        language_code = os.getenv("RIVA_ASR_LANGUAGE", "en-US")
    if use_ssl is None:
        use_ssl = os.getenv("RIVA_ASR_USE_SSL", "false").lower() == "true"

    # Build metadata for authentication (NVCF)
    if metadata is None:
        metadata = []
        ngc_api_key = os.getenv("NGC_API_KEY")
        if ngc_api_key:
            metadata.append(("authorization", f"Bearer {ngc_api_key}"))
        # Function ID for specific NIM (if needed)
        function_id = os.getenv("RIVA_ASR_FUNCTION_ID")
        if function_id:
            metadata.append(("function-id", function_id))

    return RivaASREngine(
        grpc_endpoint=grpc_endpoint,
        language_code=language_code,
        sample_rate=sample_rate,
        use_ssl=use_ssl,
        metadata=metadata,
    )


# Backwards compatibility - can be used as drop-in replacement
# Usage: stt = create_riva_asr_engine()