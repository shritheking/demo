import asyncio
import httpx
import sys

download_url = "https://jwoxmjdmhfmjutqiizes.supabase.co/storage/v1/object/sign/licenses/24/24/bot.ex5?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJsaWNlbnNlcy8yNC8yNC9ib3QuZXg1IiwiaWF0IjoxNjc1OTY2Nzg2LCJleHAiOjE2NzU5NzAzODZ9.H3r-3L... wait the token changed"
# I will fetch it dynamically!
import requests
API = "https://infinity-trader-api.onrender.com/api/v1"
r = requests.get(f"{API}/licenses/24/delivery-info")
if r.status_code != 200:
    print("Failed to get delivery info")
    sys.exit(1)

info = r.json()
download_url = info.get("download_url")

async def test():
    async with httpx.AsyncClient(verify=False) as client:
        print(f"Downloading from {download_url[:80]}...")
        file_resp = await client.get(download_url)
        print(f"Download status: {file_resp.status_code}")
        if file_resp.status_code == 200:
            print(f"File size: {len(file_resp.content)} bytes")
        else:
            print(f"Error body: {file_resp.text}")

asyncio.run(test())
