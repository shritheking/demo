import os
import sys
import json
import requests
from dotenv import load_dotenv

# Try loading from windows-worker/.env and backend/.env or root .env
load_dotenv('C:\\mt5-license-system\\windows-worker\\.env')
load_dotenv('C:\\mt5-license-system\\.env')

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SECRET_KEY')

if not url or not key:
    print("SUPABASE_URL or SUPABASE_SECRET_KEY missing from local .envs")
    sys.exit(1)

resp = requests.get(f"{url}/storage/v1/bucket", headers={"Authorization": f"Bearer {key}"})

if resp.status_code == 200:
    buckets = resp.json()
    print("Buckets found:")
    for b in buckets:
        print(f" - {b.get('id')} (name: {b.get('name')})")
else:
    print(f"Error {resp.status_code}: {resp.text}")
