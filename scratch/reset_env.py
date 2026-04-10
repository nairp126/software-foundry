import asyncio
import redis.asyncio as redis
from neo4j import AsyncGraphDatabase
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

async def reset_neo4j():
    print("Resetting Neo4j...")
    try:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j_password")
        async with AsyncGraphDatabase.driver(uri, auth=(user, password)) as driver:
            async with driver.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")
        print("Neo4j: Cleared")
    except Exception as e:
        print(f"Neo4j Reset Failed: {e}")

async def reset_redis():
    print("Resetting Redis...")
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        await r.flushall()
        print("Redis: Cleared")
    except Exception as e:
        print(f"Redis Reset Failed: {e}")

def reset_db_and_files():
    print("Resetting SQLite and Generated Files...")
    db_path = "foundry.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("SQLite: Deleted")
    
    gen_dir = "generated_projects"
    if os.path.exists(gen_dir):
        shutil.rmtree(gen_dir)
        os.makedirs(gen_dir)
        print("Generated Projects: Wiped")

async def main():
    await reset_neo4j()
    await reset_redis()
    reset_db_and_files()

if __name__ == "__main__":
    asyncio.run(main())
