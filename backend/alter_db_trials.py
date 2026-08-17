import asyncio
import os
import sys

sys.path.append(os.path.dirname(__file__))

from app.db.database import get_db, AsyncSessionLocal
from sqlalchemy import text

async def alter_table():
    print("Altering table for trial claims...")
    async with AsyncSessionLocal() as db:
        queries = [
            """
            CREATE TABLE IF NOT EXISTS trial_claims (
                id SERIAL PRIMARY KEY,
                telegram_id VARCHAR,
                claim_month VARCHAR,
                license_id INTEGER REFERENCES licenses(id),
                mt5_id VARCHAR,
                claimed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        ]
        
        for q in queries:
            try:
                await db.execute(text(q))
                await db.commit()
                print(f"Success: {q.strip()[:50]}...")
            except Exception as e:
                print(f"Error executing {q.strip()[:50]}...: {e}")
                await db.rollback()
                
if __name__ == "__main__":
    asyncio.run(alter_table())
