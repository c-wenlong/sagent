#!/usr/bin/env python3
"""
Interactive REPL for sagent harness with loading animation.

Usage: python3 repl.py
"""

import os
import queue
import sys
import threading
import time

from dotenv import load_dotenv
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession
from prompt_toolkit.styles import Style

from harness import AgentHarness, MemoryType
from repl_tui import (
    FG_CYAN,
    FG_DIM,
    FG_GREEN,
    FG_YELLOW,
    RESET,
    memory_count,
    print_agent_message,
    print_error,
    print_header,
    print_landing_screen,
    print_prompt_divider,
    print_status_bar,
    print_success,
    print_system_message,
    print_user_message,
)

load_dotenv()

PROMPT = f"{FG_CYAN}> {RESET}"

SLASH_COMMANDS = [
    {"name": "remember", "description": "Store a fact", "hint": "<text>"},
    {"name": "pref", "description": "Store a preference", "hint": "<text>"},
    {"name": "interact", "description": "Store an interaction", "hint": "<text>"},
    {"name": "think", "description": "Store a thought", "hint": "<text>"},
    {"name": "event", "description": "Store an event", "hint": "<text>"},
    {"name": "save", "description": "Save last chat exchange (or custom text)", "hint": "[text]"},
    {"name": "autosave", "description": "Toggle auto-save of chat exchanges", "hint": "on|off"},
    {"name": "memories", "description": "Show recent memories"},
    {"name": "profile", "description": "Show user profile"},
    {"name": "clear", "description": "Clear screen"},
    {"name": "help", "description": "Show help"},
    {"name": "exit", "description": "Exit the REPL"},
]

COMMANDS = [(f"{c['name']} {c['hint']}" if c.get("hint") else c["name"], c["description"]) for c in SLASH_COMMANDS]
COMPLETIONS = [cmd["name"] for cmd in SLASH_COMMANDS]

PROMPT_STYLE = Style.from_dict({"prompt": "ansicyan bold"})
_PROMPT_SESSION: PromptSession | None = None
_RUNTIME: dict = {}


def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def _auto_store_enabled() -> bool:
    return bool(_RUNTIME.get("auto_store", False))


def _interaction_content(prompt: str, response: str) -> str:
    preview = response[:200]
    if len(response) > 200:
        preview += "..."
    return f"User asked: {prompt}. Agent responded: {preview}"


def normalize_user_input(user_input: str) -> str:
    """Strip leading slash so `/remember foo` and `remember foo` both work."""
    text = user_input.strip()
    if text.startswith("/"):
        return text[1:]
    return text


def filter_slash_commands(prefix: str) -> list[dict]:
    """Filter slash commands by prefix, with fuzzy fallback like pi."""
    if not prefix:
        return SLASH_COMMANDS
    lower = prefix.lower()
    starts_with = [cmd for cmd in SLASH_COMMANDS if cmd["name"].lower().startswith(lower)]
    if starts_with:
        return starts_with
    return [cmd for cmd in SLASH_COMMANDS if lower in cmd["name"].lower()]


class SlashCommandCompleter(Completer):
    """Non-blocking slash-command dropdown, triggered when input starts with /."""

    def get_completions(self, document: Document, complete_event):
        line = document.text_before_cursor
        if not line.startswith("/"):
            return
        if " " in line:
            return

        prefix = line[1:]
        for cmd in filter_slash_commands(prefix):
            name = cmd["name"]
            meta = cmd["description"]
            if cmd.get("hint"):
                meta = f"{cmd['hint']} — {meta}"
            yield Completion(
                name,
                start_position=-len(prefix),
                display=HTML(f"<ansigreen>/{name}</ansigreen>"),
                display_meta=meta,
            )


def complete_slash_command(buffer: str) -> str:
    """Expand a partial slash command (used by tests and tab-style helpers)."""
    if not buffer.startswith("/"):
        return buffer
    prefix = buffer[1:]
    matches = filter_slash_commands(prefix)
    if not matches:
        return buffer
    return f"/{matches[0]['name']}"


