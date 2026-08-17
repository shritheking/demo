import asyncio
import os
import sys

sys.path.append(os.path.dirname(__file__))

from app.db.database import get_db, AsyncSessionLocal
from sqlalchemy import text

async def alter_table():
    print("Altering table...")
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("ALTER TABLE licenses ADD COLUMN broker VARCHAR;"))
            await db.commit()
            print("Added broker to licenses table.")
        except Exception as e:
            print(f"Error adding broker to licenses: {e}")
            
        try:
            await db.execute(text("ALTER TABLE broker_change_requests ADD COLUMN old_broker VARCHAR;"))
            await db.execute(text("ALTER TABLE broker_change_requests ADD COLUMN new_broker VARCHAR;"))
            await db.commit()
            print("Added old_broker and new_broker to broker_change_requests table.")
        except Exception as e:
            print(f"Error adding to broker_change_requests: {e}")

if __name__ == "__main__":
    asyncio.run(alter_table())
