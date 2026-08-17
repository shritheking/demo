import asyncio
from app.db.database import engine, Base
# Import all models so they are registered with Base.metadata
from app.models import *

async def wipe_data():
    async with engine.begin() as conn:
        # Drop all tables
        await conn.run_sync(Base.metadata.drop_all)
        # Recreate all tables
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database has been completely wiped and recreated successfully.")

if __name__ == "__main__":
    asyncio.run(wipe_data())
