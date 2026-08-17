"""
inspect_jobs.py — Read-only inspection of jobs 22 and 23 and their associated licenses.
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

r = requests.get(f"{API}/admin/compiler_jobs", timeout=20)
if r.status_code != 200:
    print("ERROR:", r.text[:300])
    sys.exit(1)

jobs = r.json()
target_job_ids = [22, 23]
target_jobs = [j for j in jobs if j.get("id") in target_job_ids]

if not target_jobs:
    print("Jobs 22 and 23 not found.")
    sys.exit(1)

r2 = requests.get(f"{API}/licenses", timeout=20)
if r2.status_code == 200:
    licenses = r2.json()
else:
    print("Could not fetch licenses:", r2.text[:200])
    sys.exit(1)

for job in target_jobs:
    print("="*40)
    print(f"Job {job['id']} record:")
    for k, v in job.items():
        print(f"  {k}: {v}")
    
    license_id = job.get("license_id")
    lic = next((l for l in licenses if l.get("id") == license_id), None)
    if lic:
        print(f"\nLicense {license_id} record:")
        for k, v in lic.items():
            print(f"  {k}: {v}")
        if lic.get("expiry_date") is None:
            print("  >>> EXPIRY DATE IS NULL IN DB <<<")
        else:
            print("  >>> EXPIRY DATE EXISTS IN DB <<<")
    else:
        print(f"\nLicense {license_id} not found.")

