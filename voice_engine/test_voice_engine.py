"""
Test script for voice engine components.
Run with: python -m voice_engine.test_voice_engine
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_stt():
    """Test STT engine initialization."""
    logger.info("Testing STT engine...")
    from voice_engine.stt import create_stt_engine

    try:
        stt = create_stt_engine(engine="faster-whisper", model_size="tiny", streaming=True)
        await stt._initialize()
        logger.info("STT engine initialized successfully")
        await stt.close()
        return True
    except Exception as e:
        logger.error(f"STT test failed: {e}")
        return False


async def test_vad():
    """Test VAD and turn detection."""
    logger.info("Testing VAD...")
    from voice_engine.turn_detection import create_turn_detector

    try:
        detector = create_turn_detector(sensitivity="medium")
        await detector.vad._initialize()
        logger.info("VAD initialized successfully")
        await detector.reset()
        return True
    except Exception as e:
        logger.error(f"VAD test failed: {e}")
        return False


async def test_tts():
    """Test TTS engine initialization."""
    logger.info("Testing TTS engine...")
    from voice_engine.tts import create_tts_engine

    try:
        # Use dummy TTS for testing without models
        tts = create_tts_engine(engine="dummy")
        logger.info("Dummy TTS initialized successfully")
        await tts.close()
        return True
    except Exception as e:
        logger.error(f"TTS test failed: {e}")
        return False


async def test_prompt_builder():
    """Test prompt builder."""
    logger.info("Testing prompt builder...")
    from voice_engine.prompt_builder import (
        AgentPromptConfig,
        AgentDirection,
        build_system_prompt,
        get_completeness_report,
    )

    try:
        config = AgentPromptConfig(
            system_prompt="You are a helpful assistant.",
            opening_line="Hello! How can I help?",
            objective_prompt="Solve the user's problem.",
            objection_handling_prompt="Handle objections gracefully.",
            voicemail_prompt="Please leave a message.",
            closing_prompt="Thank you for calling!",
            escalation_rule="Escalate if needed.",
            interruption_sensitivity="medium",
        )

        # Test outbound prompt
        prompt = build_system_prompt(config, AgentDirection.OUTBOUND)
        logger.info(f"Outbound prompt length: {len(prompt)} chars")

        # Test inbound prompt
        config.greeting_prompt = "Welcome!"
        config.qualification_prompt = "What do you need?"
        config.knowledge_prompt = "I know things."
        config.fallback_prompt = "I don't know."
        config.handoff_prompt = "Transferring..."

        prompt = build_system_prompt(config, AgentDirection.INBOUND)
        logger.info(f"Inbound prompt length: {len(prompt)} chars")

        # Test completeness
        report = get_completeness_report(config, AgentDirection.OUTBOUND)
        logger.info(f"Completeness: {report['percentage']}%")

        return True
    except Exception as e:
        logger.error(f"Prompt builder test failed: {e}")
        return False


async def test_pipeline():
    """Test pipeline initialization."""
    logger.info("Testing pipeline...")
    from voice_engine.pipeline import VoicePipeline, PipelineConfig, PipelineFactory

    try:
        # Use dummy factory
        async def dummy_factory(provider, model):
            class DummyProvider:
                async def stream_reply(self, messages, **kwargs):
                    yield "Test response. "
                    yield "This is a dummy LLM. "
                async def close(self):
                    pass
            return DummyProvider()

        config = PipelineConfig(
            stt_engine="faster-whisper",
            stt_model_size="tiny",
            tts_engine="dummy",
            llm_provider="dummy",
            llm_model="dummy",
        )

        pipeline = VoicePipeline(config=config, llm_provider_factory=dummy_factory)
        await pipeline.initialize()
        logger.info("Pipeline initialized successfully")

        # Test starting a call
        await pipeline.start_call("Test system prompt")
        logger.info(f"Pipeline state: {pipeline.state}")

        await pipeline.stop_call()
        logger.info("Pipeline stopped")
        return True
    except Exception as e:
        logger.error(f"Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_telephony_adapter():
    """Test telephony adapter."""
    logger.info("Testing telephony adapter...")
    from voice_engine.telephony_adapter import create_telephony_adapter, SimulatedCallAdapter
    from voice_engine.prompt_builder import AgentPromptConfig, AgentDirection

    try:
        async def dummy_factory(provider, model):
            class DummyProvider:
                async def stream_reply(self, messages, **kwargs):
                    yield "Test response. "
                async def close(self):
                    pass
            return DummyProvider()

        adapter = create_telephony_adapter("simulated", llm_provider_factory=dummy_factory)
        logger.info("Telephony adapter created")

        config = AgentPromptConfig(
            system_prompt="Test prompt",
            opening_line="Hello",
            tts_engine="dummy",
        )

        session = await adapter.start_call(
            agent_config=config,
            direction=AgentDirection.OUTBOUND,
            on_audio_output=lambda x: None,
            on_transcript=lambda x: None,
            on_state_change=lambda x: None,
            on_call_end=lambda x: None,
        )
        logger.info(f"Session started: {session.session_id}")

        await adapter.end_call(session.session_id)
        logger.info("Session ended")
        return True
    except Exception as e:
        logger.error(f"Telephony adapter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests."""
    tests = [
        ("STT", test_stt),
        ("VAD", test_vad),
        ("TTS", test_tts),
        ("Prompt Builder", test_prompt_builder),
        ("Pipeline", test_pipeline),
        ("Telephony Adapter", test_telephony_adapter),
    ]

    results = []
    for name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {name} test...")
        try:
            result = await test_func()
            results.append((name, result))
            logger.info(f"{name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"{name}: ERROR - {e}")
            results.append((name, False))

    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status} - {name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)