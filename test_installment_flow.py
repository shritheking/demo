import asyncio
import httpx
import uuid

BASE_URL = "https://infinity-trader-api.onrender.com/api/v1"

async def test_flow():
    async with httpx.AsyncClient() as client:
        print("1. Creating user and order...")
        user_res = await client.post(f"{BASE_URL}/users/", json={
            "telegram_id": "test_user_77",
            "name": "Test User",
            "username": "test_user_77"
        })
        user_id = user_res.json()["id"]
        
        prod_res = await client.get(f"{BASE_URL}/products/")
        product_id = prod_res.json()[0]["id"]
        
        order_res = await client.post(f"{BASE_URL}/orders/", json={
            "user_id": user_id,
            "product_id": product_id,
            "order_type": "ea",
            "mt5_id": ""
        })
        order = order_res.json()
        order_id = order["id"]
        print(f"Created Order #{order_id}")
        
        print("2. Admin approves order...")
        await client.post(f"{BASE_URL}/orders/{order_id}/approve")
        
        print("3. Customer submits MT5 ID...")
        mt5_id = "MT5_" + str(uuid.uuid4())[:8]
        mt5_res = await client.put(f"{BASE_URL}/orders/{order_id}/mt5", json={
            "mt5_id": mt5_id
        })
        print(f"MT5 save response: {mt5_res.json()}")
        
        print("4. Admin creates installment arrangement...")
        arr_res = await client.post(f"{BASE_URL}/installments/create", json={
            "order_id": order_id,
            "total_amount": 30000,
            "installment_amount": 5000,
            "installment_count": 6,
            "first_payment_amount": 5000,
            "license_period_days": 35
        })
        print(f"Create arrangement response: {arr_res.json()}")
        
        print("6. Pay next installment...")
        pay_res = await client.post(f"{BASE_URL}/installments/pay", json={
            "order_id": order_id,
            "amount": 5000
        })
        print(f"Pay next response: {pay_res.json()}")
        
if __name__ == "__main__":
    asyncio.run(test_flow())
