import asyncio
import httpx

async def check():
    base = "https://infinity-trader-api.onrender.com/api/v1"
    key = "yx9Cd2LLjjaV1ugyxdlbP39-bBjuTwa42PRilaqlhBk"
    
    async with httpx.AsyncClient(timeout=30) as c:
        # Check pending jobs
        r = await c.get(f"{base}/jobs/pending", headers={"infinity-worker-api-key": key})
        print("Pending jobs:", r.text[:300])
        
        # Try claiming a job to see if any exist
        r2 = await c.post(f"{base}/jobs/claim", 
                          headers={"infinity-worker-api-key": key},
                          json={"worker_id": "debug-check"})
        print("Claim attempt:", r2.status_code, r2.text[:300])
        
        # If claimed, fail it back so worker can retry
        if r2.status_code == 200 and r2.json().get("status") == "success":
            job = r2.json()["job"]
            job_id = job["job_id"]
            print(f"Got job {job_id}, failing it back...")
            r3 = await c.post(f"{base}/jobs/{job_id}/fail",
                              headers={"infinity-worker-api-key": key},
                              json={"worker_id": "debug-check", "error_message": "debug check - re-queuing"})
            print("Fail response:", r3.status_code, r3.text)

asyncio.run(check())
