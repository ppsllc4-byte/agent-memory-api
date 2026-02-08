from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv
from datetime import datetime
from database import db
from payment import PaymentProcessor, verify_payment_token

load_dotenv()

app = FastAPI(
    title="Agent Memory API",
    description="Persistent memory and context storage for AI agents - rent a brain for your agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class MemoryStore(BaseModel):
    agent_id: str
    content: str
    tags: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}
    ttl_days: Optional[int] = 30

class MemorySearch(BaseModel):
    agent_id: str
    query: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: Optional[int] = 10

class MemoryResponse(BaseModel):
    memory_id: str
    agent_id: str
    content: str
    tags: List[str]
    metadata: Dict[str, Any]
    created_at: str
    expires_at: Optional[str]
    access_count: int

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Agent Memory API - Persistent Memory for AI Agents",
        "tagline": "Rent a brain for your agent",
        "version": "1.0.0",
        "endpoints": {
            "store": "POST /memory/store",
            "retrieve": "GET /memory/{memory_id}",
            "search": "POST /memory/search",
            "delete": "DELETE /memory/{memory_id}",
            "stats": "GET /agent/{agent_id}/stats",
            "purchase": "POST /purchase",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "operational",
        "encryption": "active"
    }

@app.post("/memory/store")
async def store_memory(
    memory: MemoryStore,
    authorization: Optional[str] = Header(None)
):
    """
    Store encrypted memory for an agent
    
    Cost: $0.001 per memory stored
    
    Args:
    - agent_id: Your agent's unique identifier
    - content: The memory/context to store (encrypted automatically)
    - tags: Optional tags for organization
    - metadata: Optional metadata
    - ttl_days: Time-to-live in days (default: 30, 0 = never expires)
    
    Returns memory_id for future retrieval
    """
    
    # Verify payment
    is_authorized = await verify_payment_token(authorization)
    
    if not is_authorized:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Payment required",
                "message": "Memory storage requires payment",
                "pricing": "$0.001 per memory stored",
                "get_credits": "/purchase"
            }
        )
    
    try:
        result = await db.store_memory(
            agent_id=memory.agent_id,
            content=memory.content,
            tags=memory.tags,
            metadata=memory.metadata,
            ttl_days=memory.ttl_days
        )
        
        return {
            "status": "success",
            "memory_id": result["memory_id"],
            "agent_id": result["agent_id"],
            "created_at": result["created_at"],
            "expires_at": result["expires_at"],
            "message": "Memory stored and encrypted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage failed: {str(e)}")

@app.get("/memory/{memory_id}")
async def retrieve_memory(
    memory_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Retrieve and decrypt a stored memory
    
    Cost: $0.001 per retrieval
    
    Returns decrypted memory content with metadata
    """
    
    # Verify payment
    is_authorized = await verify_payment_token(authorization)
    
    if not is_authorized:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Payment required",
                "message": "Memory retrieval requires payment",
                "pricing": "$0.001 per retrieval",
                "get_credits": "/purchase"
            }
        )
    
    try:
        memory = await db.retrieve_memory(memory_id)
        
        if not memory:
            raise HTTPException(
                status_code=404,
                detail="Memory not found or expired"
            )
        
        return {
            "status": "success",
            "memory": memory
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

@app.post("/memory/search")
async def search_memories(
    search: MemorySearch,
    authorization: Optional[str] = Header(None)
):
    """
    Search through agent's memories
    
    Cost: $0.005 per search
    
    Args:
    - agent_id: Your agent's ID
    - query: Optional text to search for in content
    - tags: Optional tags to filter by
    - limit: Max results (default: 10)
    
    Returns matching memories with previews
    """
    
    # Verify payment
    is_authorized = await verify_payment_token(authorization)
    
    if not is_authorized:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Payment required",
                "message": "Memory search requires payment",
                "pricing": "$0.005 per search",
                "get_credits": "/purchase"
            }
        )
    
    try:
        results = await db.search_memories(
            agent_id=search.agent_id,
            query=search.query,
            tags=search.tags,
            limit=search.limit or 10
        )
        
        return {
            "status": "success",
            "agent_id": search.agent_id,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.delete("/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    agent_id: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """
    Delete a stored memory
    
    Free operation (you paid to store it)
    
    Args:
    - memory_id: The memory to delete
    - agent_id: Your agent ID (for verification)
    """
    
    # Verify payment (light check for deletion)
    is_authorized = await verify_payment_token(authorization)
    
    if not is_authorized:
        raise HTTPException(status_code=401, detail="Authorization required")
    
    try:
        success = await db.delete_memory(memory_id, agent_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Memory not found or unauthorized"
            )
        
        return {
            "status": "success",
            "memory_id": memory_id,
            "message": "Memory deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/agent/{agent_id}/stats")
async def get_agent_stats(agent_id: str):
    """
    Get agent's memory statistics
    
    Free endpoint - check your memory usage
    """
    try:
        stats = await db.get_agent_stats(agent_id)
        
        if not stats:
            return {
                "agent_id": agent_id,
                "active_memories": 0,
                "total_memories_stored": 0,
                "storage_used_mb": 0.0,
                "message": "No memories stored yet"
            }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")

@app.post("/admin/cleanup")
async def cleanup_expired(authorization: Optional[str] = Header(None)):
    """
    Admin endpoint: Clean up expired memories
    """
    # Simple admin auth
    if authorization != f"Bearer {os.getenv('API_SECRET_KEY')}":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    try:
        count = await db.cleanup_expired()
        return {
            "status": "success",
            "expired_cleaned": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.post("/purchase")
async def purchase_credits(
    credits: int = 1000,
    service_type: str = "memory_credits",
    email: Optional[str] = None
):
    """
    Purchase memory API credits
    
    Args:
    - credits: Number of operations to purchase
    - service_type: "store", "retrieve", "search", or "memory_credits"
    - email: Optional email for receipt
    
    Returns Stripe checkout URL
    """
    if credits < 1 or credits > 100000:
        raise HTTPException(status_code=400, detail="Credits must be between 1 and 100,000")
    
    base_url = os.getenv("BASE_URL", "https://agent-memory-api-production.up.railway.app")
    
    session = await PaymentProcessor.create_checkout_session(
        success_url=f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/payment/cancel",
        quantity=credits,
        service_type=service_type
    )
    
    return {
        "checkout_url": session['url'],
        "session_id": session['session_id'],
        "total_amount": session['amount_total'],
        "credits": credits,
        "service_type": service_type,
        "message": "Complete payment at checkout_url to receive your API key"
    }

@app.get("/payment/success")
async def payment_success(session_id: str):
    return {
        "status": "success",
        "message": "Payment successful! Your API key will be sent to your email.",
        "session_id": session_id,
        "next_steps": "Check your email for your API key and usage instructions"
    }

@app.get("/payment/cancel")
async def payment_cancel():
    return {
        "status": "cancelled",
        "message": "Payment was cancelled. You can try again at /purchase"
    }

@app.get("/pricing")
async def get_pricing():
    return {
        "store_memory": "$0.001 per memory stored",
        "retrieve_memory": "$0.001 per retrieval",
        "search_memories": "$0.005 per search",
        "delete_memory": "FREE",
        "agent_stats": "FREE",
        "storage_limits": "Unlimited (pay for what you use)",
        "retention": "30 days default, configurable up to forever",
        "encryption": "AES-256 encryption included",
        "payment_methods": ["stripe"],
        "bulk_pricing": {
            "1000_operations": "$1.00",
            "10000_operations": "$10.00",
            "100000_operations": "$100.00"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
