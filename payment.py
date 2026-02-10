import stripe
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from fastapi import HTTPException
from api_keys import api_key_manager

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
            
            total_price = quantity * unit_price
            amount_cents = int(total_price * 100)
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'Agent Memory API - {description}',
                            'description': f'{quantity} credits for agent memory operations'
                        },
                        'unit_amount': amount_cents
                    },
                    'quantity': 1
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={'credits': quantity}
            )
            return {'session_id': session.id, 'url': session.url, 'amount_total': session.amount_total / 100 if session.amount_total else 0}
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Checkout error: {str(e)}")
    
    @staticmethod
    async def verify_session(session_id: str) -> Dict[str, Any]:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status != 'paid':
                raise HTTPException(status_code=400, detail="Payment not completed")
            return {
                'session_id': session.id,
                'customer_email': session.customer_details.email if session.customer_details else None,
                'amount_total': session.amount_total / 100 if session.amount_total else 0,
                'credits': int(session.metadata.get('credits', 0)),
                'paid': True
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Session verification failed: {str(e)}")

async def verify_payment_token(authorization: Optional[str], cost_in_credits: int = 1) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    api_key = authorization.replace("Bearer ", "").strip()
    key_data = api_key_manager.validate_key(api_key)
    if not key_data:
        return False
    return api_key_manager.deduct_credits(api_key, cost_in_credits)
