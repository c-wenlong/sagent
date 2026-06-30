# Changelog

All notable changes to sagent are documented here.

## [0.1.2] - 2026-06-25

### Added
- Server-side Pendo Track Event instrumentation (`harness/pendo.py`)
- 12 track events across the codebase:
  - `memory_stored` — fires after a memory is persisted to HydraDB
  - `memory_recalled` — fires after a semantic search/recall completes
  - `agent_query_completed` — fires after the LLM pipeline returns a response
  - `session_started` — fires when a new conversation session begins
  - `session_ended` — fires when a session is ended, includes duration and memory count
  - `user_profile_retrieved` — fires when a user's memory profile is aggregated
  - `chat_exchange_saved` — fires when `/save` persists a chat exchange
  - `autosave_toggled` — fires when `/autosave` changes the auto-save setting
  - `repl_session_started` — fires when the REPL is fully initialized
  - `memories_listed` — fires when `/memories` lists recent memories
  - `demo_completed` — fires when the cross-session demo finishes
  - `context_built` — fires when ContextBuilder assembles memory context
- Unit tests for pendo module (`tests/test_pendo.py`)

## [0.1.1] - 2026-06-21

### Added
- Interactive REPL (`repl.py`) with loading animation
- **`sagent` CLI command** — run `pip install -e .` then type `sagent` to start the REPL
- Spinner animation while agent is thinking
- Colorized terminal output (ANSI)
- All memory type shortcuts: remember, pref, interact, think, event
- REPL tests for session and command handling
- **Ctrl+C** cancels thinking (stops spinner, skips response)

### Changed
- **Opt-in memory storage** — chat no longer auto-saves to HydraDB; use `/save`, `/remember`, or other store commands
- REPL adds `/save` (last exchange or custom text) and `/autosave on|off` (set `SAGENT_AUTO_STORE=1` for default on)
- `AgentHarness.think()` defaults to `store_interaction=False`
- REPL rewritten without curses — uses standard `input()` loop to fix terminal glitches
- REPL slash commands use `prompt_toolkit` dropdown autocomplete (pi/opencode-style, non-blocking)
- REPL landing screen with Hermes-style ASCII banner, info panel, status bar, and prompt dividers
- `demo.py` rewritten as a structured two-act cross-session demo (sagent meta narrative, all 5 memory types, isolated sub-tenant)

### Fixed
- REPL TUI flicker and corrupted terminal state from curses/endwin/ANSI cursor juggling
- HydraDB recall used wrong chunk field (`content` → `chunk_content`) — recall returned nothing
- Memory types and user IDs now encoded in stored text for list API; metadata used on recall
- ContextBuilder filters memories by user_id
- REPL exit no longer prints "Goodbye" twice
- Integration tests use `MemoryType` enum instead of raw strings

## [0.1.0] - 2026-06-21

### Added
- Initial release: AgentHarness with HydraDB memory
- Memory types: FACT, PREFERENCE, INTERACTION, THOUGHT, EVENT
- ContextBuilder for assembling memory into prompts
- SessionManager for session tracking
- Nebius Token Factory as default LLM provider (GLM-5.2)
- Unit tests (17 tests)
- Integration tests
- GitHub Actions CI pipeline
- demo.py cross-session memory demonstration

### Fixed
- ContextBuilder now always shows current query even when no memories
- HydraDB SDK field names: `memory_id`/`memory_content` (not `source_id`/`content`)
- `sub_tenant_id` made optional (defaults to "default")
- Env var name: `HYDRA_DB_API_KEY` (not `HYDRADB_API_KEY`)

### Known Limitations
- SessionManager is in-memory (lost on restart)
- MemoryType taxonomy flattened by HydraDB's `infer=True` processing
- MemoryStore.update() and delete() are stubs (return False)
