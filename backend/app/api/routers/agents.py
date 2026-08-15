"""
Agent management API routes.
Handles CRUD operations for voice agents, prompt configuration, and completeness checking.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_agent, get_db
from app.models import Agent, AgentPromptVersion, AgentStatus, AgentDirection, User
from app.schemas.schemas import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentCompletenessResponse,
    AgentPromptVersionResponse,
    AgentPromptFields,
)

router = APIRouter()


# Required prompt fields per direction
REQUIRED_FIELDS = {
    AgentDirection.OUTBOUND: [
        "system_prompt",
        "opening_line",
        "objective_prompt",
        "objection_handling_prompt",
        "voicemail_prompt",
        "closing_prompt",
        "escalation_rule",
    ],
    AgentDirection.INBOUND: [
        "system_prompt",
        "greeting_prompt",
        "qualification_prompt",
        "knowledge_prompt",
        "fallback_prompt",
        "handoff_prompt",
    ],
}


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_in: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """
    Create a new voice agent.

    - **name**: Agent name
    - **direction**: inbound or outbound
    - All prompt fields are optional (for drafts)
    """
    agent = Agent(
        owner_id=current_user.id,
        name=agent_in.name,
        direction=agent_in.direction,
        status=AgentStatus.DRAFT,
        # Engine config
        stt_engine=agent_in.stt_engine.value if agent_in.stt_engine else "faster-whisper",
        tts_engine=agent_in.tts_engine.value if agent_in.tts_engine else "kokoro",
        tts_voice=agent_in.tts_voice or "af_heart",
        language=agent_in.language or "en-US",
        # LLM config
        llm_provider=agent_in.llm_provider.value if agent_in.llm_provider else "ollama_local",
        llm_model=agent_in.llm_model or "qwen3:4b",
        # Prompts (all nullable)
        system_prompt=agent_in.system_prompt,
        interruption_sensitivity=agent_in.interruption_sensitivity.value if agent_in.interruption_sensitivity else "medium",
        max_call_duration_s=agent_in.max_call_duration_s or 300,
        silence_timeout_s=agent_in.silence_timeout_s or 10,
        # Outbound prompts
        opening_line=agent_in.opening_line,
        objective_prompt=agent_in.objective_prompt,
        objection_handling_prompt=agent_in.objection_handling_prompt,
        voicemail_prompt=agent_in.voicemail_prompt,
        closing_prompt=agent_in.closing_prompt,
        escalation_rule=agent_in.escalation_rule,
        # Inbound prompts
        greeting_prompt=agent_in.greeting_prompt,
        qualification_prompt=agent_in.qualification_prompt,
        knowledge_prompt=agent_in.knowledge_prompt,
        fallback_prompt=agent_in.fallback_prompt,
        handoff_prompt=agent_in.handoff_prompt,
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return await _build_agent_response(db, agent)


@router.get("", response_model=List[AgentListResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[AgentStatus] = Query(None, alias="status"),
    direction_filter: Optional[AgentDirection] = Query(None, alias="direction"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[AgentListResponse]:
    """
    List all agents for the current user.

    Supports filtering by status and direction.
    """
    query = select(Agent).where(Agent.owner_id == current_user.id)

    if status_filter:
        query = query.where(Agent.status == status_filter)
    if direction_filter:
        query = query.where(Agent.direction == direction_filter)

    query = query.order_by(Agent.updated_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    agents = result.scalars().all()

    # Get last test call date and completeness for each agent
    agent_responses = []
    for agent in agents:
        completeness = await _calculate_completeness(agent)
        agent_responses.append(AgentListResponse(
            id=agent.id,
            name=agent.name,
            direction=agent.direction,
            status=agent.status,
            completeness_percentage=completeness["completion_percentage"],
            last_test_call_at=None,  # TODO: Add from CallLog
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        ))

    return agent_responses


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """
    Get a specific agent by ID.
    Only returns agents owned by the current user.
    """
    return await _build_agent_response(db, agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_in: AgentUpdate,
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """
    Update an agent's configuration.

    Tracks prompt field changes in AgentPromptVersion for history.
    """
    update_data = agent_in.model_dump(exclude_unset=True)

    # Track prompt field changes for version history
    prompt_fields = [
        "system_prompt", "interruption_sensitivity", "max_call_duration_s",
        "silence_timeout_s", "stt_engine", "tts_engine", "tts_voice",
        "language", "llm_provider", "llm_model",
        "opening_line", "objective_prompt", "objection_handling_prompt",
        "voicemail_prompt", "closing_prompt", "escalation_rule",
        "greeting_prompt", "qualification_prompt", "knowledge_prompt",
        "fallback_prompt", "handoff_prompt",
    ]

    for field in prompt_fields:
        if field in update_data and update_data[field] is not None:
            old_value = getattr(agent, field)
            new_value = update_data[field]

            # Convert enum values to strings for storage
            if hasattr(new_value, 'value'):
                new_value = new_value.value

            if old_value != new_value:
                # Create version record
                version = AgentPromptVersion(
                    agent_id=agent.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=new_value,
                )
                db.add(version)

    # Apply updates
    for field, value in update_data.items():
        if value is not None:
            # Convert enum values to strings
            if hasattr(value, 'value'):
                value = value.value
            setattr(agent, field, value)

    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)

    return await _build_agent_response(db, agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an agent and all associated data (API keys, call logs, queue entries).
    """
    await db.delete(agent)
    await db.commit()


