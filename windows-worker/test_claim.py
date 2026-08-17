"""
test_claim.py
Safe test request to the /claim endpoint.
Claims one job, prints the payload, and resets it back to pending.
"""
import os, sys, requests, json
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).resolve().parent / ".env")

API = os.getenv("API_BASE_URL", "").rstrip("/")
KEY = os.getenv("WORKER_API_KEY", "")
WORKER_ID = "test-worker-01"

headers = {"infinity-worker-api-key": KEY}

print(f"[INFO] Connecting to API: {API}")

# Claim a job
print("[INFO] POST /jobs/claim")
r = requests.post(f"{API}/jobs/claim", json={"worker_id": WORKER_ID}, headers=headers, timeout=10)

if r.status_code != 200:
    print(f"[ERROR] HTTP {r.status_code}: {r.text[:200]}")
    sys.exit(1)

data = r.json()
print("\n[SUCCESS] Claim Payload Received:")
print(json.dumps(data, indent=2))

if data.get("status") == "success" and "job" in data:
    job_id = data["job"]["job_id"]
    print(f"\n[INFO] Resetting Job {job_id} back to pending...")
    r_reset = requests.post(f"{API}/admin/jobs/{job_id}/retry", timeout=10)
    print(f"Reset result: HTTP {r_reset.status_code} - {r_reset.text}")
