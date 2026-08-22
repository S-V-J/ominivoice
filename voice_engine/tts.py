"""
Streaming Text-to-Speech Engines.
Supports Stack A (Kokoro/Piper local) and Stack B (Chatterbox TTS NIM gRPC).
"""
import asyncio
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """A chunk of synthesized audio."""
    audio: np.ndarray  # float32, mono, sample_rate Hz
    sample_rate: int
    is_final: bool = False


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text_generator: AsyncIterator[str],
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream synthesize audio from text chunks.

        Args:
            text_generator: Async iterator yielding text chunks (sentences/phrases)

        Yields:
            AudioChunk objects with synthesized audio
        """
        pass

    @abstractmethod
    async def synthesize(self, text: str) -> np.ndarray:
        """Synthesize complete text to audio (non-streaming)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate."""
        pass

    @property
    @abstractmethod
    def available_voices(self) -> List[str]:
        """List of available voice names."""
        pass


class KokoroTTS(TTSEngine):
    """
    Kokoro-82M TTS engine.
    Small, fast, high-quality TTS with multiple voices.
    """

    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.0,
        device: str = "auto",
    ):
        """
        Initialize Kokoro TTS.

        Args:
            voice: Voice name (e.g., 'af_heart', 'am_puck', 'bf_emma', etc.)
            speed: Speech speed multiplier
            device: "cuda", "cpu", or "auto"
        """
        self.voice = voice
        self.speed = speed
        self.device = device
        self._model = None
        self._pipeline = None
        self._initialized = False
        self._sample_rate = 24000  # Kokoro native sample rate

        # Kokoro voice mapping
        self._voice_map = {
            # American Female
            "af_heart": "af_heart",
            "af_bella": "af_bella",
            "af_nicole": "af_nicole",
            "af_sarah": "af_sarah",
            "af_sky": "af_sky",
            # American Male
            "am_adam": "am_adam",
            "am_michael": "am_michael",
            "am_puck": "am_puck",
            # British Female
            "bf_emma": "bf_emma",
            "bf_isabella": "bf_isabella",
            # British Male
            "bm_daniel": "bm_daniel",
            "bm_fable": "bm_fable",
            "bm_george": "bm_george",
            "bm_lewis": "bm_lewis",
        }

    async def _initialize(self):
        """Lazy load Kokoro model."""
        if self._initialized:
            return

        try:
            from kokoro import KPipeline
            import torch

            logger.info(f"Loading Kokoro TTS with voice: {self.voice}")

            # Determine device
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device

            lang_code = self._get_lang_code(self.voice)
            self._pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=device)
            self._initialized = True
            logger.info("Kokoro TTS loaded successfully")
        except ImportError:
            logger.error("kokoro not installed. Install with: pip install kokoro-onnx")
            raise
        except Exception as e:
            logger.error(f"Failed to load Kokoro TTS: {e}")
            raise

    def _get_lang_code(self, voice: str) -> str:
        """Get language code from voice name."""
        if voice.startswith(("af_", "am_")):
            return "a"  # American English
        elif voice.startswith(("bf_", "bm_")):
            return "b"  # British English
        return "a"

    async def synthesize_stream(
        self,
        text_generator: AsyncIterator[str],
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream synthesize from text chunks.
        Kokoro generates per-sentence, so we yield as each sentence completes.
        """
        await self._initialize()

        # Collect all text first (Kokoro works best with full sentences)
        # For true streaming, we buffer until we have sentence boundaries
        text_buffer = ""
        sentence_endings = ('.', '!', '?', '。', '！', '？')

        async for text_chunk in text_generator:
            text_buffer += text_chunk

            # Check for sentence boundaries
            while True:
                end_idx = -1
                for ending in sentence_endings:
                    idx = text_buffer.find(ending)
                    if idx != -1:
                        if end_idx == -1 or idx < end_idx:
                            end_idx = idx

                if end_idx == -1:
                    break  # No complete sentence yet

                # Extract sentence
                sentence = text_buffer[:end_idx + 1].strip()
                text_buffer = text_buffer[end_idx + 1:]

                if sentence:
                    # Synthesize this sentence
                    audio = await self._synthesize_sentence(sentence)
                    yield AudioChunk(
                        audio=audio,
                        sample_rate=self._sample_rate,
                        is_final=False,
                    )

        # Synthesize remaining buffer
        if text_buffer.strip():
            audio = await self._synthesize_sentence(text_buffer.strip())
            yield AudioChunk(
                audio=audio,
                sample_rate=self._sample_rate,
                is_final=True,
            )
        else:
            # Send final marker
            yield AudioChunk(
                audio=np.array([], dtype=np.float32),
                sample_rate=self._sample_rate,
                is_final=True,
            )

    async def _synthesize_sentence(self, text: str) -> np.ndarray:
        """Synthesize a single sentence."""
        loop = asyncio.get_event_loop()

        def _generate():
            generator = self._pipeline(
                text,
                voice=self._voice_map.get(self.voice, self.voice),
                speed=self.speed,
                split_pattern=r'\n+',
            )
            # Collect all audio chunks
            audio_chunks = []
            for _, _, audio in generator:
                audio_chunks.append(audio)
            if audio_chunks:
                return np.concatenate(audio_chunks)
            return np.array([], dtype=np.float32)

        return await loop.run_in_executor(None, _generate)

    async def synthesize(self, text: str) -> np.ndarray:
        """Synthesize complete text (non-streaming)."""
        await self._initialize()
        return await self._synthesize_sentence(text)

    async def close(self) -> None:
        self._pipeline = None
        self._initialized = False

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def available_voices(self) -> List[str]:
        return list(self._voice_map.keys())