@router.get("/{agent_id}/completeness", response_model=AgentCompletenessResponse)
async def get_agent_completeness(
    agent: Agent = Depends(get_owned_agent),
) -> AgentCompletenessResponse:
    """
    Check which required prompt fields are still empty for an agent.

    Returns completeness percentage and list of missing required fields
    based on the agent's direction (inbound/outbound).
    """
    completeness = await _calculate_completeness(agent)
    return AgentCompletenessResponse(
        agent_id=agent.id,
        direction=agent.direction,
        is_complete=completeness["is_complete"],
        missing_required_fields=completeness["missing_required_fields"],
        field_status=completeness["field_status"],
        completion_percentage=completeness["completion_percentage"],
    )


@router.get("/{agent_id}/prompt-versions", response_model=List[AgentPromptVersionResponse])
async def get_prompt_versions(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    field_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> List[AgentPromptVersionResponse]:
    """
    Get version history for agent prompt fields.

    Optionally filter by field_name.
    """
    query = select(AgentPromptVersion).where(AgentPromptVersion.agent_id == agent.id)

    if field_name:
        query = query.where(AgentPromptVersion.field_name == field_name)

    query = query.order_by(AgentPromptVersion.edited_at.desc()).limit(limit)

    result = await db.execute(query)
    versions = result.scalars().all()

    return [
        AgentPromptVersionResponse(
            id=v.id,
            agent_id=v.agent_id,
            field_name=v.field_name,
            old_value=v.old_value,
            new_value=v.new_value,
            edited_at=v.edited_at,
        )
        for v in versions
    ]


@router.post("/{agent_id}/rewrite-prompt", response_model=dict)
async def rewrite_prompt(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    field_name: str = Query(..., description="Prompt field to rewrite"),
    current_text: str = Query(..., description="Current prompt text"),
    instruction: Optional[str] = Query(None, description="Additional instruction for rewrite"),
) -> dict:
    """
    Rewrite a prompt field using AI.

    Calls the configured LLM provider with a meta-prompt to improve the prompt.
    Returns the rewritten text as a suggestion (does not auto-save).
    """
    # Validate field name
    valid_fields = [
        "system_prompt", "opening_line", "objective_prompt", "objection_handling_prompt",
        "voicemail_prompt", "closing_prompt", "escalation_rule",
        "greeting_prompt", "qualification_prompt", "knowledge_prompt",
        "fallback_prompt", "handoff_prompt",
    ]

    if field_name not in valid_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid field name. Must be one of: {', '.join(valid_fields)}"
        )

    # Get the agent's LLM provider
    from app.services.llm_service import get_llm_provider, LLMProviderError

    try:
        provider = get_llm_provider(agent.llm_provider, agent.llm_model)
    except LLMProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM provider error: {str(e)}"
        )

    # Build meta-prompt for rewriting
    meta_prompt = f"""You are a prompt engineer specializing in voice agent prompts.
Rewrite the following {field_name} prompt to be clearer, more concise, and more effective for a natural-sounding phone conversation.
Preserve the original intent. Return only the rewritten prompt, no preamble or explanation.

Original prompt:
{current_text}

{f"Additional instruction: {instruction}" if instruction else ""}"""

    try:
        rewritten = await provider.generate_text(meta_prompt, temperature=0.7)
        return {
            "field_name": field_name,
            "original": current_text,
            "rewritten": rewritten.strip(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rewrite prompt: {str(e)}"
        )


# Helper functions

async def _build_agent_response(db: AsyncSession, agent: Agent) -> AgentResponse:
    """Build full agent response with all fields."""
    # Get prompt version count for each field
    version_counts = {}
    for field in [
        "system_prompt", "opening_line", "objective_prompt", "objection_handling_prompt",
        "voicemail_prompt", "closing_prompt", "escalation_rule",
        "greeting_prompt", "qualification_prompt", "knowledge_prompt",
        "fallback_prompt", "handoff_prompt",
    ]:
        result = await db.execute(
            select(func.count(AgentPromptVersion.id)).where(
                AgentPromptVersion.agent_id == agent.id,
                AgentPromptVersion.field_name == field
            )
        )
        version_counts[field] = result.scalar() or 0

    return AgentResponse(
        id=agent.id,
        owner_id=agent.owner_id,
        name=agent.name,
        direction=agent.direction,
        status=agent.status,
        # Engine config
        stt_engine=agent.stt_engine,
        tts_engine=agent.tts_engine,
        tts_voice=agent.tts_voice,
        language=agent.language,
        # LLM config
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        # Prompts
        system_prompt=agent.system_prompt,
        interruption_sensitivity=agent.interruption_sensitivity,
        max_call_duration_s=agent.max_call_duration_s,
        silence_timeout_s=agent.silence_timeout_s,
        opening_line=agent.opening_line,
        objective_prompt=agent.objective_prompt,
        objection_handling_prompt=agent.objection_handling_prompt,
        voicemail_prompt=agent.voicemail_prompt,
        closing_prompt=agent.closing_prompt,
        escalation_rule=agent.escalation_rule,
        greeting_prompt=agent.greeting_prompt,
        qualification_prompt=agent.qualification_prompt,
        knowledge_prompt=agent.knowledge_prompt,
        fallback_prompt=agent.fallback_prompt,
        handoff_prompt=agent.handoff_prompt,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        completeness_percentage=version_counts.get("system_prompt", 0) * 10,  # Placeholder
    )


async def _calculate_completeness(agent: Agent) -> dict:
    """Calculate completeness for an agent based on required fields."""
    required = REQUIRED_FIELDS.get(agent.direction, [])

    field_status = {}
    missing = []

    for field in required:
        value = getattr(agent, field, None)
        is_filled = bool(value and value.strip())
        field_status[field] = is_filled
        if not is_filled:
            missing.append(field)

    # Also check optional but recommended fields
    optional_fields = [
        "interruption_sensitivity", "max_call_duration_s", "silence_timeout_s",
        "stt_engine", "tts_engine", "tts_voice", "language",
        "llm_provider", "llm_model",
    ]
    for field in optional_fields:
        value = getattr(agent, field, None)
        field_status[field] = bool(value)

    total_fields = len(required) + len(optional_fields)
    filled_fields = sum(1 for v in field_status.values() if v)
    completion_percentage = int((filled_fields / total_fields) * 100) if total_fields > 0 else 0

    return {
        "is_complete": len(missing) == 0,
        "missing_required_fields": missing,
        "field_status": field_status,
        "completion_percentage": completion_percentage,
    }