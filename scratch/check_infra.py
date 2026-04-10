import asyncio
import redis.asyncio as redis
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

async def check_redis():
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        await r.ping()
        print("Redis: OK")
    except Exception as e:
        print(f"Redis: FAILED ({e})")

async def check_neo4j():
    try:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j_password")
        async with AsyncGraphDatabase.driver(uri, auth=(user, password)) as driver:
            await driver.verify_connectivity()
        print("Neo4j: OK")
    except Exception as e:
        print(f"Neo4j: FAILED ({e})")

async def main():
    await check_redis()
    await check_neo4j()

if __name__ == "__main__":
    asyncio.run(main())
