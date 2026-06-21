# sagent - AI Harness with HydraDB for Long-Term Memory

A minimal (~750 LoC) Python harness that wraps HydraDB to give AI agents long-term memory. Enables agents to remember, recall, and act on past interactions across sessions.

## Features

- **Long-term memory** — Store and retrieve memories across sessions via HydraDB
- **Context-aware responses** — Memory context injected into prompts automatically
- **Session tracking** — Track conversation context per session
- **Multi-type memories** — FACT, PREFERENCE, INTERACTION, THOUGHT, EVENT
- **LLM agnostic** — Works with any Chat Completions API provider (Nebius, OpenAI, etc.)
- **Minimal footprint** — ~750 lines of code

## Quick Start

```bash
pip install -e .
cp .env.example .env
# Edit .env with your API keys
sagent          # interactive REPL
sagent demo     # cross-session memory demo
```

## Environment Variables

```env
HYDRA_DB_API_KEY=your-hydra-api-key
HYDRA_DB_TENANT_ID=your-tenant-id
HYDRA_DB_SUB_TENANT_ID=default  # optional
NEBIUS_API_KEY=your-nebius-api-key  # or any Chat Completions compatible key
```

## Usage

```python
from harness import AgentHarness, MemoryType

harness = AgentHarness(
    api_key="your-hydra-api-key",
    tenant_id="your-tenant-id",
    llm_api_key="your-llm-api-key",
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

# Get user profile
profile = harness.profile(user_id)
```

## Architecture

```
AgentHarness
├── HydraDBClient     # hydra-db-python SDK wrapper
├── MemoryStore      # MemoryEntry CRUD + HydraDB operations
├── ContextBuilder   # Assemble memory → prompt context
└── SessionManager  # Track session state (in-memory)
```

## Memory Types

| Type | Description |
|------|-------------|
| `FACT` | Facts and knowledge |
| `PREFERENCE` | User preferences |
| `INTERACTION` | Conversations/events |
| `THOUGHT` | Ideas and thoughts |
| `EVENT` | Events and occurrences |

## HydraDB Setup

1. Sign up at [dashboard.hydradb.com](https://dashboard.hydradb.com)
2. Create a tenant and get your API key
3. Use promo code: `HYDRA2026` for hackathon credits

## LLM Providers

Default: Nebius Token Factory (`zai-org/GLM-5.2`)

Any Chat Completions API compatible provider works. See `AGENTS.md` for changing providers.

## Testing

```bash
# Unit tests
pytest tests/test_harness.py -v

# Integration tests (requires API keys)
pytest tests/test_integration.py -v -m integration
```

## CI/CD

GitHub Actions runs on every push:
- Lint (ruff)
- Unit tests
- Integration tests (on main branch, requires secrets)

## License

MIT
