#!/usr/bin/env python3
"""
Interactive REPL for sagent harness

Usage: python repl.py
"""

import os
import sys
from dotenv import load_dotenv

from harness import AgentHarness, MemoryType

load_dotenv()


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

    print("=" * 60)
    print("sagent REPL - Type 'exit' to quit, 'remember <text>' to store")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
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
            print(f"Stored: {content}")
            continue

        if user_input.lower().startswith("pref "):
            content = user_input[5:].strip()
            harness.remember(
                content=content,
                user_id=user_id,
                memory_type=MemoryType.PREFERENCE,
            )
            print(f"Stored preference: {content}")
            continue

        if user_input.lower() == "memories":
            recent = harness.get_recent_memories(user_id, limit=10)
            if not recent:
                print("No memories found.")
            else:
                for m in recent:
                    print(f"  [{m.type.value}] {m.content[:80]}")
            continue

        if user_input.lower() == "profile":
            profile = harness.profile(user_id)
            print(f"Profile for {user_id}:")
            print(f"  Facts: {len(profile.facts)}")
            print(f"  Preferences: {len(profile.preferences)}")
            print(f"  Interactions: {len(profile.interactions)}")
            print(f"  Thoughts: {len(profile.thoughts)}")
            print(f"  Events: {len(profile.events)}")
            continue

        if user_input.lower() == "help":
            print("Commands:")
            print("  remember <text>  - Store a fact")
            print("  pref <text>      - Store a preference")
            print("  memories         - Show recent memories")
            print("  profile          - Show user profile")
            print("  clear            - Clear screen")
            print("  exit/quit        - Exit")
            continue

        if user_input.lower() == "clear":
            print("\033[2J\033[H", end="")
            continue

        print("Agent: ", end="", flush=True)
        response = harness.think(
            prompt=user_input,
            user_id=user_id,
            store_interaction=True,
        )
        print(response)
        print()


if __name__ == "__main__":
    main()
