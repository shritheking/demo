import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine
from app.db.database import DATABASE_URL
from app.models import Base

async def create_tables():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"Tables created successfully in {DATABASE_URL}!")

if __name__ == "__main__":
    asyncio.run(create_tables())