class PiperTTS(TTSEngine):
    """
    Piper TTS engine (fallback for low-resource environments).
    Fast, lightweight, CPU-friendly.
    """

    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        model_dir: Optional[str] = None,
    ):
        """
        Initialize Piper TTS.

        Args:
            voice: Voice model name (e.g., 'en_US-lessac-medium', 'en_US-amy-low')
            model_dir: Directory containing Piper voice models
        """
        self.voice = voice
        self.model_dir = model_dir or os.path.expanduser("~/.local/share/piper/voices")
        self._voice_model = None
        self._config = None
        self._initialized = False
        self._sample_rate = 22050  # Piper default

    async def _initialize(self):
        if self._initialized:
            return

        try:
            from piper import PiperVoice
            import json

            logger.info(f"Loading Piper TTS voice: {self.voice}")

            model_path = os.path.join(self.model_dir, f"{self.voice}.onnx")
            config_path = os.path.join(self.model_dir, f"{self.voice}.onnx.json")

            # Download if not present
            if not os.path.exists(model_path):
                await self._download_voice(self.voice)

            self._voice_model = PiperVoice.load(model_path, config_path)

            with open(config_path) as f:
                self._config = json.load(f)
            self._sample_rate = self._config.get("audio", {}).get("sample_rate", 22050)

            self._initialized = True
            logger.info("Piper TTS loaded successfully")
        except ImportError:
            logger.error("piper-tts not installed. Install with: pip install piper-tts")
            raise
        except Exception as e:
            logger.error(f"Failed to load Piper TTS: {e}")
            raise

    async def _download_voice(self, voice: str):
        """Download Piper voice model if not present."""
        import urllib.request

        os.makedirs(self.model_dir, exist_ok=True)

        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
        model_url = f"{base_url}/{voice}/{voice}.onnx"
        config_url = f"{base_url}/{voice}/{voice}.onnx.json"

        model_path = os.path.join(self.model_dir, f"{voice}.onnx")
        config_path = os.path.join(self.model_dir, f"{voice}.onnx.json")

        logger.info(f"Downloading Piper voice: {voice}")
        urllib.request.urlretrieve(model_url, model_path)
        urllib.request.urlretrieve(config_url, config_path)
        logger.info("Piper voice downloaded")

    async def synthesize_stream(
        self,
        text_generator: AsyncIterator[str],
    ) -> AsyncIterator[AudioChunk]:
        """Stream synthesize with Piper (synthesizes per-sentence)."""
        await self._initialize()

        text_buffer = ""
        sentence_endings = ('.', '!', '?', '。', '！', '？')

        async for text_chunk in text_generator:
            text_buffer += text_chunk

            while True:
                end_idx = -1
                for ending in sentence_endings:
                    idx = text_buffer.find(ending)
                    if idx != -1:
                        if end_idx == -1 or idx < end_idx:
                            end_idx = idx

                if end_idx == -1:
                    break

                sentence = text_buffer[:end_idx + 1].strip()
                text_buffer = text_buffer[end_idx + 1:]

                if sentence:
                    audio = await self._synthesize_sentence(sentence)
                    yield AudioChunk(
                        audio=audio,
                        sample_rate=self._sample_rate,
                        is_final=False,
                    )

        if text_buffer.strip():
            audio = await self._synthesize_sentence(text_buffer.strip())
            yield AudioChunk(
                audio=audio,
                sample_rate=self._sample_rate,
                is_final=True,
            )
        else:
            yield AudioChunk(
                audio=np.array([], dtype=np.float32),
                sample_rate=self._sample_rate,
                is_final=True,
            )

    async def _synthesize_sentence(self, text: str) -> np.ndarray:
        loop = asyncio.get_event_loop()

        def _generate():
            audio_chunks = []
            for audio_bytes in self._voice_model.synthesize_stream_raw(text):
                audio_chunk = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                audio_chunks.append(audio_chunk)
            if audio_chunks:
                return np.concatenate(audio_chunks)
            return np.array([], dtype=np.float32)

        return await loop.run_in_executor(None, _generate)

    async def synthesize(self, text: str) -> np.ndarray:
        await self._initialize()
        return await self._synthesize_sentence(text)

    async def close(self) -> None:
        self._voice_model = None
        self._initialized = False

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def available_voices(self) -> List[str]:
        # Common Piper voices
        return [
            "en_US-lessac-medium",
            "en_US-lessac-low",
            "en_US-lessac-high",
            "en_US-amy-low",
            "en_US-amy-medium",
            "en_US-joe-medium",
            "en_GB-alan-medium",
            "en_GB-semaine-medium",
        ]


