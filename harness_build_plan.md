# AI Harness for HydraDB — Build Plan

## Overview
Minimal (~1000 LoC) Python harness that wraps HydraDB for long-term AI agent memory. Enable agents to remember, recall, and act on past interactions.

---

## Architecture

```
AgentHarness
├── HydraDBClient      # Connection + raw operations
├── MemoryStore        # Structured memory CRUD
├── ContextBuilder     # Assemble memory → prompt context
└── SessionManager     # Track session state + history
```

---

## File Structure

```
harness/
├── __init__.py           # Public exports
├── client.py             # HydraDB connection + basic ops (~120 lines)
├── memory.py             # MemoryEntry dataclass + MemoryStore class (~220 lines)
├── context.py            # ContextBuilder (~160 lines)
├── session.py            # SessionManager (~130 lines)
├── harness.py           # AgentHarness main class (~280 lines)
└── utils.py              # Helpers, embedding utils (~90 lines)
```

**Total: ~1000 lines**

---

## Data Model

### MemoryEntry
```python
@dataclass
class MemoryEntry:
    id: str                          # UUID
    type: MemoryType                 # FACT | PREFERENCE | INTERACTION | THOUGHT | EVENT
    content: str                     # Raw content
    embedding: Optional[List[float]] # Vector embedding
    metadata: Dict[str, Any]        # Source, tags, importance
    created_at: datetime
    updated_at: datetime
    session_id: Optional[str]       # Which session created this
    user_id: Optional[str]          # Whose memory
```

### MemoryStore Operations
- `add(entry)` → str (id)
- `recall(query, limit=5)` → List[MemoryEntry]
- `get_recent(user_id, limit=20)` → List[MemoryEntry]
- `get_by_type(user_id, type, limit)` → List[MemoryEntry]
- `update(id, content)` → bool
- `delete(id)` → bool

---

## ContextBuilder

Takes a prompt + user context → builds full context window:

```python
context = builder.build(
    prompt="what did I work on last week?",
    user_id="user_123",
    max_tokens=4000,
    include_types=[FACT, INTERACTION, EVENT],
    time_range=TimeRange(last_n_days=7)
)
```

Output:
```
## Recent Context
- [2026-06-20] INTERACTION: Discussed project X with Sarah
- [2026-06-19] FACT: Working on AI harness project

## Current Query
what did I work on last week?

## Relevant History
...
```

---

## SessionManager

- `start_session(user_id)` → session_id
- `end_session(session_id)` → summary (optional)
- `get_session_context(session_id)` → List[MemoryEntry] from this session
- `merge_to_long_term(session_id)` → moves session memories to persistent store

---

## AgentHarness Interface

```python
class AgentHarness:
    def __init__(self, hydra_db_url: str, api_key: str):
        ...

    def think(self, prompt: str, user_id: str) -> str:
        # 1. Build context from memory
        # 2. Call LLM with context
        # 3. Optionally store result as memory
        return response

    def remember(self, content: str, user_id: str, type: MemoryType = FACT):
        # Store new memory
        ...

    def recall(self, query: str, user_id: str) -> List[MemoryEntry]:
        # Semantic search on memories
        ...

    def profile(self, user_id: str) -> UserProfile:
        # Get user summary built from all their memories
        ...
```

---

## Implementation Steps

### Phase 1: Foundation (~30 min)
- [ ] Set up project structure
- [ ] Implement `client.py` — HydraDB connection
- [ ] Implement `memory.py` — MemoryEntry + MemoryStore

### Phase 2: Context Layer (~30 min)
- [ ] Implement `context.py` — ContextBuilder
- [ ] Implement `session.py` — SessionManager
- [ ] Implement `utils.py` — embedding helpers

### Phase 3: Integration (~30 min)
- [ ] Implement `harness.py` — AgentHarness
- [ ] Wire up HydraDB calls
- [ ] Add streaming response support (optional)

### Phase 4: Testing (~30 min)
- [ ] Write demo script showing memory across sessions
- [ ] Verify HydraDB read/write works
- [ ] Test context injection in prompts

---

## Demo Flow

```
Session 1:
  user: "I'm learning Rust and working on a project called OctoDB"
  harness.remember(user_id, content, type=FACT)

Session 2:
  user: "what am I working on?"
  harness.think() → "You're learning Rust and building OctoDB, a project..."
```

---

## HydraDB Setup

1. Sign up: dashboard.hydradb.com
2. Get API key + project URL
3. Use promo code: HYDRA2026 (for hackathon credits)
4. Create collection: "agent_memory"

---

## Dependencies

```txt
hydradb>=0.1.0       # Or actual HydraDB client SDK
openai>=1.0.0        # Or anthropic, for LLM calls
python-dotenv>=1.0.0
pydantic>=2.0
```

---

## Success Criteria

1. <1000 LoC total
2. Session 1 stores memory → Session 2 recalls it
3. Works with any LLM (OpenAI/Anthropic/etc.)
4. HydraDB persistence verified with execution logs
