import asyncio
import os
import sys

sys.path.append(os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, update
from app.db.database import DATABASE_URL
from app.models import Product

async def seed_products():
    engine = create_async_engine(DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as session:
        # Mark all existing EA products as inactive
        await session.execute(
            update(Product).where(Product.type == 'EA').values(active=False)
        )
        
        # Create single lifetime product
        lifetime_product = Product(
            type="EA",
            name="Infinity Trader EA - Lifetime",
            price=25000.0,
            duration=0,
            active=True,
            description="Lifetime License for Infinity Trader EA tied to a single MT5 ID."
        )
        session.add(lifetime_product)
        await session.commit()
        
    print("Seeded Lifetime Product Successfully!")

if __name__ == "__main__":
    asyncio.run(seed_products())