class DummyTTS(TTSEngine):
    """Dummy TTS for testing without audio dependencies."""

    def __init__(self, sample_rate: int = 24000):
        self._sample_rate = sample_rate
        self._initialized = True

    async def synthesize_stream(
        self,
        text_generator: AsyncIterator[str],
    ) -> AsyncIterator[AudioChunk]:
        async for text in text_generator:
            # Generate silence as placeholder
            duration = max(0.5, len(text) * 0.05)  # Rough estimate
            samples = int(self._sample_rate * duration)
            yield AudioChunk(
                audio=np.zeros(samples, dtype=np.float32),
                sample_rate=self._sample_rate,
                is_final=False,
            )
        yield AudioChunk(
            audio=np.array([], dtype=np.float32),
            sample_rate=self._sample_rate,
            is_final=True,
        )

    async def synthesize(self, text: str) -> np.ndarray:
        duration = max(0.5, len(text) * 0.05)
        samples = int(self._sample_rate * duration)
        return np.zeros(samples, dtype=np.float32)

    async def close(self) -> None:
        pass

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def available_voices(self) -> List[str]:
        return ["dummy"]


def create_tts_engine(
    engine: str = "kokoro",
    voice: str = "af_heart",
    speed: float = 1.0,
    device: str = "auto",
    model_dir: Optional[str] = None,
    # Stack B (Chatterbox) parameters
    voice_stack: str = "stack_a",
    chatterbox_grpc_endpoint: Optional[str] = None,
    chatterbox_voice: Optional[str] = None,
    chatterbox_language: Optional[str] = None,
    chatterbox_emotion_exaggeration: Optional[float] = None,
    chatterbox_use_ssl: bool = False,
    chatterbox_metadata: Optional[list] = None,
) -> TTSEngine:
    """
    Factory function to create TTS engine for either stack.

    Args:
        engine: Engine name ("kokoro", "piper", "dummy", "chatterbox")
        voice: Voice name (Stack A)
        speed: Speech speed (Stack A)
        device: Device for inference (Stack A)
        model_dir: Model directory for Piper (Stack A)
        voice_stack: "stack_a" (local) or "stack_b" (NVIDIA NIM)
        chatterbox_grpc_endpoint: Chatterbox TTS gRPC endpoint (Stack B)
        chatterbox_voice: Chatterbox voice name (Stack B)
        chatterbox_language: Chatterbox language code (Stack B)
        chatterbox_emotion_exaggeration: Emotion exaggeration 0.0-1.0 (Stack B)
        chatterbox_use_ssl: Use SSL for Chatterbox gRPC (Stack B)
        chatterbox_metadata: Auth metadata for Chatterbox (Stack B)

    Returns:
        TTSEngine instance
    """
    # Stack B: Chatterbox TTS NIM
    if voice_stack == "stack_b" or engine == "chatterbox":
        from .tts_chatterbox import create_chatterbox_tts_engine
        return create_chatterbox_tts_engine(
            grpc_endpoint=chatterbox_grpc_endpoint,
            voice_name=chatterbox_voice or voice,
            language_code=chatterbox_language,
            emotion_exaggeration=chatterbox_emotion_exaggeration,
            use_ssl=chatterbox_use_ssl,
            metadata=chatterbox_metadata,
        )

    # Stack A: Local engines (default)
    if engine == "kokoro":
        return KokoroTTS(voice=voice, speed=speed, device=device)
    elif engine == "piper":
        return PiperTTS(voice=voice, model_dir=model_dir)
    elif engine == "dummy":
        return DummyTTS()

    raise ValueError(f"Unknown TTS engine: {engine} for stack: {voice_stack}")