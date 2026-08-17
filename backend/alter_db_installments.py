import asyncio
import os
import sys

sys.path.append(os.path.dirname(__file__))

from app.db.database import get_db, AsyncSessionLocal
from sqlalchemy import text

async def alter_table():
    print("Altering table for installments...")
    async with AsyncSessionLocal() as db:
        queries = [
            "ALTER TABLE orders ADD COLUMN installment_enabled BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE orders ADD COLUMN installment_total_amount FLOAT;",
            "ALTER TABLE orders ADD COLUMN installment_amount FLOAT;",
            "ALTER TABLE orders ADD COLUMN installment_count INTEGER;",
            "ALTER TABLE orders ADD COLUMN installments_paid INTEGER DEFAULT 0;",
            "ALTER TABLE orders ADD COLUMN amount_paid FLOAT DEFAULT 0.0;",
            "ALTER TABLE orders ADD COLUMN amount_remaining FLOAT;",
            "ALTER TABLE orders ADD COLUMN next_due_date TIMESTAMP WITH TIME ZONE;",
            "ALTER TABLE orders ADD COLUMN license_period_days INTEGER;",
            "ALTER TABLE orders ADD COLUMN grace_days INTEGER DEFAULT 5;",
            "ALTER TABLE orders ADD COLUMN installment_status VARCHAR DEFAULT 'active';",
            """
            CREATE TABLE IF NOT EXISTS installment_payments (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                amount FLOAT,
                payment_number INTEGER,
                payment_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR DEFAULT 'confirmed'
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
