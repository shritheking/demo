import requests
import json

url = 'https://infinity-trader-telegram-bot.onrender.com/internal/delivery'
payload = {'license_id': 24}

print(f"Triggering delivery for license 24 at {url}...")
try:
    resp = requests.post(url, json=payload, timeout=10)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
