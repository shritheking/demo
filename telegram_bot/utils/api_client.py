import httpx
import logging

import os

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


def _admin_headers():
    """Header for admin-only backend routes. These routes enforce this
    server-side (see app.core.security.verify_admin_key) - the bot's own
    telegram-id check only controls what buttons a user sees, it is not a
    substitute for backend auth."""
    return {"X-Admin-Key": ADMIN_API_KEY}


def _safe_error_message(response) -> str:
    """Log the raw backend error and return a customer-safe message.

    Spec section 30: customers must never see raw backend error text
    (status codes, stack traces, HTML error pages, etc). A 4xx response
    with a JSON "detail" field is an intentional, customer-facing message
    written by our own API (e.g. "This MT5 ID already has an active
    license.") and is safe to show as-is. Anything else - 5xx responses,
    unparseable bodies - gets logged for us and replaced with a generic
    message for the customer.
    """
    detail = None
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("detail")
    except Exception:
        pass

    logging.error(f"Backend error {response.status_code}: {response.text}")

    if detail and response.status_code < 500:
        return str(detail)
    return "Something went wrong on our end. Please try again shortly or contact support."


def _connection_error_message(e) -> str:
    logging.error(f"Connection error: {e}")
    return "Could not reach the server. Please try again in a moment."

async def register_user(telegram_id, name, username, phone=None):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/users/",
                json={
                    "telegram_id": str(telegram_id),
                    "name": name,
                    "username": username or "",
                    "phone": phone
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error registering user: {e}")
            return None

async def get_user(telegram_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/users/{telegram_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error fetching user: {e}")
            return None

async def update_user_phone(user_id, phone):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(f"{BASE_URL}/users/{user_id}/phone", json={"phone": phone})
            if response.status_code >= 400:
                return False
            return True
        except Exception as e:
            logging.error(f"Error updating phone: {e}")
            return False

async def get_products(product_type=None):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/products/")
            response.raise_for_status()
            products = response.json()
            if product_type:
                products = [p for p in products if p['type'] == product_type]
            return products
        except Exception as e:
            logging.error(f"Error fetching products: {e}")
            return []

async def create_order(user_id, product_id, order_type, mt5_id=None):
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "user_id": user_id,
                "product_id": product_id,
                "order_type": order_type
            }
            if mt5_id:
                payload["mt5_id"] = mt5_id
                
            response = await client.post(
                f"{BASE_URL}/orders/",
                json=payload
            )
            
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def approve_order(order_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/orders/{order_id}/approve", headers=_admin_headers())
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def reject_order(order_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/orders/{order_id}/reject", headers=_admin_headers())
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def generate_license(order_id, mt5_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/licenses/generate",
                json={
                    "order_id": order_id,
                    "mt5_id": mt5_id
                },
                headers=_admin_headers()
            )
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def create_installment_arrangement(payload: dict):
    """Admin-only: sets up an installment arrangement for an approved order
    that already has an MT5 ID. Installments are never a self-serve/public
    plan - this is only ever called from the admin flow in bot.py."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/installments/create",
                json=payload,
                headers=_admin_headers()
            )
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def pay_installment(order_id, amount):
    """Admin-only: records that the customer has paid the admin directly
    and the admin has confirmed it. There is no automated payment gateway
    in this flow."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/installments/pay",
                json={"order_id": order_id, "amount": amount},
                headers=_admin_headers()
            )
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def get_admin_installment(order_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/installments/admin/{order_id}",
                headers=_admin_headers()
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logging.error(f"Error fetching admin installment: {e}")
            return None

async def save_order_mt5_id(order_id, mt5_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{BASE_URL}/orders/{order_id}/mt5",
                json={
                    "mt5_id": mt5_id
                }
            )
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def request_free_trial(telegram_id, mt5_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/trials/request",
                json={
                    "telegram_user_id": str(telegram_id),
                    "mt5_id": mt5_id
                }
            )
            
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def request_broker_change(license_id, new_mt5_id, new_broker, telegram_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/licenses/{license_id}/broker-change-request",
                json={"new_mt5_id": new_mt5_id, "new_broker": new_broker, "telegram_id": str(telegram_id)}
            )
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def approve_broker_change(request_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/licenses/broker-change/{request_id}/approve", headers=_admin_headers())
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def reject_broker_change(request_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/licenses/broker-change/{request_id}/reject", headers=_admin_headers())
            if response.status_code >= 400:
                return {"error": _safe_error_message(response)}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": _connection_error_message(e)}

async def get_installment_status(telegram_id):
    """Fetch a customer's installment arrangement, if any. Returns None if the
    customer has no installment arrangement (used both to render the status
    screen and to decide whether the 'My Installment' menu button is shown)."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/installments/customer/{telegram_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logging.error(f"Error fetching installment status: {e}")
            return None


async def is_installment_eligible(telegram_id):
    """True only for customers with an active/eligible installment arrangement.
    Normal customers must never see the installment menu option."""
    return await get_installment_status(telegram_id) is not None


async def get_settings():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/settings/")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception:
            return {}

async def update_setting(key, value):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(f"{BASE_URL}/settings/{key}", json={"setting_value": str(value)})
            if response.status_code == 200:
                return True
            return False
        except Exception:
            return False
