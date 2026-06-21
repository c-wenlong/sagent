# AGENTS.md — Instructions for AI Assistants

This file contains guidance for AI assistants working on or with the sagent project.
**Always read CHANGELOG.md first when working with this codebase.**

---

## Project Overview

sagent is a Python harness (~750 LoC) that gives AI agents long-term memory using HydraDB.
It wraps the hydra-db-python SDK and provides a simple interface for storing/recalling memories.

## Key Files

- `harness/harness.py` — `AgentHarness` main class
- `harness/client.py` — HydraDB SDK wrapper
- `harness/memory.py` — `MemoryStore` + `MemoryEntry`
- `harness/context.py` — `ContextBuilder` for prompt assembly
- `harness/session.py` — `SessionManager`
- `demo.py` — Working demonstration
- `CHANGELOG.md` — **Always check this before making changes**

## Changing LLM Providers

sagent uses the OpenAI-compatible Chat Completions API. To switch providers:

### 1. Update Default Constants (harness/harness.py)

```python
DEFAULT_MODEL = "your-model"
DEFAULT_BASE_URL = "https://api.provider.com/v1/"
```

### 2. Update Environment Variable

In `.env` and `.env.example`:
```
NEBIUS_API_KEY=your-provider-key
```

### 3. Common Provider Configurations

| Provider | Base URL | Model Example |
|----------|----------|---------------|
| Nebius Token Factory | `https://api.tokenfactory.nebius.com/v1/` | `zai-org/GLM-5.2` |
| OpenAI | `https://api.openai.com/v1/` | `gpt-4` |
| Groq | `https://api.groq.com/openai/v1/` | `llama-3.1-70b` |
| Cerebras | `https://api.cerebras.ai/v1/` | `cerebras/Llama-3.3-70B` |
| LM Studio | `http://localhost:8000/v1/` | `local-model` |

### 4. Update README.md

Update the "LLM Providers" section and "Environment Variables" section.

### 5. No Code Changes Needed

The `OpenAI` client from the `openai` package is OpenAI-compatible and works with any
provider that implements the Chat Completions API. Just set `base_url` and `api_key`.

## Changing Vector Database Providers

Currently uses HydraDB. To switch:

1. Rewrite `harness/client.py` to use new provider's SDK
2. Update `harness/memory.py` `MemoryStore` methods to match new API
3. Update `requirements.txt`
4. Document in CHANGELOG.md

## Running Tests

```bash
# All unit tests
pytest tests/test_harness.py -v

# Specific test class
pytest tests/test_harness.py::TestMemoryEntry -v

# Skip integration tests (don't need API keys)
pytest tests/ -v -m "not integration"
```

## Common Tasks

### Add a new MemoryType
1. Add to `MemoryType` enum in `harness/memory.py`
2. Update `ContextBuilder._group_by_type()` if needed
3. Update `AgentHarness.profile()` if needed
4. Document in CHANGELOG.md

### Add a new method to AgentHarness
1. Add to `harness/harness.py`
2. Add unit test in `tests/test_harness.py`
3. If uses LLM, handle `llm is None` fallback case
4. Document in CHANGELOG.md

### Modify HydraDB Integration
1. Check `harness/client.py` — this is the only file that directly calls HydraDB SDK
2. SDK reference: https://docs.hydradb.com/api-reference/sdks
3. Document API changes in CHANGELOG.md

## Before Committing

1. Run `pytest tests/test_harness.py -v` — all tests must pass
2. Run `ruff check .` — no lint errors
3. Update CHANGELOG.md with your changes
4. Do not commit `.env` or API keys

## Test Requirements

**Write tests for every new feature or change.** This is enforced.

### Adding a new feature
1. Write unit tests in `tests/test_harness.py`
2. Write integration tests in `tests/test_integration.py` if it touches HydraDB or LLM
3. Run `pytest tests/test_harness.py -v` — all tests must pass before committing

### Fixing a bug
1. Write a test that reproduces the bug
2. Fix the bug
3. Verify the test passes
4. Commit with the fix

### Test categories
- **Unit tests** (`tests/test_harness.py`) — Mock HydraDB/LLM, fast, no API keys needed
- **Integration tests** (`tests/test_integration.py`) — Real API calls, requires secrets, skip locally without keys

## Architecture Notes

- Memory is external (HydraDB), not in LLM conversation state
- This is intentional — allows multiple agents to share memory
- `infer=True` is used for HydraDB's graph construction
- SessionManager is in-memory only (could be extended to persist)
