# Agent Memory API

Persistent memory and context storage for AI agents. Rent a brain for your agent.

## What It Does

Provides encrypted, persistent memory storage for AI agents who have no memory between sessions.

## Features

- 🔐 AES-256 encryption by default
- 💾 Persistent storage with TTL
- 🔍 Semantic search capabilities
- 🏷️ Tag-based organization
- 📊 Usage statistics
- ⚡ Fast retrieval (<100ms)
- 💰 Pay-per-use pricing

## Endpoints

- `POST /memory/store` - Store encrypted memory ($0.001)
- `GET /memory/{id}` - Retrieve memory ($0.001)
- `POST /memory/search` - Search memories ($0.005)
- `DELETE /memory/{id}` - Delete memory (FREE)
- `GET /agent/{id}/stats` - Agent statistics (FREE)

## Pricing

- Store: $0.001 per memory
- Retrieve: $0.001 per query
- Search: $0.005 per search
- Delete: FREE
- Encryption: Included

## Use Cases

- Session continuity
- Context preservation
- Knowledge sharing between agents
- Long-term learning
- Collaborative agent memory

## Live API

Visit /docs for interactive documentation
