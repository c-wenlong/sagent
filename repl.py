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

load_dotenv()

RESET = "\033[0m"
BG_USER = "\033[48;5;237m"
BG_AGENT = "\033[48;5;239m"
BG_HEADER = "\033[44m"
FG_WHITE = "\033[97m"
FG_GREEN = "\033[92m"
FG_CYAN = "\033[96m"
FG_YELLOW = "\033[93m"
FG_MAGENTA = "\033[95m"
FG_DIM = "\033[90m"
FG_RED = "\033[91m"
FG_BOLD_CYAN = "\033[1;96m"

PROMPT = f"{FG_CYAN}> {RESET}"

# Slash commands shown in the autocomplete dropdown (pi/opencode-style).
SLASH_COMMANDS = [
    {"name": "remember", "description": "Store a fact", "hint": "<text>"},
    {"name": "pref", "description": "Store a preference", "hint": "<text>"},
    {"name": "interact", "description": "Store an interaction", "hint": "<text>"},
    {"name": "think", "description": "Store a thought", "hint": "<text>"},
    {"name": "event", "description": "Store an event", "hint": "<text>"},
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


def print_banner():
    """Print the initial banner."""
    print("\033[2J\033[H", end="")
    print(f"{BG_HEADER}{FG_WHITE}  sagent  {RESET}")
    print(f"{FG_DIM}Type {FG_GREEN}/{FG_DIM} for commands, {FG_GREEN}help{FG_DIM} to list all, {FG_GREEN}exit{FG_DIM} to quit")
    print(f"{FG_DIM}Press {FG_YELLOW}Ctrl+C{FG_DIM} during thinking to cancel\n")


def print_agent_message(text):
    """Print agent message with background highlight."""
    lines = text.split("\n")
    print(f"{BG_AGENT}{FG_WHITE} {FG_MAGENTA}Agent:{RESET}")
    for line in lines:
        print(f"{BG_AGENT}{FG_WHITE} {line}{RESET}")
    print()


def print_success(text):
    """Print success message."""
    print(f"{FG_GREEN}✓ {text}{RESET}")


def print_error(text):
    """Print error message."""
    print(f"{FG_RED}✗ {text}{RESET}")


def print_header(text):
    """Print header banner."""
    print(f"{BG_HEADER}{FG_WHITE} {text} {RESET}")


def print_system_message(text):
    """Print system message."""
    print(f"{FG_DIM}{text}{RESET}")


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


def run_think_in_thread(harness, prompt, user_id, result_queue, cancel_event):
    """Run think() in a thread and put result in queue."""
    try:
        response = harness.think(prompt=prompt, user_id=user_id, store_interaction=True)
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
        print_header(f" Profile: {user_id} ")
        print(f"  📝 Facts: {len(profile.facts)}")
        print(f"  ⚙️ Preferences: {len(profile.preferences)}")
        print(f"  💬 Interactions: {len(profile.interactions)}")
        print(f"  💡 Thoughts: {len(profile.thoughts)}")
        print(f"  📅 Events: {len(profile.events)}")
        print()
        return True

    if user_input.lower() == "clear":
        print_banner()
        return True

    if user_input.lower() == "help":
        print(f"""
{BG_HEADER} Commands {RESET}

  {FG_GREEN}/remember <text>{RESET}  Store a fact
  {FG_GREEN}/pref <text>{RESET}         Store a preference
  {FG_GREEN}/interact <text>{RESET}    Store an interaction
  {FG_GREEN}/think <text>{RESET}       Store a thought
  {FG_GREEN}/event <text>{RESET}       Store an event
  {FG_GREEN}/memories{RESET}            Show recent memories
  {FG_GREEN}/profile{RESET}             Show user profile
  {FG_GREEN}/clear{RESET}              Clear screen
  {FG_GREEN}/help{FG_DIM}               Show this help
  {FG_GREEN}/exit{FG_DIM}               Exit

  {FG_DIM}Type {FG_GREEN}/{FG_DIM} to open the command menu while typing.
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


def read_input():
    """Read a line of input with slash-command autocomplete when attached to a TTY."""
    try:
        if sys.stdin.isatty():
            return get_prompt_session().prompt([("class:prompt", "> ")]).strip()
        return input(PROMPT).strip()
    except EOFError:
        print()
        raise SystemExit(0) from None
    except KeyboardInterrupt:
        print()
        raise SystemExit(0) from None


def chat_with_spinner(harness, user_id, user_input):
    """Send a chat message and show a spinner while waiting."""
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

    print_banner()

    while True:
        user_input = read_input()

        try:
            is_cmd = handle_command(user_input, harness, user_id)
        except SystemExit:
            print(f"{FG_GREEN}Goodbye!{RESET}")
            return

        if is_cmd or not user_input:
            continue

        chat_with_spinner(harness, user_id, user_input)


if __name__ == "__main__":
    main()
