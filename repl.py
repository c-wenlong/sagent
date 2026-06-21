#!/usr/bin/env python3
"""
Interactive REPL for sagent harness with streaming and loading animation.

Usage: python3 repl.py
"""

import os
import sys
import time
import threading
import queue
from dotenv import load_dotenv

from harness import AgentHarness, MemoryType

load_dotenv()

RESET = "\033[0m"
BOLD = "\033[1m"
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
FG_BOLD_GREEN = "\033[1;92m"
FG_BOLD_CYAN = "\033[1;96m"

COMMANDS = [
    ("remember <text>", "Store a fact"),
    ("pref <text>", "Store a preference"),
    ("interact <text>", "Store an interaction"),
    ("think <text>", "Store a thought"),
    ("event <text>", "Store an event"),
    ("memories", "Show recent memories"),
    ("profile", "Show user profile"),
    ("clear", "Clear screen"),
    ("help", "Show help"),
]

COMPLETIONS = [cmd for cmd, _ in COMMANDS]


class CommandCompleter:
    """Provides tab completion using readline."""

    def __init__(self, options):
        self.options = sorted(options)
        self.index = 0
        self.matches = []

    def complete(self, text, state):
        if state == 0:
            self.matches = [opt for opt in self.options if opt.startswith(text)]
            self.index = 0
        if self.index < len(self.matches):
            result = self.matches[self.index]
            self.index += 1
            return result
        return None


class ThinkingCanceller:
    """Handles thinking animation with Escape key cancellation."""

    def __init__(self, message="Thinking"):
        self.message = message
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.index = 0
        self.running = False
        self.cancelled = False
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

        if self.cancel_event.is_set() and self.running:
            sys.stdout.write(f"\r{FG_RED}✗ Cancelled{RESET}   ")
            sys.stdout.flush()

    def start(self):
        self.running = True
        self.cancelled = False
        self.cancel_event.clear()
        self.spinner_thread = threading.Thread(target=self._spinner_loop, daemon=True)
        self.spinner_thread.start()

    def was_cancelled(self):
        return self.cancel_event.is_set()

    def stop(self):
        self.running = False
        self.cancel_event.set()
        if self.spinner_thread:
            self.spinner_thread.join(timeout=0.5)
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()


def run_think_in_thread(harness, prompt, user_id, result_queue):
    """Run think() in thread and put result in queue."""
    try:
        response = harness.think(prompt=prompt, user_id=user_id, store_interaction=True)
        result_queue.put(("success", response))
    except Exception as e:
        result_queue.put(("error", str(e)))


def setup_readline():
    """Setup readline with tab completion."""
    try:
        import readline
        completer = CommandCompleter(COMPLETIONS)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("?: complete")
    except ImportError:
        pass


def print_user_message(text):
    """Print user message with background highlight."""
    lines = text.split("\n")
    print(f"{BG_USER}{FG_WHITE} {FG_CYAN}You:{RESET}")
    for line in lines:
        print(f"{BG_USER}{FG_WHITE} {line}{RESET}")
    print()


def print_agent_message(text):
    """Print agent message with background highlight."""
    lines = text.split("\n")
    print(f"{BG_AGENT}{FG_WHITE} {FG_MAGENTA}Agent:{RESET}")
    for line in lines:
        print(f"{BG_AGENT}{FG_WHITE} {line}{RESET}")
    print()


def print_system_message(text):
    """Print system message."""
    print(f"{FG_DIM}{text}{RESET}")


def print_success(text):
    """Print success message."""
    print(f"{FG_GREEN}✓ {text}{RESET}")


def print_error(text):
    """Print error message."""
    print(f"{FG_RED}✗ {text}{RESET}")


def print_header(text):
    """Print header banner."""
    print(f"{BG_HEADER}{FG_WHITE} {text} {RESET}")


def print_hint(text):
    """Print inline hint below input."""
    print(f"{FG_DIM}{text}{RESET}")


