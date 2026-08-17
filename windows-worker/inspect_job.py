"""
inspect_job.py — Read-only inspection of job 21 and its associated license.
Prints the license_id, expiry_date, and plan so we know what to fix.
Makes no changes to the database.
"""
import os, sys, requests
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).resolve().parent / ".env")

API = os.getenv("API_BASE_URL", "").rstrip("/")
KEY = os.getenv("WORKER_API_KEY", "")
h   = {"infinity-worker-api-key": KEY}

print(f"[INFO] API: {API}")
print()

# ── All compiler jobs (admin — no auth needed on this route) ─────────────────
r = requests.get(f"{API}/admin/compiler_jobs", timeout=20)
print(f"GET /admin/compiler_jobs → HTTP {r.status_code}")
if r.status_code != 200:
    print("ERROR:", r.text[:300])
    sys.exit(1)

jobs = r.json()
job21 = next((j for j in jobs if j.get("id") == 21), None)
if not job21:
    print("Job 21 not found. All jobs:")
    for j in jobs:
        print(" ", j)
    sys.exit(1)

print()
print("Job 21 record:")
for k, v in job21.items():
    print(f"  {k}: {v}")

license_id = job21.get("license_id")
print()
print(f"[INFO] License ID for job 21: {license_id}")

# ── Fetch the license ─────────────────────────────────────────────────────────
if license_id:
    r2 = requests.get(f"{API}/licenses", timeout=20)
    print(f"GET /licenses → HTTP {r2.status_code}")
    if r2.status_code == 200:
        licenses = r2.json()
        lic = next((l for l in licenses if l.get("id") == license_id), None)
        if lic:
            print()
            print(f"License {license_id} record:")
            for k, v in lic.items():
                print(f"  {k}: {v}")
        else:
            print(f"License {license_id} not found in /licenses list")
    else:
        print("Could not fetch licenses:", r2.text[:200])
