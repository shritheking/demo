import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv('C:\\mt5-license-system\\.env')
load_dotenv('C:\\mt5-license-system\\windows-worker\\.env')
load_dotenv('C:\\mt5-license-system\\telegram_bot\\.env')

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("No Telegram Token found!")
    sys.exit(1)

# Fetch delivery info from API directly to get the exact URL
API = "https://infinity-trader-api.onrender.com/api/v1"
r = requests.get(f"{API}/licenses/24/delivery-info")
if r.status_code != 200:
    print("Failed to get delivery info")
    sys.exit(1)

info = r.json()
chat_id = info.get("telegram_id")
download_url = info.get("download_url")

print(f"Chat ID: {chat_id}")
print(f"URL: {download_url[:100]}...")

# Try to send document directly to see Telegram's response
resp = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendDocument",
    json={"chat_id": chat_id, "document": download_url, "caption": "Test Delivery"}
)

print(f"Telegram API Response: {resp.status_code}")
try:
    print(json.dumps(resp.json(), indent=2))
except:
    print(resp.text)
