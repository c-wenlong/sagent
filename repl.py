#!/usr/bin/env python3
"""
Interactive REPL for sagent harness with streaming and loading animation.

Usage: python repl.py
"""

import os
import sys
import time
import threading
from dotenv import load_dotenv

from harness import AgentHarness, MemoryType

load_dotenv()


class Spinner:
    """Simple spinner animation for loading state."""

    def __init__(self, message="Thinking"):
        self.message = message
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.index = 0
        self.running = False
        self.thread = None

    def _spin(self):
        while self.running:
            frame = self.frames[self.index % len(self.frames)]
            sys.stdout.write(f"\r{frame} {self.message}...")
            sys.stdout.flush()
            self.index += 1
            time.sleep(0.08)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self, final_message=None):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        # Clear the spinner line
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()
        if final_message:
            print(final_message)


def stream_print(text, delay=0.01):
    """Print text character by character with a small delay."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def main():
    hydra_key = os.getenv("HYDRA_DB_API_KEY")
    tenant_id = os.getenv("HYDRA_DB_TENANT_ID")
    llm_key = os.getenv("NEBIUS_API_KEY")

    if not all([hydra_key, tenant_id, llm_key]):
        print("Error: Missing required environment variables.")
        print("Set HYDRA_DB_API_KEY, HYDRA_DB_TENANT_ID, NEBIUS_API_KEY in .env")
        sys.exit(1)

    harness = AgentHarness(
        api_key=hydra_key,
        tenant_id=tenant_id,
        llm_api_key=llm_key,
    )

    user_id = os.getenv("SAGENT_USER_ID", "default_user")

    print("\033[1m\033[94msagent\033[0m - AI Agent with Long-Term Memory")
    print("Type \033[92mhelp\033[0m for commands, \033[92mexit\033[0m to quit\n")

    while True:
        try:
            user_input = input("\033[96mYou\033[0m: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        if user_input.lower().startswith("remember "):
            content = user_input[9:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.FACT,
            )
            print(f"\033[92m✓\033[0m Stored: {content}")
            continue

        if user_input.lower().startswith("pref "):
            content = user_input[5:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.PREFERENCE,
            )
            print(f"\033[92m✓\033[0m Stored preference: {content}")
            continue

        if user_input.lower() == "memories":
            recent = harness.get_recent_memories(user_id, limit=10)
            if not recent:
                print("No memories found.")
            else:
                print(f"\n\033[1mRecent Memories:\033[0m")
                for i, m in enumerate(recent, 1):
                    type_icon = {
                        "fact": "📝",
                        "preference": "⚙️",
                        "interaction": "💬",
                        "thought": "💡",
                        "event": "📅",
                    }.get(m.type.value, "•")
                    content_preview = m.content[:60] + "..." if len(m.content) > 60 else m.content
                    print(f"  {type_icon} [{m.type.value}] {content_preview}")
            print()
            continue

        if user_input.lower() == "profile":
            profile = harness.profile(user_id)
            print(f"\n\033[1mProfile for {user_id}:\033[0m")
            print(f"  📝 Facts: {len(profile.facts)}")
            print(f"  ⚙️ Preferences: {len(profile.preferences)}")
            print(f"  💬 Interactions: {len(profile.interactions)}")
            print(f"  💡 Thoughts: {len(profile.thoughts)}")
            print(f"  📅 Events: {len(profile.events)}")
            print()
            continue

        if user_input.lower() == "clear":
            print("\033[2J\033[H", end="")
            continue

        if user_input.lower() == "help":
            print("""
\033[1mCommands:\033[0m
  \033[92mremember <text>\033[0m  - Store a fact (e.g., \033[90mremember I like coffee\033[0m)
  \033[92mpref <text>\033[0m         - Store a preference (e.g., \033[90mpref dark mode\033[0m)
  \033[92minteract <text>\033[0m   - Store an interaction
  \033[92mthink <text>\033[0m       - Store a thought
  \033[92mevent <text>\033[0m       - Store an event
  \033[92mmemories\033[0m          - Show recent memories
  \033[92mprofile\033[0m           - Show user profile summary
  \033[92mclear\033[0m             - Clear screen
  \033[92mhelp\033[0m             - Show this help
  \033[92mexit/quit\033[0m        - Exit

Or just type anything to chat with the agent!
""")
            continue

        # Handle interaction/thought/event shortcuts
        if user_input.lower().startswith("interact "):
            content = user_input[9:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.INTERACTION,
            )
            print(f"\033[92m✓\033[0m Stored interaction: {content}")
            continue

        if user_input.lower().startswith("think "):
            content = user_input[6:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.THOUGHT,
            )
            print(f"\033[92m✓\033[0m Stored thought: {content}")
            continue

        if user_input.lower().startswith("event "):
            content = user_input[6:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.EVENT,
            )
            print(f"\033[92m✓\033[0m Stored event: {content}")
            continue

        # Chat with the agent
        spinner = Spinner("Thinking")
        spinner.start()

        response = harness.think(
            prompt=user_input,
            user_id=user_id,
            store_interaction=True,
        )

        spinner.stop()

        print("\033[95mAgent\033[0m: ", end="", flush=True)
        stream_print(response, delay=0.005)
        print()


if __name__ == "__main__":
    main()
