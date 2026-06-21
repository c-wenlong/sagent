#!/usr/bin/env python3
"""
Interactive REPL for sagent harness with streaming and loading animation.

Usage: python3 repl.py
"""

import os
import sys
import time
import threading
import select
from dotenv import load_dotenv
from PIL import Image

from harness import AgentHarness, MemoryType

load_dotenv()

BOLD = "\033[1m"
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


def load_avatar_pixels(img_path, max_width=20, max_height=12):
    """Load and resize image to pixel art, return list of ANSI color codes per row."""
    img = Image.open(img_path).convert("RGB")
    img = img.resize((max_width, max_height), Image.Resampling.NEAREST)
    pixels = img.load()
    width, height = img.size

    def rgb_to_ansi(r, g, b):
        if r == g == b:
            return 16 if r < 128 else 231
        if r > 200 and g < 100 and b < 100:
            return 196
        if r > 200 and g > 200 and b < 100:
            return 226
        if r < 100 and g > 200 and b < 100:
            return 46
        if r < 100 and g > 200 and b > 200:
            return 51
        if r < 100 and g < 100 and b > 200:
            return 21
        if r > 200 and g < 100 and b > 200:
            return 201
        return 255

    result = []
    for y in range(height):
        row = []
        for x in range(width):
            r, g, b = pixels[x, y]
            row.append(rgb_to_ansi(r, g, b))
        result.append(row)
    return result


AVATAR_HUMAN = load_avatar_pixels("assets/icons/human.png", 20, 12)
AVATAR_AGENT = load_avatar_pixels("assets/icons/agent.png", 20, 12)


class Spinner:
    """Spinner animation with Escape key detection."""

    def __init__(self, message="Thinking"):
        self.message = message
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.index = 0
        self.running = False
        self.thread = None
        self.cancelled = False

    def _spin(self):
        while self.running:
            # Check for Escape key press (non-blocking)
            if self._escape_pressed():
                self.cancelled = True
                self.running = False
                sys.stdout.write(f"\r{FG_RED}✗ Cancelled{RESET}")
                sys.stdout.flush()
                return

            frame = self.frames[self.index % len(self.frames)]
            sys.stdout.write(f"\r{FG_YELLOW}{frame}{RESET} {self.message}...")
            sys.stdout.flush()
            self.index += 1
            time.sleep(0.08)

    def _escape_pressed(self):
        """Check if Escape key was pressed (non-blocking read)."""
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape
                # Drain any remaining escape sequence characters
                while select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.read(1)
                return True
            # Put non-escape chars back would be complex, so we just note it
        return False

    def start(self):
        self.running = True
        self.cancelled = False
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def is_cancelled(self):
        return self.cancelled


def print_agent_message(text):
    """Print agent message with background highlight and avatar."""
    lines = text.split("\n")
    print(f"{BG_AGENT}{FG_WHITE}{BOLD} {RESET}", end="")
    for color in AVATAR_AGENT[0]:
        print(f"\033[48;5;{color}m  ", end="")
    print(f"\033[0m {FG_MAGENTA}{BOLD}Agent:{RESET}")
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


def stream_print(text):
    """Print text character by character."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.003)
    print()


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

    print("\033[2J\033[H", end="")
    print_header("  sagent  ")
    print(f"{FG_DIM}Type {FG_GREEN}help{FG_DIM} for commands, {FG_GREEN}exit{FG_DIM} to quit")
    print(f"{FG_DIM}Press {FG_YELLOW}Esc{FG_DIM} during thinking to cancel\n")

    while True:
        try:
            user_input = input(f"{FG_CYAN}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

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
            print(f"{FG_DIM}Press {FG_YELLOW}Esc{FG_DIM} during thinking to cancel\n")
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
  {FG_GREEN}help{FG_GREEN}               Show this help
  {FG_GREEN}exit/quit{FG_GREEN}          Exit

  {FG_YELLOW}Esc{RESET} - Cancel during thinking

Or just type anything to chat with the agent!
""")
            continue

        spinner = Spinner("Thinking")
        spinner.start()

        response = harness.think(
            prompt=user_input,
            user_id=user_id,
            store_interaction=True,
        )

        spinner.stop()

        if spinner.is_cancelled():
            print_error("Cancelled")
            print()
            continue

        print_agent_message(response)
        print()


if __name__ == "__main__":
    main()
