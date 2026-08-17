# NOTE: Razorpay/automated payment-gateway support is NOT part of the
# customer flow. The finalized business flow is "customer pays the admin
# directly, admin confirms the payment in the bot/dashboard" (see
# installments.py /pay and orders.py /approve). This module is kept only
# for potential future compatibility and is not imported by main.py or any
# router - it has no effect unless something explicitly imports it again.
#
# Two things were fixed here even though the module is dormant, because
# leaving them would be a landmine for whoever re-enables it later:
#   1. It used to force `verify=False` onto every `requests` call made by
#      the whole process (not just Razorpay calls) the moment this module
#      was imported, silently disabling TLS certificate validation
#      everywhere. Removed.
#   2. It shipped hardcoded fallback API credentials. Removed - the
#      credentials must now come from the environment, with no fallback.
import razorpay
import os
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY = os.getenv("RAZORPAY_API_KEY")
RAZORPAY_SECRET = os.getenv("RAZORPAY_API_SECRET")

client = None
if RAZORPAY_KEY and RAZORPAY_SECRET:
    client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))


def _require_client():
    if client is None:
        raise RuntimeError(
            "Razorpay is not configured (RAZORPAY_API_KEY/RAZORPAY_API_SECRET not set) "
            "and is not part of the current customer payment flow."
        )
    return client

def create_razorpay_order(amount: float, currency: str = "INR", receipt: str = None) -> dict:
    """
    Creates an order in Razorpay.
    """
    data = {
        "amount": int(amount * 100), # Razorpay expects amount in paise
        "currency": currency,
        "receipt": receipt
    }
    return _require_client().order.create(data=data)

def create_payment_link(amount: float, reference_id: str, description: str = "Infinity Trader Order") -> dict:
    """
    Creates a Razorpay Payment Link.
    """
    data = {
        "amount": int(amount * 100),
        "currency": "INR",
        "accept_partial": False,
        "description": description,
        "reference_id": reference_id,
        "notify": {
            "sms": False,
            "email": False
        },
        "reminder_enable": False,
        "callback_method": "get"
    }
    return _require_client().payment_link.create(data)

def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """
    Verifies the signature sent by Razorpay.
    """
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    try:
        return _require_client().utility.verify_payment_signature(params_dict)
    except Exception as e:
        return False

def verify_webhook_signature(body: str, signature: str, secret: str) -> bool:
    """
    Verifies the webhook signature.
    """
    try:
        return _require_client().utility.verify_webhook_signature(body, signature, secret)
    except Exception as e:
        return False
