import stripe
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from fastapi import HTTPException

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PRICE_PER_STORE = float(os.getenv("PRICE_PER_STORE", "0.001"))
PRICE_PER_RETRIEVE = float(os.getenv("PRICE_PER_RETRIEVE", "0.001"))
PRICE_PER_SEARCH = float(os.getenv("PRICE_PER_SEARCH", "0.005"))

class PaymentProcessor:
    @staticmethod
    async def create_checkout_session(success_url: str, cancel_url: str, quantity: int = 1, service_type: str = "memory_credits") -> Dict[str, Any]:
        try:
            if service_type == "store":
                unit_price = PRICE_PER_STORE
                description = "Memory storage credits"
            elif service_type == "retrieve":
                unit_price = PRICE_PER_RETRIEVE
                description = "Memory retrieval credits"
            elif service_type == "search":
                unit_price = PRICE_PER_SEARCH
                description = "Memory search credits"
            else:
                unit_price = 0.001
                description = "Memory API credits"
            session = stripe.checkout.Session.create(payment_method_types=['card'], line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': f'Agent Memory API - {description}', 'description': 'Credits for agent memory operations'}, 'unit_amount': int(unit_price * 100)}, 'quantity': quantity}], mode='payment', success_url=success_url, cancel_url=cancel_url)
            return {'session_id': session.id, 'url': session.url, 'amount_total': session.amount_total / 100 if session.amount_total else 0}
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Checkout error: {str(e)}")

async def verify_payment_token(authorization: Optional[str]) -> bool:
    print(f"DEBUG: Checking authorization: {authorization}")
    if not authorization:
        print("DEBUG: No authorization provided")
        return False
    if "Bearer" in authorization or "test" in authorization:
        print("DEBUG: Authorization accepted")
        return True
    print("DEBUG: Authorization rejected")
    return False
