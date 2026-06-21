# Changelog

All notable changes to sagent are documented here.

## [0.1.1] - 2026-06-21

### Added
- Interactive REPL (`repl.py`) with streaming output and loading animation
- Spinner animation while agent is thinking
- Pixel art avatars from `assets/icons/human.png` and `assets/icons/agent.png`
- Background highlighting for user/agent messages instead of labels
- Colorized terminal output (ANSI)
- All memory type shortcuts: remember, pref, interact, think, event
- REPL tests for avatar pixel loading
- **Escape key** cancels thinking (stops spinner, skips response)

### Changed
- N/A

### Fixed
- N/A

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
