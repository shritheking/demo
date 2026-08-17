import requests
url = "https://infinity-trader-telegram-bot.onrender.com/internal/delivery"
r = requests.post(url, json={"license_id": 30})
print("Status Code:", r.status_code)
print("Response:", r.text)
