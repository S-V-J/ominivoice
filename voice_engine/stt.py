"""
Streaming Speech-to-Text Engines.
Supports Stack A (faster-whisper local) and Stack B (Riva ASR NIM gRPC).
"""
import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A single transcript segment (interim or final)."""
    text: str
    is_final: bool
    start_time: float
    end_time: float
    language: Optional[str] = None
    language_probability: Optional[float] = None


class STTEngine(ABC):
    """Abstract base class for STT engines."""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_chunk_generator: AsyncIterator[np.ndarray],
    ) -> AsyncIterator[TranscriptSegment]:
        """
        Transcribe a stream of audio chunks.

        Args:
            audio_chunk_generator: Async iterator yielding numpy arrays of audio samples
                                 (int16 or float32, mono, 16kHz expected)

        Yields:
            TranscriptSegment objects with interim and final results
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass


class FasterWhisperSTT(STTEngine):
    """
    faster-whisper streaming STT engine.
    Uses CTranslate2 for fast inference with int8/float16 quantization.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
        language: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        vad_parameters: Optional[dict] = None,
    ):
        """
        Initialize faster-whisper model.

        Args:
            model_size: Model size (tiny, base, small, medium, large-v3)
            device: "cuda", "cpu", or "auto"
            compute_type: "int8", "float16", "float32", "int8_float16"
            language: Force language (None for auto-detect)
            beam_size: Beam size for decoding
            vad_filter: Enable VAD filtering for speech segments
            vad_parameters: VAD parameters dict
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.vad_parameters = vad_parameters or {
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "max_speech_duration_s": 30,
            "min_silence_duration_ms": 100,
            "window_size_samples": 1024,
            "speech_pad_ms": 400,
        }
        self._model = None
        self._initialized = False

    async def _initialize(self):
        """Lazy initialization of the whisper model."""
        if self._initialized:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model: {self.model_size} on {self.device} ({self.compute_type})")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._initialized = True
            logger.info("faster-whisper model loaded successfully")
        except ImportError:
            logger.error("faster-whisper not installed. Install with: pip install faster-whisper")
            raise
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise

    async def transcribe_stream(
        self,
        audio_chunk_generator: AsyncIterator[np.ndarray],
    ) -> AsyncIterator[TranscriptSegment]:
        """
        Stream transcribe audio chunks using faster-whisper's streaming API.

        Note: faster-whisper doesn't have native streaming, so we batch chunks
        and run inference on accumulating buffers, yielding interim results.
        """
        await self._initialize()

        # Accumulate audio chunks into a buffer
        buffer = np.array([], dtype=np.float32)
        chunk_duration_ms = 100  # Process every 100ms
        sample_rate = 16000
        samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)

        async for chunk in audio_chunk_generator:
            # Ensure float32 mono
            if chunk.dtype == np.int16:
                chunk = chunk.astype(np.float32) / 32768.0
            elif chunk.dtype != np.float32:
                chunk = chunk.astype(np.float32)

            # Handle stereo -> mono
            if chunk.ndim > 1:
                chunk = chunk.mean(axis=1)

            buffer = np.concatenate([buffer, chunk])

            # Process when we have enough samples
            while len(buffer) >= samples_per_chunk:
                process_chunk = buffer[:samples_per_chunk]
                buffer = buffer[samples_per_chunk:]

                # Run inference in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                segments, info = await loop.run_in_executor(
                    None,
                    lambda: list(self._model.transcribe(
                        process_chunk,
                        language=self.language,
                        beam_size=self.beam_size,
                        vad_filter=self.vad_filter,
                        vad_parameters=self.vad_parameters,
                        word_timestamps=True,
                    ))
                )

                for segment in segments:
                    # Yield interim for each segment, final when VAD confirms end
                    yield TranscriptSegment(
                        text=segment.text.strip(),
                        is_final=True,  # faster-whisper gives final segments with VAD
                        start_time=segment.start,
                        end_time=segment.end,
                        language=info.language,
                        language_probability=info.language_probability,
                    )

    async def close(self) -> None:
        """Release model resources."""
        self._model = None
        self._initialized = False


