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
import curses
from dotenv import load_dotenv

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


def print_banner():
    """Print the initial banner."""
    print("\033[2J\033[H", end="")
    print(f"{BG_HEADER}{FG_WHITE}  sagent  {RESET}")
    print(f"{FG_DIM}Type {FG_GREEN}help{FG_DIM} for commands, {FG_GREEN}exit{FG_DIM} to quit")
    print(f"{FG_DIM}Press {FG_YELLOW}Esc{FG_DIM} during thinking to cancel\n")
    print(f"{FG_BOLD_CYAN}Tip:{RESET} Type {FG_GREEN}/{RESET} then Tab to autocomplete commands\n")


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


class ThinkingCanceller:
    """Handles thinking animation with Escape key cancellation."""

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
        if self.cancel_event.is_set() and self.running:
            sys.stdout.write(f"\r{FG_RED}✗ Cancelled{RESET}   ")
            sys.stdout.flush()

    def start(self):
        self.running = True
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


def handle_command(user_input, harness, user_id):
    """Process a command. Returns True if was a command (not chat), False if chat."""
    if not user_input:
        return True

    if user_input.lower() in ("exit", "quit", "q"):
        print_success("Goodbye!")
        sys.exit(0)

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
        return True

    return False


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    hydra_key = os.getenv("HYDRA_DB_API_KEY")
    tenant_id = os.getenv("HYDRA_DB_TENANT_ID")
    llm_key = os.getenv("NEBIUS_API_KEY")

    if not all([hydra_key, tenant_id, llm_key]):
        curses.endwin()
        print(f"{FG_YELLOW}Error: Missing required environment variables.{RESET}")
        print("Set HYDRA_DB_API_KEY, HYDRA_DB_TENANT_ID, NEBIUS_API_KEY in .env")
        return

    harness = AgentHarness(api_key=hydra_key, tenant_id=tenant_id, llm_api_key=llm_key)
    user_id = os.getenv("SAGENT_USER_ID", "default_user")

    curses.endwin()
    print_banner()

    input_buffer = ""
    canceller = ThinkingCanceller()
    result_queue = queue.Queue()
    think_thread = None

    while True:
        curses.endwin()
        sys.stdout.write(f"{FG_CYAN}> {RESET}{input_buffer}\033[0G")
        sys.stdout.write(f"\033[{len(input_buffer)}C")
        sys.stdout.flush()

        key = stdscr.getch()

        if key == curses.ERR:
            if canceller.running:
                if canceller.was_cancelled():
                    canceller.stop()
                    print_error("Cancelled")
                    print()
                    canceller = ThinkingCanceller()
                    result_queue = queue.Queue()
                    think_thread = None
                elif not result_queue.empty():
                    canceller.stop()
                    status, result = result_queue.get_nowait()
                    if status == "success":
                        print_agent_message(result)
                    else:
                        print_error(f"Error: {result}")
                    print()
                    canceller = ThinkingCanceller()
                    result_queue = queue.Queue()
                    think_thread = None
            continue

        if key in (curses.KEY_ENTER, 10, 13):
            user_input = input_buffer.strip()
            input_buffer = ""
            print()
            curses.endwin()

            is_cmd = handle_command(user_input, harness, user_id)
            if is_cmd:
                continue

            if not user_input:
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
            continue

        if key == curses.KEY_BACKSPACE or key in (127,):
            input_buffer = input_buffer[:-1]
            continue

        if key == 9:
            if input_buffer == "":
                input_buffer = "/"
            elif input_buffer == "/":
                matches = [c for c in COMPLETIONS if c.startswith("/")]
                if matches:
                    input_buffer = matches[0]
            continue

        if key == 27:
            if canceller.running and not canceller.was_cancelled():
                canceller.cancel_event.set()
            input_buffer = ""
            continue

        if key in (3, 4):
            curses.endwin()
            print(f"{FG_GREEN}Goodbye!{RESET}")
            return

        if 32 <= key <= 126:
            ch = chr(key)
            if ch == "/" and input_buffer == "":
                input_buffer = ch
            elif ch.isprintable():
                input_buffer += ch


if __name__ == "__main__":
    curses.wrapper(main)
