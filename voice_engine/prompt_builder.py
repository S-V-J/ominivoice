"""
Direction-aware system prompt assembly for voice agents.
Builds structured system prompts from agent configuration fields.
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AgentDirection(str, Enum):
    """Agent direction types."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass
class AgentPromptConfig:
    """Agent prompt configuration fields."""

    # Agent identifier
    agent_id: str = ""

    # Voice stack selection
    voice_stack: str = "stack_a"  # "stack_a" (local) or "stack_b" (NVIDIA NIM)

    # Shared fields
    system_prompt: Optional[str] = None
    interruption_sensitivity: str = "medium"
    max_call_duration_s: int = 300
    silence_timeout_s: float = 30.0
    language: str = "en"
    stt_engine: str = "faster-whisper"
    tts_engine: str = "kokoro"
    tts_voice: str = "af_heart"
    llm_provider: str = "nvidia_integrate"
    llm_model: str = "stepfun-ai/step-3.7-flash"

    # Stack B (NVIDIA NIM) specific fields
    chatterbox_voice: str = "Chatterbox-Multilingual.en-US.Female"
    chatterbox_emotion_exaggeration: float = 0.5
    riva_asr_language: str = "en-US"
    riva_vad_threshold: float = 0.5

    # Outbound-specific fields
    opening_line: Optional[str] = None
    objective_prompt: Optional[str] = None
    objection_handling_prompt: Optional[str] = None
    voicemail_prompt: Optional[str] = None
    closing_prompt: Optional[str] = None
    escalation_rule: Optional[str] = None

    # Inbound-specific fields
    greeting_prompt: Optional[str] = None
    qualification_prompt: Optional[str] = None
    knowledge_prompt: Optional[str] = None
    fallback_prompt: Optional[str] = None
    handoff_prompt: Optional[str] = None


# Section templates for structured prompts
OUTBOUND_SECTIONS = [
    ("SYSTEM PROMPT (Persona & Rules)", "system_prompt"),
    ("OPENING LINE", "opening_line"),
    ("CALL OBJECTIVE", "objective_prompt"),
    ("OBJECTION HANDLING", "objection_handling_prompt"),
    ("VOICEMAIL HANDLING", "voicemail_prompt"),
    ("CLOSING", "closing_prompt"),
    ("ESCALATION RULE", "escalation_rule"),
]

INBOUND_SECTIONS = [
    ("SYSTEM PROMPT (Persona & Rules)", "system_prompt"),
    ("GREETING", "greeting_prompt"),
    ("QUALIFICATION QUESTIONS", "qualification_prompt"),
    ("KNOWLEDGE BASE", "knowledge_prompt"),
    ("FALLBACK RESPONSE", "fallback_prompt"),
    ("HANDOFF PROCEDURE", "handoff_prompt"),
]

SHARED_SECTIONS = [
    ("INTERRUPTION SENSITIVITY", "interruption_sensitivity"),
    ("MAX CALL DURATION", "max_call_duration_s"),
    ("LANGUAGE", "language"),
]


def build_system_prompt(
    config: AgentPromptConfig,
    direction: AgentDirection,
    include_shared: bool = True,
) -> str:
    """
    Build a complete system prompt from agent configuration.

    Args:
        config: Agent prompt configuration
        direction: Agent direction (inbound/outbound)
        include_shared: Whether to include shared config fields

    Returns:
        Formatted system prompt string
    """
    sections = []

    # Add direction-specific sections
    if direction == AgentDirection.OUTBOUND:
        sections.extend(_build_sections(config, OUTBOUND_SECTIONS))
    else:
        sections.extend(_build_sections(config, INBOUND_SECTIONS))

    # Add shared configuration
    if include_shared:
        sections.extend(_build_shared_sections(config))

    # Combine with clear delimiters
    prompt = "\n\n".join(sections)

    # Add meta-instructions for voice conversation
    prompt += _get_voice_meta_instructions(direction)

    return prompt.strip()


