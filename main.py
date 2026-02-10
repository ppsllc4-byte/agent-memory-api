from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv
from datetime import datetime
from database import db
from payment import PaymentProcessor, verify_payment_token
from api_keys import api_key_manager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

app = FastAPI(
    title="Agent Memory API",
    description="Persistent memory and context storage for AI agents",
    version="2.0.0"
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MemoryStore(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=100000)
    tags: Optional[List[str]] = Field(default=[], max_length=10)
    metadata: Optional[Dict[str, Any]] = {}
    ttl_days: Optional[int] = Field(default=30, ge=0, le=365)

class MemorySearch(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    query: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(None, max_length=10)
    limit: Optional[int] = Field(default=10, ge=1, le=100)

@app.get("/")
@limiter.limit("100/minute")
async def root(request: Request):
    return {
        "message": "Agent Memory API - Persistent Memory for AI Agents",
        "tagline": "Rent a brain for your agent",
        "version": "2.0.0",
        "security": "API key authentication + rate limiting enabled",
        "endpoints": {
            "store": "POST /memory/store",
            "retrieve": "GET /memory/{memory_id}",
            "search": "POST /memory/search",
            "delete": "DELETE /memory/{memory_id}",
            "stats": "GET /agent/{agent_id}/stats",
            "credits": "GET /credits/check"
        }
    }

@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "operational",
        "encryption": "active",
        "authentication": "enabled",
        "version": "2.0.0"
    }

@app.post("/memory/store")
@limiter.limit("60/minute")
async def store_memory(request: Request, memory: MemoryStore, authorization: Optional[str] = Header(None)):
    is_authorized = await verify_payment_token(authorization, cost_in_credits=1)
    if not is_authorized:
        raise HTTPException(status_code=402, detail={"error": "Payment required", "message": "Invalid API key or insufficient credits", "pricing": "$0.001 per memory stored (1 credit)", "get_credits": "/purchase"})
    try:
        result = await db.store_memory(agent_id=memory.agent_id, content=memory.content, tags=memory.tags, metadata=memory.metadata, ttl_days=memory.ttl_days)
        return {"status": "success", "memory_id": result["memory_id"], "agent_id": result["agent_id"], "created_at": result["created_at"], "expires_at": result["expires_at"], "message": "Memory stored and encrypted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage failed: {str(e)}")

@app.get("/memory/{memory_id}")
@limiter.limit("100/minute")
async def retrieve_memory(request: Request, memory_id: str, authorization: Optional[str] = Header(None)):
    is_authorized = await verify_payment_token(authorization, cost_in_credits=1)
    if not is_authorized:
        raise HTTPException(status_code=402, detail={"error": "Payment required", "message": "Invalid API key or insufficient credits", "pricing": "$0.001 per retrieval (1 credit)", "get_credits": "/purchase"})
    try:
        memory = await db.retrieve_memory(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found or expired")
        return {"status": "success", "memory": memory}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

@app.post("/memory/search")
@limiter.limit("30/minute")
async def search_memories(request: Request, search: MemorySearch, authorization: Optional[str] = Header(None)):
    is_authorized = await verify_payment_token(authorization, cost_in_credits=5)
    if not is_authorized:
        raise HTTPException(status_code=402, detail={"error": "Payment required", "message": "Invalid API key or insufficient credits", "pricing": "$0.005 per search (5 credits)", "get_credits": "/purchase"})
    try:
        results = await db.search_memories(agent_id=search.agent_id, query=search.query, tags=search.tags, limit=search.limit or 10)
        return {"status": "success", "agent_id": search.agent_id, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.delete("/memory/{memory_id}")
@limiter.limit("100/minute")
async def delete_memory(request: Request, memory_id: str, agent_id: str = Query(...), authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    try:
        success = await db.delete_memory(memory_id, agent_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found or unauthorized")
        return {"status": "success", "memory_id": memory_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/agent/{agent_id}/stats")
@limiter.limit("100/minute")
async def get_agent_stats(request: Request, agent_id: str):
    try:
        stats = await db.get_agent_stats(agent_id)
        if not stats:
            return {"agent_id": agent_id, "active_memories": 0, "total_memories_stored": 0, "storage_used_mb": 0.0}
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

@app.get("/credits/check")
@limiter.limit("100/minute")
async def check_credits(request: Request, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization.replace("Bearer ", "").strip()
    credits = api_key_manager.get_credits(api_key)
    if credits is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"credits_remaining": credits, "status": "active" if credits > 0 else "depleted"}

@app.post("/admin/create-api-key")
async def create_api_key(user_email: str, credits: int = 1000, admin_secret: str = Header(None, alias="X-Admin-Secret")):
    if admin_secret != os.getenv("API_SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Forbidden")
    api_key = api_key_manager.create_key(user_email, credits)
    return {"status": "success", "api_key": api_key, "user_email": user_email, "credits": credits, "message": "SAVE THIS KEY!"}

@app.post("/admin/cleanup")
async def cleanup_expired(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {os.getenv('API_SECRET_KEY')}":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        count = await db.cleanup_expired()
        return {"status": "success", "expired_cleaned": count, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.post("/purchase")
@limiter.limit("10/minute")
async def purchase_credits(request: Request, credits: int = 1000, service_type: str = "memory_credits", email: Optional[str] = None):
    if credits < 1 or credits > 100000:
        raise HTTPException(status_code=400, detail="Credits must be between 1 and 100,000")
    base_url = os.getenv("BASE_URL", "https://agent-memory-api-production.up.railway.app")
    session = await PaymentProcessor.create_checkout_session(success_url=f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{base_url}/payment/cancel", quantity=credits, service_type=service_type)
    return {"checkout_url": session['url'], "session_id": session['session_id'], "total_amount": session['amount_total'], "credits": credits}

@app.get("/payment/success")
async def payment_success(session_id: str):
    try:
        payment_info = await PaymentProcessor.verify_session(session_id)
        user_email = payment_info['customer_email'] or f"user_{session_id[:8]}@stripe.customer"
        credits = payment_info['credits']
        api_key = api_key_manager.create_key(user_email, credits)
        return {"status": "success", "message": "SAVE THIS API KEY! It will not be shown again.", "api_key": api_key, "credits": credits, "user_email": user_email, "amount_paid": f"${payment_info['amount_total']:.2f}", "instructions": {"step_1": "Copy the api_key above", "step_2": "Use it in Authorization header", "example": f"Authorization: Bearer {api_key}"}, "docs": "https://agent-memory-api-production.up.railway.app/docs"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment processing failed: {str(e)}")

@app.get("/payment/cancel")
async def payment_cancel():
    return {"status": "cancelled", "message": "Payment cancelled"}

@app.get("/pricing")
@limiter.limit("100/minute")
async def get_pricing(request: Request):
    return {"store_memory": "$0.001 per memory (1 credit)", "retrieve_memory": "$0.001 per retrieval (1 credit)", "search_memories": "$0.005 per search (5 credits)", "delete_memory": "FREE", "encryption": "AES-256 included", "bulk_pricing": {"1000_credits": "$1.00", "10000_credits": "$10.00", "100000_credits": "$100.00"}}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
