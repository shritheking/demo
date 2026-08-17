import asyncio
import httpx

async def reset_and_check():
    base = "https://infinity-trader-api.onrender.com/api/v1"
    key = "yx9Cd2LLjjaV1ugyxdlbP39-bBjuTwa42PRilaqlhBk"
    
    async with httpx.AsyncClient(timeout=30) as c:
        # First check job status
        print("=== JOB STATUS ===")
        r = await c.get(f"{base}/jobs/status", headers={"infinity-worker-api-key": key})
        print(f"Status ({r.status_code}): {r.text}")
        
        if r.status_code == 404:
            print("Endpoint not deployed yet. Render still deploying...")
            return
        
        # Reset stuck jobs
        print()
        print("=== RESETTING STUCK JOBS ===")
        r2 = await c.post(f"{base}/jobs/reset-stuck", headers={"infinity-worker-api-key": key})
        print(f"Reset ({r2.status_code}): {r2.text}")
        
        # Verify pending jobs now
        print()
        print("=== PENDING JOBS AFTER RESET ===")
        r3 = await c.get(f"{base}/jobs/pending", headers={"infinity-worker-api-key": key})
        print(f"Pending ({r3.status_code}): {r3.text[:500]}")
        
        # Check status again
        print()
        print("=== JOB STATUS AFTER RESET ===")
        r4 = await c.get(f"{base}/jobs/status", headers={"infinity-worker-api-key": key})
        print(f"Status: {r4.text}")

asyncio.run(reset_and_check())