def _build_sections(config: AgentPromptConfig, section_defs: List[tuple]) -> List[str]:
    """Build prompt sections from config fields."""
    sections = []
    for section_title, field_name in section_defs:
        value = getattr(config, field_name, None)
        if value and str(value).strip():
            sections.append(f"=== {section_title} ===\n{value.strip()}")
        else:
            sections.append(f"=== {section_title} ===\n[NOT CONFIGURED]")
    return sections


def _build_shared_sections(config: AgentPromptConfig) -> List[str]:
    """Build shared configuration sections."""
    sections = []

    # Interruption sensitivity
    sensitivity = config.interruption_sensitivity or "medium"
    sensitivity_desc = {
        "high": "High - Allow frequent interruptions, very responsive",
        "medium": "Medium - Balanced interruption handling",
        "low": "Low - Wait for clear pauses before responding",
    }.get(sensitivity, "Medium")
    sections.append(f"=== INTERRUPTION SENSITIVITY ===\n{sensitivity_desc}")

    # Max call duration
    max_duration = config.max_call_duration_s or 300
    sections.append(f"=== MAX CALL DURATION ===\n{max_duration} seconds")

    # Language
    language = config.language or "en"
    sections.append(f"=== LANGUAGE ===\n{language}")

    return sections


def _get_voice_meta_instructions(direction: AgentDirection) -> str:
    """Get meta-instructions for voice conversation behavior."""
    base_instructions = """
=== VOICE CONVERSATION INSTRUCTIONS ===
- You are speaking on a phone call. Keep responses natural and conversational.
- Use short sentences. Avoid long monologues. Pause to let the other person speak.
- Never say "As an AI" or mention you are an AI. You are the agent persona defined above.
- If you don't know something, use your fallback/handoff procedure.
- Handle interruptions gracefully - stop speaking immediately when the user interrupts.
- Match the user's energy and speaking pace.
- Use natural filler words sparingly (um, uh, well) to sound human.
- Always confirm understanding before proceeding.
"""

    if direction == AgentDirection.OUTBOUND:
        base_instructions += """
=== OUTBOUND CALL SPECIFIC ===
- You initiated this call. State your opening line immediately when the call connects.
- If you reach voicemail, deliver the voicemail prompt and hang up.
- Drive the conversation toward your objective.
- Handle objections using the objection handling framework.
- If the user asks for a human or meets escalation criteria, follow the escalation rule.
- End with the closing prompt and clear next steps.
"""
    else:
        base_instructions += """
=== INBOUND CALL SPECIFIC ===
- The caller initiated this call. Start with your greeting.
- Qualify the caller's intent using your qualification questions.
- Answer questions from your knowledge base.
- If unsure, use the fallback response.
- If the caller needs human assistance, follow the handoff procedure.
"""

    return base_instructions


def build_outbound_prompt(config: AgentPromptConfig) -> str:
    """Build system prompt for outbound agent."""
    return build_system_prompt(config, AgentDirection.OUTBOUND)


def build_inbound_prompt(config: AgentPromptConfig) -> str:
    """Build system prompt for inbound agent."""
    return build_system_prompt(config, AgentDirection.INBOUND)


def get_completeness_report(config: AgentPromptConfig, direction: AgentDirection) -> Dict[str, Any]:
    """
    Get a completeness report for the agent configuration.

    Returns:
        Dict with required fields, filled fields, missing fields, and completion percentage
    """
    if direction == AgentDirection.OUTBOUND:
        required_fields = [
            "system_prompt",
            "opening_line",
            "objective_prompt",
            "objection_handling_prompt",
            "voicemail_prompt",
            "closing_prompt",
            "escalation_rule",
        ]
    else:
        required_fields = [
            "system_prompt",
            "greeting_prompt",
            "qualification_prompt",
            "knowledge_prompt",
            "fallback_prompt",
            "handoff_prompt",
        ]

    filled = []
    missing = []

    for field in required_fields:
        value = getattr(config, field, None)
        if value and str(value).strip():
            filled.append(field)
        else:
            missing.append(field)

    total = len(required_fields)
    filled_count = len(filled)
    percentage = int((filled_count / total) * 100) if total > 0 else 0

    return {
        "direction": direction.value,
        "total_required": total,
        "filled": filled_count,
        "missing": total - filled_count,
        "percentage": percentage,
        "filled_fields": filled,
        "missing_fields": missing,
        "is_complete": filled_count == total,
    }


