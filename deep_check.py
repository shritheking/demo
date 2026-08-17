import asyncio
import httpx

async def deep_check():
    base = "https://infinity-trader-api.onrender.com/api/v1"
    key = "yx9Cd2LLjjaV1ugyxdlbP39-bBjuTwa42PRilaqlhBk"
    
    async with httpx.AsyncClient(timeout=30) as c:
        # Job status
        r = await c.get(f"{base}/jobs/status", headers={"infinity-worker-api-key": key})
        print("Job status:", r.json())
        
        # Check pending jobs - get all of them
        r2 = await c.get(f"{base}/jobs/pending", headers={"infinity-worker-api-key": key})
        pending = r2.json()
        print(f"\nPending jobs ({len(pending)}):")
        for j in pending:
            print(f"  Job {j['job_id']} -> License {j['license_id']} MT5={j['mt5_id']}")
        
        # Check if license 72 (most recent) has its job in the queue
        lic_ids_in_queue = [j['license_id'] for j in pending]
        print(f"\nLicense IDs in pending queue: {lic_ids_in_queue}")
        print(f"License 65-72 in queue: {[l for l in range(65,73) if l in lic_ids_in_queue]}")
        print(f"License 65-72 NOT in queue: {[l for l in range(65,73) if l not in lic_ids_in_queue]}")
        
        # Check license status now
        r3 = await c.get(f"{base}/licenses/")
        lics = r3.json()
        print("\nRecent licenses:")
        for l in lics[:8]:
            fn = l.get("generated_filename") or "NO FILE"
            print(f"  License {l['id']} | order={l['order_id']} | status={l['status']} | mt5={l['mt5_id']} | file={'YES' if fn != 'NO FILE' else 'NO'}")

asyncio.run(deep_check())
