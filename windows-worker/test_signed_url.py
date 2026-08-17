import os, sys, requests
from dotenv import load_dotenv
load_dotenv('C:\\mt5-license-system\\.env')
load_dotenv('C:\\mt5-license-system\\windows-worker\\.env')

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SECRET_KEY')

from supabase import create_client
supabase = create_client(url, key)

try:
    res = supabase.storage.from_("licenses").create_signed_url("test.ex5", 3600)
    print("Signed URL response:", res)
except Exception as e:
    print("Error:", e)