def main():
    hydra_key = os.getenv("HYDRA_DB_API_KEY")
    tenant_id = os.getenv("HYDRA_DB_TENANT_ID")
    llm_key = os.getenv("NEBIUS_API_KEY")

    if not all([hydra_key, tenant_id, llm_key]):
        print(f"{FG_YELLOW}Error: Missing required environment variables.{RESET}")
        print("Set HYDRA_DB_API_KEY, HYDRA_DB_TENANT_ID, NEBIUS_API_KEY in .env")
        sys.exit(1)

    harness = AgentHarness(
        api_key=hydra_key,
        tenant_id=tenant_id,
        llm_api_key=llm_key,
    )

    user_id = os.getenv("SAGENT_USER_ID", "default_user")

    setup_readline()

    print("\033[2J\033[H", end="")
    print_header("  sagent  ")
    print(f"{FG_DIM}Type {FG_GREEN}help{FG_DIM} for commands, {FG_GREEN}exit{FG_DIM} to quit")
    print(f"{FG_DIM}Press {FG_YELLOW}Esc{FG_DIM} during thinking to cancel")
    print()
    print_hint("Tip: Type / then press Tab to see commands")

    while True:
        try:
            user_input = input(f"{FG_CYAN}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input == "/":
            print_hint("")
            print_hint(f"{FG_BOLD_CYAN}Commands:{RESET} remember, pref, interact, think, event, memories, profile, clear, help")
            print_hint("Tab to autocomplete, or type full command")
            print_hint("")
            user_input = input(f"{FG_CYAN}> {RESET}").strip()
            while user_input == "/":
                print_hint(f"{FG_BOLD_CYAN}Commands:{RESET} remember, pref, interact, think, event, memories, profile, clear, help")
                user_input = input(f"{FG_CYAN}> {RESET}").strip()
            if not user_input:
                continue

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print_success("Goodbye!")
            break

        if user_input.lower().startswith("remember "):
            content = user_input[9:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.FACT,
            )
            print_success(f"Stored: {content}")
            continue

        if user_input.lower().startswith("pref "):
            content = user_input[5:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.PREFERENCE,
            )
            print_success(f"Stored preference: {content}")
            continue

        if user_input.lower().startswith("interact "):
            content = user_input[9:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.INTERACTION,
            )
            print_success(f"Stored interaction: {content}")
            continue

        if user_input.lower().startswith("think "):
            content = user_input[6:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.THOUGHT,
            )
            print_success(f"Stored thought: {content}")
            continue

        if user_input.lower().startswith("event "):
            content = user_input[6:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.EVENT,
            )
            print_success(f"Stored event: {content}")
            continue

        if user_input.lower() == "memories":
            recent = harness.get_recent_memories(user_id, limit=10)
            if not recent:
                print_system_message("No memories found.")
            else:
                print_header("Recent Memories")
                for m in recent:
                    type_icons = {
                        "fact": "📝",
                        "preference": "⚙️",
                        "interaction": "💬",
                        "thought": "💡",
                        "event": "📅",
                    }.get(m.type.value, "•")
                    content_preview = m.content[:70] + "..." if len(m.content) > 70 else m.content
                    print(f"  {type_icons} [{m.type.value}] {content_preview}")
            print()
            continue

        if user_input.lower() == "profile":
            profile = harness.profile(user_id)
            print_header(f" Profile: {user_id} ")
            print(f"  📝 Facts: {len(profile.facts)}")
            print(f"  ⚙️ Preferences: {len(profile.preferences)}")
            print(f"  💬 Interactions: {len(profile.interactions)}")
            print(f"  💡 Thoughts: {len(profile.thoughts)}")
            print(f"  📅 Events: {len(profile.events)}")
            print()
            continue

        if user_input.lower() == "clear":
            print("\033[2J\033[H", end="")
            print_header("  sagent  ")
            print(f"{FG_DIM}Type {FG_GREEN}help{FG_DIM} for commands, {FG_GREEN}exit{FG_DIM} to quit")
            print(f"{FG_DIM}Press {FG_YELLOW}Esc{FG_DIM} during thinking to cancel")
            print()
            print_hint("Tip: Type / then press Tab to see commands")
            continue

        if user_input.lower() == "help":
            print(f"""
{BG_HEADER} Commands {RESET}

  {FG_GREEN}remember <text>{RESET}  Store a fact
  {FG_GREEN}pref <text>{RESET}         Store a preference
  {FG_GREEN}interact <text>{RESET}    Store an interaction
  {FG_GREEN}think <text>{RESET}       Store a thought
  {FG_GREEN}event <text>{RESET}       Store an event
  {FG_GREEN}memories{RESET}            Show recent memories
  {FG_GREEN}profile{RESET}             Show user profile
  {FG_GREEN}clear{RESET}              Clear screen
  {FG_GREEN}help{FG_DIM}               Show this help
  {FG_GREEN}exit/quit{FG_DIM}          Exit

  {FG_YELLOW}Tab{RESET} - Autocomplete commands

Or just type anything to chat with the agent!
""")
            continue

        canceller = ThinkingCanceller("Thinking")
        canceller.start()

        result_queue = queue.Queue()
        think_thread = threading.Thread(
            target=run_think_in_thread,
            args=(harness, user_input, user_id, result_queue),
            daemon=True
        )
        think_thread.start()

        while think_thread.is_alive():
            if canceller.was_cancelled():
                time.sleep(0.1)
                break
            time.sleep(0.05)

        canceller.stop()

        if canceller.was_cancelled():
            print_error("Cancelled")
            print()
            continue

        think_thread.join(timeout=0.1)

        if not result_queue.empty():
            status, result = result_queue.get_nowait()
            if status == "success":
                print_agent_message(result)
            else:
                print_error(f"Error: {result}")
        print()


if __name__ == "__main__":
    main()
