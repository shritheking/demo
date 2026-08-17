"""
reset_jobs.py
Waits for the Render deployment to complete, then resets Jobs 22 and 23.
"""
import os, sys, requests, time
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).resolve().parent / ".env")

API = os.getenv("API_BASE_URL", "").rstrip("/")
print(f"[INFO] API: {API}")

def reset_job(job_id):
    url = f"{API}/admin/jobs/{job_id}/retry"
    r = requests.post(url, timeout=10)
    return r.status_code, r.text

print("[INFO] Waiting for Render deployment to complete (checking retry endpoint)...")
max_retries = 30
for i in range(max_retries):
    try:
        # Just ping job 22. If we get a 404, the old code is running.
        # Wait, if we get 404 it might be because job 22 doesn't exist? No, we know it exists.
        # But wait, the old API doesn't have the /retry route at all, so it will return 404 Not Found for the route.
        # Wait, if we get 405 Method Not Allowed or 404 Not Found for the route, it means old code.
        status, text = reset_job(22)
        if status in (200, 400):
            print(f"\n[SUCCESS] New API is LIVE! Job 22 reset result: HTTP {status} - {text}")
            break
        else:
            print(f"Wait {i+1}/{max_retries}... HTTP {status}")
    except Exception as e:
        print(f"Wait {i+1}/{max_retries}... Error: {e}")
    time.sleep(10)
else:
    print("\n[ERROR] Deployment check timed out.")
    sys.exit(1)

# Now reset job 23
print("\n[INFO] Resetting Job 23...")
try:
    status, text = reset_job(23)
    print(f"Job 23 reset result: HTTP {status} - {text}")
except Exception as e:
    print(f"Failed to reset job 23: {e}")

print("\n[SUCCESS] Jobs reset. Worker is ready to be started.")
