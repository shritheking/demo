import asyncio
import os
import sys

sys.path.append(os.path.dirname(__file__))

from app.db.database import get_db, AsyncSessionLocal
from sqlalchemy import text
from app.models import User, Order, Payment, License, VpsOrder, AdminNotification, CompileJob

async def clear_data():
    print("Clearing all data except products...")
    async with AsyncSessionLocal() as db:
        # SQLite doesn't support TRUNCATE, so we use DELETE
        await db.execute(text("DELETE FROM compile_jobs"))
        await db.execute(text("DELETE FROM payments"))
        await db.execute(text("DELETE FROM vps_orders"))
        await db.execute(text("DELETE FROM licenses"))
        await db.execute(text("DELETE FROM orders"))
        await db.execute(text("DELETE FROM admin_notifications"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()
    print("Data cleared successfully.")

if __name__ == "__main__":
    asyncio.run(clear_data())
