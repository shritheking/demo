import os, requests
from dotenv import load_dotenv

load_dotenv('C:\\mt5-license-system\\.env')
load_dotenv('C:\\mt5-license-system\\windows-worker\\.env')

API = os.getenv("API_BASE_URL", "").rstrip("/")
KEY = os.getenv("WORKER_API_KEY", "")

def fetch_data():
    print("[ORDERS]")
    r = requests.get(f"{API}/orders")
    if r.status_code == 200:
        orders = sorted(r.json(), key=lambda x: x['id'])
        for o in orders[-5:]:
            print(f"Order {o['id']}: status={o['status']}, mt5_id={o.get('mt5_id')}")
            
    print("\n[LICENSES]")
    r = requests.get(f"{API}/licenses")
    if r.status_code == 200:
        licenses = sorted(r.json(), key=lambda x: x['id'])
        for l in licenses[-5:]:
            print(f"License {l['id']}: mt5_id={l.get('mt5_id')}, status={l['status']}")
            
    print("\n[JOBS]")
    r = requests.get(f"{API}/admin/compiler_jobs")
    if r.status_code == 200:
        jobs = sorted(r.json(), key=lambda x: x['id'])
        for j in jobs[-5:]:
            print(f"Job {j['id']}: status={j['status']}, license_id={j['license_id']}")

fetch_data()