def get_prompt_session() -> PromptSession:
    global _PROMPT_SESSION
    if _PROMPT_SESSION is None:
        _PROMPT_SESSION = PromptSession(
            completer=SlashCommandCompleter(),
            complete_style=CompleteStyle.COLUMN,
            complete_while_typing=True,
            style=PROMPT_STYLE,
        )
    return _PROMPT_SESSION


class ThinkingCanceller:
    """Spinner shown while the agent is thinking."""

    def __init__(self, message="Thinking"):
        self.message = message
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.index = 0
        self.running = False
        self.spinner_thread = None
        self.cancel_event = threading.Event()

    def _spinner_loop(self):
        while self.running and not self.cancel_event.is_set():
            frame = self.frames[self.index % len(self.frames)]
            sys.stdout.write(f"\r{FG_YELLOW}{frame}{RESET} {self.message}...")
            sys.stdout.flush()
            self.index += 1
            for _ in range(8):
                if self.cancel_event.is_set():
                    return
                time.sleep(0.01)

    def start(self):
        self.running = True
        self.cancel_event.clear()
        self.spinner_thread = threading.Thread(target=self._spinner_loop, daemon=True)
        self.spinner_thread.start()

    def was_cancelled(self):
        return self.cancel_event.is_set()

    def stop(self):
        self.running = False
        if self.spinner_thread:
            self.spinner_thread.join(timeout=0.5)
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def cancel(self):
        """Cancel thinking immediately."""
        self.cancel_event.set()


def run_think_in_thread(harness, prompt, user_id, result_queue, cancel_event, store_interaction=False):
    """Run think() in a thread and put result in queue."""
    try:
        response = harness.think(
            prompt=prompt,
            user_id=user_id,
            store_interaction=store_interaction,
        )
        if not cancel_event.is_set():
            result_queue.put(("success", response))
    except Exception as e:
        if not cancel_event.is_set():
            result_queue.put(("error", str(e)))