def create_config_from_agent(agent) -> AgentPromptConfig:
    """
    Create AgentPromptConfig from an Agent database model.

    Args:
        agent: Agent SQLAlchemy model instance

    Returns:
        AgentPromptConfig populated from agent fields
    """
    # Get voice stack (default to stack_a for backwards compatibility)
    voice_stack = getattr(agent, 'voice_stack', None)
    if voice_stack and hasattr(voice_stack, 'value'):
        voice_stack = voice_stack.value
    voice_stack = voice_stack or "stack_a"

    # Handle integer percentage fields from DB (0-100)
    chatterbox_emotion = getattr(agent, 'chatterbox_emotion_exaggeration', 50)
    if chatterbox_emotion > 1:  # Stored as integer percentage
        chatterbox_emotion = chatterbox_emotion / 100.0

    riva_vad_threshold = getattr(agent, 'riva_vad_threshold', 50)
    if riva_vad_threshold > 1:
        riva_vad_threshold = riva_vad_threshold / 100.0

    return AgentPromptConfig(
        voice_stack=voice_stack,
        system_prompt=agent.system_prompt,
        interruption_sensitivity=agent.interruption_sensitivity,
        max_call_duration_s=agent.max_call_duration_s,
        silence_timeout_s=agent.silence_timeout_s,
        language=agent.language,
        stt_engine=agent.stt_engine,
        tts_engine=agent.tts_engine,
        tts_voice=agent.tts_voice,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        # Stack B fields
        chatterbox_voice=getattr(agent, 'chatterbox_voice', "Chatterbox-Multilingual.en-US.Female"),
        chatterbox_emotion_exaggeration=chatterbox_emotion,
        riva_asr_language=getattr(agent, 'riva_asr_language', "en-US"),
        riva_vad_threshold=riva_vad_threshold,
        # Outbound
        opening_line=agent.opening_line,
        objective_prompt=agent.objective_prompt,
        objection_handling_prompt=agent.objection_handling_prompt,
        voicemail_prompt=agent.voicemail_prompt,
        closing_prompt=agent.closing_prompt,
        escalation_rule=agent.escalation_rule,
        # Inbound
        greeting_prompt=agent.greeting_prompt,
        qualification_prompt=agent.qualification_prompt,
        knowledge_prompt=agent.knowledge_prompt,
        fallback_prompt=agent.fallback_prompt,
        handoff_prompt=agent.handoff_prompt,
    )


# Example usage and testing
if __name__ == "__main__":
    # Test with sample config
    config = AgentPromptConfig(
        system_prompt="You are Sarah, a friendly sales representative for Acme Corp. You're professional but warm.",
        opening_line="Hi, this is Sarah from Acme Corp. I'm calling because we have a special offer on our new product line that I think you'd be interested in. Do you have a moment?",
        objective_prompt="Schedule a 15-minute demo call with the decision maker.",
        objection_handling_prompt="If they say 'not interested': 'I understand. Many of our current customers felt the same way before seeing the demo. It only takes 15 minutes and there's no obligation.' If they say 'too busy': 'I completely get it. When would be a better time this week?'",
        voicemail_prompt="Hi, this is Sarah from Acme Corp. We have a special offer I'd love to share. Please call me back at 555-0123. Thanks!",
        closing_prompt="Great! I'll send a calendar invite for the demo. What's the best email to use?",
        escalation_rule="If the prospect asks to speak to a manager or mentions legal/compliance concerns, say 'I'll have my manager reach out within 24 hours' and end the call.",
        interruption_sensitivity="medium",
        max_call_duration_s=300,
        language="en",
    )

    prompt = build_outbound_prompt(config)
    print("=== OUTBOUND PROMPT ===")
    print(prompt)
    print("\n" + "="*50)

    report = get_completeness_report(config, AgentDirection.OUTBOUND)
    print("=== COMPLETENESS REPORT ===")
    print(f"Complete: {report['is_complete']} ({report['percentage']}%)")
    print(f"Missing: {report['missing_fields']}")