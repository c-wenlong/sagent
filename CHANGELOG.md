# Changelog

All notable changes to sagent are documented here.

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
- REPL rewritten without curses — uses standard `input()` loop to fix terminal glitches
- REPL slash commands use `prompt_toolkit` dropdown autocomplete (pi/opencode-style, non-blocking)
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
