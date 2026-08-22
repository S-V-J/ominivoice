"""
Pytest configuration and fixtures for OminiVoice tests.
"""
import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import User, Agent, AgentDirection, AgentStatus, VoiceStack, ApiKey, CallLog, CallStatus, CallDirection, ColdCallQueueEntry, QueueEntryStatus, Subscription, SubscriptionStatus, UserPlan, AgentPromptVersion

# Override database URL for testing
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ominivoice_test")

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestAsyncSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden database dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from app.core.security import get_password_hash

    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        plan=UserPlan.FREE,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """Create a second test user for isolation tests."""
    from app.core.security import get_password_hash

    user = User(
        email="test2@example.com",
        hashed_password=get_password_hash("testpassword123"),
        plan=UserPlan.FREE,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """Get auth headers for test user."""
    response = await client.post("/auth/login", json={
        "email": test_user.email,
        "password": "testpassword123",
    })
    assert response.status_code == 200
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest_asyncio.fixture
async def test_agent(db_session: AsyncSession, test_user: User) -> Agent:
    """Create a test agent."""
    agent = Agent(
        owner_id=test_user.id,
        name="Test Agent",
        direction=AgentDirection.OUTBOUND,
        status=AgentStatus.DRAFT,
        voice_stack=VoiceStack.STACK_A,
        system_prompt="You are a helpful assistant.",
        opening_line="Hello, this is a test call.",
        objective_prompt="Schedule a demo.",
        llm_provider="nvidia_integrate",
        llm_model="stepfun-ai/step-3.7-flash",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_inbound_agent(db_session: AsyncSession, test_user: User) -> Agent:
    """Create a test inbound agent."""
    agent = Agent(
        owner_id=test_user.id,
        name="Test Inbound Agent",
        direction=AgentDirection.INBOUND,
        status=AgentStatus.DRAFT,
        voice_stack=VoiceStack.STACK_A,
        system_prompt="You are a helpful support agent.",
        greeting_prompt="Hello! How can I help you?",
        qualification_prompt="What is your issue?",
        llm_provider="nvidia_integrate",
        llm_model="stepfun-ai/step-3.7-flash",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent