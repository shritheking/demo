import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def wipe():
    # Convert postgresql:// to postgresql+asyncpg://
    url = "postgresql+asyncpg://admin:erKlPDL9AR93DG4kg6pOtjyuLaT0wb37@dpg-d9qpcvtbedkc73fgs86g-a/infinitytrader"
    engine = create_async_engine(url, echo=True)
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE users CASCADE;"))
            await conn.execute(text("TRUNCATE TABLE orders CASCADE;"))
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(wipe())
