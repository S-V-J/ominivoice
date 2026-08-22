"""
OminiVoice Voice Engine Package.
Real-time voice pipeline with STT, VAD, TTS, and LLM integration.
"""
from .stt import (
    STTEngine,
    TranscriptSegment,
    FasterWhisperSTT,
    StreamingFasterWhisperSTT,
    create_stt_engine,
)

from .turn_detection import (
    VADBase,
    SileroVAD,
    TurnDetector,
    VADResult,
    TurnResult,
    VADState,
    create_turn_detector,
)

from .tts import (
    TTSEngine,
    AudioChunk,
    KokoroTTS,
    PiperTTS,
    DummyTTS,
    create_tts_engine,
)

from .pipeline import (
    VoicePipeline,
    PipelineConfig,
    PipelineState,
    TurnLog,
    PipelineFactory,
)

from .prompt_builder import (
    AgentPromptConfig,
    AgentDirection,
    build_system_prompt,
    build_outbound_prompt,
    build_inbound_prompt,
    get_completeness_report,
    create_config_from_agent,
)

from .telephony_adapter import (
    TelephonyAdapter,
    SimulatedCallAdapter,
    BrowserSimulatedCallSession,
    CallSession,
    create_telephony_adapter,
)

__version__ = "1.0.0"

__all__ = [
    # STT
    "STTEngine",
    "TranscriptSegment",
    "FasterWhisperSTT",
    "StreamingFasterWhisperSTT",
    "create_stt_engine",
    # Turn Detection
    "VADBase",
    "SileroVAD",
    "TurnDetector",
    "VADResult",
    "TurnResult",
    "VADState",
    "create_turn_detector",
    # TTS
    "TTSEngine",
    "AudioChunk",
    "KokoroTTS",
    "PiperTTS",
    "DummyTTS",
    "create_tts_engine",
    # Pipeline
    "VoicePipeline",
    "PipelineConfig",
    "PipelineState",
    "TurnLog",
    "PipelineFactory",
    # Prompt Builder
    "AgentPromptConfig",
    "AgentDirection",
    "build_system_prompt",
    "build_outbound_prompt",
    "build_inbound_prompt",
    "get_completeness_report",
    "create_config_from_agent",
    # Telephony
    "TelephonyAdapter",
    "SimulatedCallAdapter",
    "BrowserSimulatedCallSession",
    "CallSession",
    "create_telephony_adapter",
]