def handle_command(user_input, harness, user_id):
    """Process a command. Returns True if was a command (not chat), False if chat."""
    user_input = normalize_user_input(user_input)

    if not user_input:
        return True

    if user_input.lower() in ("exit", "quit", "q"):
        raise SystemExit(0)

    if user_input.lower().startswith("remember "):
        content = user_input[9:].strip()
        harness.remember(content=content, user_id=user_id, memory_type=MemoryType.FACT)
        print_success(f"Stored: {content}")
        return True

    if user_input.lower().startswith("pref "):
        content = user_input[5:].strip()
        harness.remember(content=content, user_id=user_id, memory_type=MemoryType.PREFERENCE)
        print_success(f"Stored preference: {content}")
        return True

    if user_input.lower().startswith("interact "):
        content = user_input[9:].strip()
        harness.remember(content=content, user_id=user_id, memory_type=MemoryType.INTERACTION)
        print_success(f"Stored interaction: {content}")
        return True

    if user_input.lower().startswith("think "):
        content = user_input[6:].strip()
        harness.remember(content=content, user_id=user_id, memory_type=MemoryType.THOUGHT)
        print_success(f"Stored thought: {content}")
        return True

    if user_input.lower().startswith("event "):
        content = user_input[6:].strip()
        harness.remember(content=content, user_id=user_id, memory_type=MemoryType.EVENT)
        print_success(f"Stored event: {content}")
        return True

    if user_input.lower() == "save" or user_input.lower().startswith("save "):
        custom = user_input[4:].strip() if user_input.lower().startswith("save ") else ""
        if custom:
            content = custom
        else:
            exchange = _RUNTIME.get("last_exchange")
            if not exchange:
                print_system_message("Nothing to save yet — chat first, then /save.")
                print()
                return True
            content = _interaction_content(exchange["prompt"], exchange["response"])
        harness.remember(content=content, user_id=user_id, memory_type=MemoryType.INTERACTION)
        print_success("Stored interaction.")
        return True

    if user_input.lower() in ("autosave", "autosave on", "autosave off"):
        if user_input.lower() == "autosave on":
            _RUNTIME["auto_store"] = True
        elif user_input.lower() == "autosave off":
            _RUNTIME["auto_store"] = False
        else:
            _RUNTIME["auto_store"] = not _auto_store_enabled()
        state = "on" if _auto_store_enabled() else "off"
        print_success(f"Auto-save is {state}.")
        return True

    if user_input.lower() == "memories":
        recent = harness.get_recent_memories(user_id, limit=10)
        if not recent:
            print_system_message("No memories found.")
        else:
            print_header("Recent Memories")
            for m in recent:
                type_icons = {
                    "fact": "📝", "preference": "⚙️", "interaction": "💬",
                    "thought": "💡", "event": "📅",
                }.get(m.type.value, "•")
                preview = m.content[:70] + "..." if len(m.content) > 70 else m.content
                print(f"  {type_icons} [{m.type.value}] {preview}")
        print()
        return True

    if user_input.lower() == "profile":
        profile = harness.profile(user_id)
        print_header(f"Profile: {user_id}")
        print(f"  📝 Facts: {len(profile.facts)}")
        print(f"  ⚙️ Preferences: {len(profile.preferences)}")
        print(f"  💬 Interactions: {len(profile.interactions)}")
        print(f"  💡 Thoughts: {len(profile.thoughts)}")
        print(f"  📅 Events: {len(profile.events)}")
        print()
        return True

    if user_input.lower() == "clear":
        runtime_harness = _RUNTIME.get("harness", harness)
        runtime_user = _RUNTIME.get("user_id", user_id)
        runtime_model = _RUNTIME.get("model", getattr(runtime_harness, "llm_model", "unknown"))
        print_landing_screen(
            harness=runtime_harness,
            user_id=runtime_user,
            model=runtime_model,
            session_id=_RUNTIME.get("session_id"),
        )
        if _RUNTIME.get("harness"):
            _refresh_status_bar()
        return True

    if user_input.lower() == "help":
        print(f"""
{FG_GREEN}Slash Commands{RESET}

  {FG_GREEN}/remember <text>{RESET}  Store a fact
  {FG_GREEN}/pref <text>{RESET}         Store a preference
  {FG_GREEN}/interact <text>{RESET}    Store an interaction
  {FG_GREEN}/think <text>{RESET}       Store a thought
  {FG_GREEN}/event <text>{RESET}       Store an event
  {FG_GREEN}/save{RESET}               Save the last chat exchange
  {FG_GREEN}/save <text>{RESET}        Save custom interaction text
  {FG_GREEN}/autosave on|off{RESET}    Toggle auto-save of chat turns
  {FG_GREEN}/memories{RESET}            Show recent memories
  {FG_GREEN}/profile{RESET}             Show user profile
  {FG_GREEN}/clear{RESET}              Clear screen
  {FG_GREEN}/help{RESET}               Show this help
  {FG_GREEN}/exit{RESET}               Exit

  {FG_DIM}Chat is ephemeral by default — use {FG_GREEN}/save{FG_DIM} or {FG_GREEN}/remember{FG_DIM} to persist.
Type {FG_GREEN}/{FG_DIM} while typing to open the command menu.
Or just type anything to chat with the agent!
""")
        return True

    return False


