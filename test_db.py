import asyncio
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    engine = create_async_engine("postgresql+asyncpg://ominivoice:changeme@postgres:5432/ominivoice")
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        print(result.scalar())
    await engine.dispose()

asyncio.run(test())
