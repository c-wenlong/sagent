# sagent - Simple Agent Harness with HydraDB

A minimal (~750 LoC) Python harness that wraps HydraDB to give AI agents long-term memory.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your HydraDB and Nebius keys
python demo.py
```

## HydraDB Setup

1. Sign up at [dashboard.hydradb.com](https://dashboard.hydradb.com)
2. Get your API key and tenant ID
3. Use promo code: `HYDRA2026` for hackathon credits

## Nebius Token Factory

Uses Nebius Token Factory for LLM calls. Get your API key at [tokenfactory.nebius.com](https://tokenfactory.nebius.com).

Default model: `zai-org/GLM-5.2`

## Usage

```python
from harness import AgentHarness, MemoryType

harness = AgentHarness(
    api_key="your-hydra-api-key",
    tenant_id="your-tenant-id",
    sub_tenant_id="default",
    llm_api_key="your-nebius-key",
)

user_id = "user_123"

# Store a memory
harness.remember(
    content="I'm learning Rust",
    user_id=user_id,
    memory_type=MemoryType.FACT,
)

# Ask with memory context
response = harness.think(
    prompt="What am I learning?",
    user_id=user_id,
)
```

## Architecture

```
AgentHarness
├── HydraDBClient     # Connection + operations (hydra-db-python SDK)
├── MemoryStore       # MemoryEntry CRUD
├── ContextBuilder    # Assemble memory → prompts
└── SessionManager    # Track sessions
```

## Memory Types

- `FACT` - Facts and knowledge
- `PREFERENCE` - User preferences
- `INTERACTION` - Conversations/events
- `THOUGHT` - Ideas and thoughts
- `EVENT` - Events and occurrences

## License

MIT
