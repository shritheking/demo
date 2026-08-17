import asyncio
import httpx

async def check():
    base = "https://infinity-trader-api.onrender.com/api/v1"
    async with httpx.AsyncClient(timeout=30) as c:
        # Check recent orders
        r = await c.get(f"{base}/orders/")
        orders = r.json()
        print("=== ORDERS ===")
        for o in orders[:8]:
            print(f"Order {o['id']} | status={o['status']} | installment={o.get('installment_enabled')} | paid={o.get('installments_paid')} / {o.get('installment_count')} | mt5={o.get('mt5_id')}")
        
        print()
        print("=== LICENSES ===")
        r2 = await c.get(f"{base}/licenses/")
        lics = r2.json()
        for l in lics[:8]:
            fn = l.get("generated_filename") or "NO FILE"
            print(f"License {l['id']} | order={l['order_id']} | status={l['status']} | mt5={l['mt5_id']} | file={fn}")

asyncio.run(check())
