import asyncio
import httpx

async def fix_failed():
    base = "https://infinity-trader-api.onrender.com/api/v1"
    key = "yx9Cd2LLjjaV1ugyxdlbP39-bBjuTwa42PRilaqlhBk"
    
    async with httpx.AsyncClient(timeout=30) as c:
        # Reset failed jobs
        print("Resetting failed jobs...")
        r = await c.post(f"{base}/jobs/reset-stuck", headers={"infinity-worker-api-key": key})
        print("Reset result:", r.json())
        
        # Now check what's pending - especially for licenses 65-70
        r2 = await c.get(f"{base}/jobs/pending", headers={"infinity-worker-api-key": key})
        pending = r2.json()
        print(f"\nPending jobs ({len(pending)}):")
        for j in pending:
            print(f"  Job {j['job_id']} -> License {j['license_id']} MT5={j['mt5_id']}")
        
        # For licenses with empty MT5 ID (license 65, order 85) - we need to skip
        # Check license 65
        r3 = await c.get(f"{base}/licenses/")
        lics = r3.json()
        empty_mt5 = [l for l in lics if not l.get('mt5_id')]
        print(f"\nLicenses with empty MT5 ID: {[(l['id'], l['order_id']) for l in empty_mt5]}")

asyncio.run(fix_failed())