class REPLSession:
    """Testable REPL session state for async thinking."""

    def __init__(self, harness, user_id):
        self.harness = harness
        self.user_id = user_id
        self.canceller = ThinkingCanceller()
        self.result_queue = queue.Queue()
        self.think_thread = None

    def start_thinking(self, user_input):
        """Start the thinking process for user input."""
        self.canceller = ThinkingCanceller("Thinking")
        self.canceller.start()
        self.result_queue = queue.Queue()
        self.think_thread = threading.Thread(
            target=run_think_in_thread,
            args=(
                self.harness,
                user_input,
                self.user_id,
                self.result_queue,
                self.canceller.cancel_event,
                _auto_store_enabled(),
            ),
            daemon=True,
        )
        self.think_thread.start()

    def is_thinking(self):
        """Check if currently thinking."""
        return self.think_thread is not None and self.think_thread.is_alive()

    def is_cancelled(self):
        """Check if thinking was cancelled."""
        return self.canceller.was_cancelled()

    def cancel_thinking(self):
        """Cancel the current thinking."""
        self.canceller.cancel()

    def wait_for_result(self, poll_interval=0.1):
        """Block until thinking finishes or is cancelled. Returns (status, result) or None."""
        while self.is_thinking():
            time.sleep(poll_interval)
        self.canceller.stop()
        if self.is_cancelled():
            return None
        if not self.result_queue.empty():
            return self.result_queue.get_nowait()
        return None


def _refresh_status_bar() -> None:
    harness = _RUNTIME.get("harness")
    user_id = _RUNTIME.get("user_id", "")
    if not harness:
        return
    count = memory_count(harness, user_id)
    print_status_bar(model=_RUNTIME.get("model", ""), user_id=user_id, memory_count=count)


def read_input():
    """Read a line of input with slash-command autocomplete when attached to a TTY."""
    try:
        if sys.stdin.isatty():
            print_prompt_divider()
            return get_prompt_session().prompt([("class:prompt", "❯ ")]).strip()
        return input(PROMPT).strip()
    except EOFError:
        print()
        raise SystemExit(0) from None
    except KeyboardInterrupt:
        print()
        raise SystemExit(0) from None


def chat_with_spinner(harness, user_id, user_input):
    """Send a chat message and show a spinner while waiting."""
    print_user_message(user_input)
    session = REPLSession(harness, user_id)
    session.start_thinking(user_input)

    try:
        while session.is_thinking():
            time.sleep(0.1)
    except KeyboardInterrupt:
        session.cancel_thinking()
        session.wait_for_result()
        print_error("Cancelled")
        print()
        return

    result = session.wait_for_result()
    if result is None:
        print_error("Cancelled")
        print()
        return

    status, response = result
    if status == "success":
        print_agent_message(response)
        _RUNTIME["last_exchange"] = {"prompt": user_input, "response": response}
        if not _auto_store_enabled():
            print(f"{FG_DIM}Tip: {FG_GREEN}/save{FG_DIM} to store this exchange.{RESET}")
    else:
        print_error(f"Error: {response}")
        print()


def main():
    hydra_key = os.getenv("HYDRA_DB_API_KEY")
    tenant_id = os.getenv("HYDRA_DB_TENANT_ID")
    llm_key = os.getenv("NEBIUS_API_KEY")

    if not all([hydra_key, tenant_id, llm_key]):
        print(f"{FG_YELLOW}Error: Missing required environment variables.{RESET}")
        print("Set HYDRA_DB_API_KEY, HYDRA_DB_TENANT_ID, NEBIUS_API_KEY in .env")
        return

    harness = AgentHarness(api_key=hydra_key, tenant_id=tenant_id, llm_api_key=llm_key)
    user_id = os.getenv("SAGENT_USER_ID", "default_user")
    session = harness.start_session(user_id)

    _RUNTIME.update(
        harness=harness,
        user_id=user_id,
        session_id=session.id,
        model=harness.llm_model,
        auto_store=_env_flag("SAGENT_AUTO_STORE", False),
        last_exchange=None,
    )

    print_landing_screen(
        harness=harness,
        user_id=user_id,
        model=harness.llm_model,
        session_id=session.id,
    )
    _refresh_status_bar()

    while True:
        user_input = read_input()

        try:
            is_cmd = handle_command(user_input, harness, user_id)
        except SystemExit:
            harness.end_session(session.id)
            print(f"{FG_GREEN}Goodbye!{RESET}")
            return

        if is_cmd or not user_input:
            continue

        chat_with_spinner(harness, user_id, user_input)
        _refresh_status_bar()


if __name__ == "__main__":
    main()
