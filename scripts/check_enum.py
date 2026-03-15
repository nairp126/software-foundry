import asyncio
from sqlalchemy import text
from foundry.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

async def check():
    url = settings.database_url.replace("foundry_db", "foundry_db_test").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT unnest(enum_range(NULL::artifact_type))::text"))
        rows = result.fetchall()
        print("artifact_type values:", [r[0] for r in rows])
    await engine.dispose()

asyncio.run(check())
