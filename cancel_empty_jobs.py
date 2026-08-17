import asyncio
import httpx

async def cancel_empty_mt5_jobs():
    """
    Cancel compile jobs for licenses that have no MT5 ID.
    These jobs would keep failing in a loop.
    Also mark their licenses as 'failed' so admin knows they need attention.
    """
    base = "https://infinity-trader-api.onrender.com/api/v1"
    key = "yx9Cd2LLjjaV1ugyxdlbP39-bBjuTwa42PRilaqlhBk"
    worker_id = "admin-cleanup"
    
    async with httpx.AsyncClient(timeout=30) as c:
        # Job 67 is the empty MT5 job (license 63, also licenses 64, 65)
        # We need to claim those jobs and fail them permanently
        
        print("Current pending jobs:")
        r = await c.get(f"{base}/jobs/pending", headers={"infinity-worker-api-key": key})
        pending = r.json()
        
        # Find all empty MT5 jobs
        empty_jobs = [j for j in pending if not j.get('mt5_id') or j['mt5_id'].strip() == '']
        print(f"Jobs with empty MT5 ID: {[(j['job_id'], j['license_id']) for j in empty_jobs]}")
        
        # We need to claim and fail each empty MT5 job
        for job in empty_jobs:
            job_id = job['job_id']
            # Claim it
            claim_resp = await c.post(f"{base}/jobs/claim",
                                      headers={"infinity-worker-api-key": key},
                                      json={"worker_id": worker_id})
            if claim_resp.status_code == 200 and claim_resp.json().get("status") == "success":
                claimed_job_id = claim_resp.json()["job"]["job_id"]
                # Fail it permanently with a clear message
                fail_resp = await c.post(f"{base}/jobs/{claimed_job_id}/fail",
                                         headers={"infinity-worker-api-key": key},
                                         json={
                                             "worker_id": worker_id,
                                             "error_message": "PERMANENTLY_SKIPPED: License has no MT5 ID. Admin must re-generate with valid MT5 ID."
                                         })
                print(f"Cancelled job {claimed_job_id}: {fail_resp.status_code}")
        
        # Final status
        r2 = await c.get(f"{base}/jobs/status", headers={"infinity-worker-api-key": key})
        print(f"\nFinal job status: {r2.json()}")
        
        # Show remaining pending (valid) jobs
        r3 = await c.get(f"{base}/jobs/pending", headers={"infinity-worker-api-key": key})
        valid = r3.json()
        print(f"Valid pending jobs: {len(valid)}")
        for j in valid:
            print(f"  Job {j['job_id']} -> License {j['license_id']} MT5={j['mt5_id']}")

asyncio.run(cancel_empty_mt5_jobs())
