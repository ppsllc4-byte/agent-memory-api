import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from cryptography.fernet import Fernet
from dateutil import parser
import hashlib

DB_FILE = "memories_db.json"

class MemoryDatabase:
    def __init__(self):
        self.db_file = DB_FILE
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            self.cipher = Fernet(Fernet.generate_key())
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        if not os.path.exists(self.db_file):
            initial_data = {"memories": {}, "agents": {}}
            with open(self.db_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def _read_db(self) -> Dict:
        with open(self.db_file, 'r') as f:
            return json.load(f)
    
    def _write_db(self, data: Dict):
        with open(self.db_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def _generate_memory_id(self, agent_id: str, content: str) -> str:
        hash_input = f"{agent_id}{content}{datetime.utcnow().isoformat()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def _is_expired(self, expires_at: str) -> bool:
        if not expires_at:
            return False
        expiry = parser.parse(expires_at)
        return datetime.now(expiry.tzinfo) > expiry
    
    async def store_memory(self, agent_id: str, content: str, tags: List[str] = None, metadata: Dict[str, Any] = None, ttl_days: int = 30) -> Dict:
        db = self._read_db()
        if agent_id not in db["agents"]:
            db["agents"][agent_id] = {"agent_id": agent_id, "total_memories": 0, "storage_used_mb": 0.0, "created_at": datetime.utcnow().isoformat()}
        memory_id = self._generate_memory_id(agent_id, content)
        encrypted_content = self._encrypt(content)
        expires_at = None
        if ttl_days > 0:
            expires_at = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
        memory = {"memory_id": memory_id, "agent_id": agent_id, "content": encrypted_content, "tags": tags or [], "metadata": metadata or {}, "created_at": datetime.utcnow().isoformat(), "expires_at": expires_at, "access_count": 0, "last_accessed": None}
        db["memories"][memory_id] = memory
        db["agents"][agent_id]["total_memories"] += 1
        storage_mb = len(encrypted_content) / (1024 * 1024)
        db["agents"][agent_id]["storage_used_mb"] += storage_mb
        self._write_db(db)
        return {"memory_id": memory_id, "agent_id": agent_id, "tags": tags or [], "metadata": metadata or {}, "created_at": memory["created_at"], "expires_at": expires_at, "status": "stored"}
    
    async def retrieve_memory(self, memory_id: str) -> Optional[Dict]:
        db = self._read_db()
        memory = db["memories"].get(memory_id)
        if not memory:
            return None
        if self._is_expired(memory.get("expires_at")):
            del db["memories"][memory_id]
            self._write_db(db)
            return None
        try:
            decrypted_content = self._decrypt(memory["content"])
        except:
            return None
        memory["access_count"] += 1
        memory["last_accessed"] = datetime.utcnow().isoformat()
        self._write_db(db)
        return {"memory_id": memory_id, "agent_id": memory["agent_id"], "content": decrypted_content, "tags": memory["tags"], "metadata": memory["metadata"], "created_at": memory["created_at"], "expires_at": memory["expires_at"], "access_count": memory["access_count"], "last_accessed": memory["last_accessed"]}
    
    async def search_memories(self, agent_id: str, query: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 10) -> List[Dict]:
        db = self._read_db()
        results = []
        for memory_id, memory in db["memories"].items():
            if memory["agent_id"] != agent_id:
                continue
            if self._is_expired(memory.get("expires_at")):
                continue
            if tags and not any(tag in memory["tags"] for tag in tags):
                continue
            if query:
                try:
                    decrypted_content = self._decrypt(memory["content"])
                    if query.lower() not in decrypted_content.lower():
                        continue
                    content_preview = decrypted_content[:200]
                except:
                    continue
            else:
                content_preview = "[Encrypted]"
            results.append({"memory_id": memory_id, "tags": memory["tags"], "metadata": memory["metadata"], "content_preview": content_preview, "created_at": memory["created_at"], "access_count": memory["access_count"]})
            if len(results) >= limit:
                break
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results
    
    async def delete_memory(self, memory_id: str, agent_id: str) -> bool:
        db = self._read_db()
        memory = db["memories"].get(memory_id)
        if not memory or memory["agent_id"] != agent_id:
            return False
        storage_mb = len(memory["content"]) / (1024 * 1024)
        if agent_id in db["agents"]:
            db["agents"][agent_id]["total_memories"] -= 1
            db["agents"][agent_id]["storage_used_mb"] -= storage_mb
        del db["memories"][memory_id]
        self._write_db(db)
        return True
    
    async def get_agent_stats(self, agent_id: str) -> Optional[Dict]:
        db = self._read_db()
        agent = db["agents"].get(agent_id)
        if not agent:
            return None
        active_memories = 0
        for memory in db["memories"].values():
            if memory["agent_id"] == agent_id and not self._is_expired(memory.get("expires_at")):
                active_memories += 1
        return {"agent_id": agent_id, "active_memories": active_memories, "total_memories_stored": agent["total_memories"], "storage_used_mb": round(agent["storage_used_mb"], 2), "created_at": agent["created_at"]}
    
    async def cleanup_expired(self) -> int:
        db = self._read_db()
        expired_count = 0
        to_delete = []
        for memory_id, memory in db["memories"].items():
            if self._is_expired(memory.get("expires_at")):
                to_delete.append(memory_id)
                expired_count += 1
        for memory_id in to_delete:
            del db["memories"][memory_id]
        if expired_count > 0:
            self._write_db(db)
        return expired_count

db = MemoryDatabase()