class StreamingFasterWhisperSTT(STTEngine):
    """
    True streaming STT using faster-whisper with sliding window.
    Better suited for realtime with interim results.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
        language: Optional[str] = None,
        window_duration_s: float = 2.0,
        step_duration_s: float = 0.5,
    ):
        """
        Initialize streaming STT.

        Args:
            model_size: Model size
            device: Device to run on
            compute_type: Quantization type
            language: Force language
            window_duration_s: Audio window for each inference
            step_duration_s: How much to advance window each step
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.window_duration_s = window_duration_s
        self.step_duration_s = step_duration_s
        self.sample_rate = 16000
        self._model = None
        self._initialized = False

    async def _initialize(self):
        if self._initialized:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading streaming faster-whisper: {self.model_size}")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._initialized = True
        except ImportError:
            logger.error("faster-whisper not installed")
            raise

    async def transcribe_stream(
        self,
        audio_chunk_generator: AsyncIterator[np.ndarray],
    ) -> AsyncIterator[TranscriptSegment]:
        """Streaming transcription with sliding window for interim results."""
        await self._initialize()

        window_samples = int(self.sample_rate * self.window_duration_s)
        step_samples = int(self.sample_rate * self.step_duration_s)

        buffer = np.array([], dtype=np.float32)
        last_text = ""

        async for chunk in audio_chunk_generator:
            if chunk.dtype == np.int16:
                chunk = chunk.astype(np.float32) / 32768.0
            elif chunk.dtype != np.float32:
                chunk = chunk.astype(np.float32)

            if chunk.ndim > 1:
                chunk = chunk.mean(axis=1)

            buffer = np.concatenate([buffer, chunk])

            # Process when we have at least one window
            while len(buffer) >= window_samples:
                window = buffer[:window_samples]
                # Keep overlap for next step
                buffer = buffer[step_samples:]

                loop = asyncio.get_event_loop()
                segments, info = await loop.run_in_executor(
                    None,
                    lambda: list(self._model.transcribe(
                        window,
                        language=self.language,
                        beam_size=5,
                        vad_filter=True,
                        word_timestamps=False,
                    ))
                )

                # Combine segments into single text
                current_text = " ".join(s.text.strip() for s in segments)

                # Determine if this is new content (interim) or final
                # Simple heuristic: if text grew significantly, it's interim
                is_final = len(current_text) <= len(last_text) * 1.1
                if current_text and current_text != last_text:
                    yield TranscriptSegment(
                        text=current_text,
                        is_final=is_final,
                        start_time=0,
                        end_time=self.window_duration_s,
                        language=info.language,
                        language_probability=info.language_probability,
                    )
                    last_text = current_text

    async def close(self) -> None:
        self._model = None
        self._initialized = False


def create_stt_engine(
    engine: str = "faster-whisper",
    model_size: str = "small",
    device: str = "auto",
    compute_type: str = "int8",
    language: Optional[str] = None,
    streaming: bool = True,
    # Stack B (Riva ASR) parameters
    voice_stack: str = "stack_a",
    riva_grpc_endpoint: Optional[str] = None,
    riva_language: Optional[str] = None,
    riva_use_ssl: bool = False,
    riva_metadata: Optional[list] = None,
) -> STTEngine:
    """
    Factory function to create STT engine for either stack.

    Args:
        engine: Engine name ("faster-whisper" or "riva-asr")
        model_size: Model size (Stack A)
        device: Device (Stack A)
        compute_type: Quantization (Stack A)
        language: Language code
        streaming: Use streaming mode with interim results
        voice_stack: "stack_a" (local) or "stack_b" (NVIDIA NIM)
        riva_grpc_endpoint: Riva ASR gRPC endpoint (Stack B)
        riva_language: Riva ASR language code (Stack B)
        riva_use_ssl: Use SSL for Riva gRPC (Stack B)
        riva_metadata: Auth metadata for Riva (Stack B)

    Returns:
        STTEngine instance
    """
    # Stack B: Riva ASR NIM
    if voice_stack == "stack_b" or engine == "riva-asr":
        from .stt_riva import create_riva_asr_engine
        return create_riva_asr_engine(
            grpc_endpoint=riva_grpc_endpoint,
            language_code=riva_language or language,
            sample_rate=16000,
            use_ssl=riva_use_ssl,
            metadata=riva_metadata,
        )

    # Stack A: faster-whisper (default)
    if engine == "faster-whisper":
        if streaming:
            return StreamingFasterWhisperSTT(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                language=language,
            )
        else:
            return FasterWhisperSTT(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                language=language,
            )

    raise ValueError(f"Unknown STT engine: {engine} for stack: {voice_stack}")