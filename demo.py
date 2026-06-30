#!/usr/bin/env python3
"""
demo.py - Cross-session memory demonstration for sagent.

Shows that agent memory persists across sessions via HydraDB while
in-memory session state is discarded on restart.

Run: python3 demo.py
"""

import os
import sys
import textwrap
import time

from dotenv import load_dotenv

from harness import AgentHarness, MemoryType, pendo

load_dotenv()

WIDTH = 64

TYPE_ICONS = {
    MemoryType.FACT: "FACT",
    MemoryType.PREFERENCE: "PREF",
    MemoryType.INTERACTION: "INTER",
    MemoryType.THOUGHT: "THOUGHT",
    MemoryType.EVENT: "EVENT",
}

SESSION_1_MEMORIES = [
    (
        MemoryType.FACT,
        "Building sagent — a Python harness that gives AI agents long-term memory using HydraDB",
    ),
    (
        MemoryType.PREFERENCE,
        "Prefer concise, technical answers with code examples when relevant",
    ),
    (
        MemoryType.INTERACTION,
        "The HydraDB team recommended using infer=True so memories link into a knowledge graph",
    ),
    (
        MemoryType.THOUGHT,
        "The killer feature is cross-session recall — not the TUI or spinner animations",
    ),
    (
        MemoryType.EVENT,
        "Demo day is today — need to prove memory survives process restarts",
    ),
]

FINAL_PROMPT = (
    "What am I building, what are my preferences, and what should I focus on for demo day?"
)

INDEX_POLL_SECONDS = 2
INDEX_TIMEOUT_SECONDS = 30


def banner(title: str) -> None:
    print("\n" + "=" * WIDTH)
    print(title)
    print("=" * WIDTH)


def section(title: str) -> None:
    print("\n" + "-" * WIDTH)
    print(title)
    print("-" * WIDTH)


def narrate(text: str) -> None:
    print(f"\n  >> {textwrap.fill(text, WIDTH - 6, subsequent_indent='     ')}")


def print_memory(memory_type: MemoryType, content: str) -> None:
    label = TYPE_ICONS[memory_type]
    print(f"  [{label}] {content}")


def print_profile(user_id: str, profile) -> None:
    print(f"\n  Profile: {user_id}")
    print(f"    Facts:        {len(profile.facts)}")
    print(f"    Preferences:  {len(profile.preferences)}")
    print(f"    Interactions: {len(profile.interactions)}")
    print(f"    Thoughts:     {len(profile.thoughts)}")
    print(f"    Events:       {len(profile.events)}")


def require_env() -> tuple[str, str, str, str, str]:
    hydra_key = os.getenv("HYDRA_DB_API_KEY")
    tenant_id = os.getenv("HYDRA_DB_TENANT_ID")
    llm_key = os.getenv("NEBIUS_API_KEY")
    sub_tenant_id = os.getenv("HYDRA_DB_SUB_TENANT_ID", "demo-run")
    user_id = os.getenv("SAGENT_DEMO_USER", "demo_presenter")

    missing = [
        name
        for name, val in [
            ("HYDRA_DB_API_KEY", hydra_key),
            ("HYDRA_DB_TENANT_ID", tenant_id),
            ("NEBIUS_API_KEY", llm_key),
        ]
        if not val or val.startswith("your-")
    ]
    if missing:
        print("Error: missing or placeholder environment variables:")
        for name in missing:
            print(f"  - {name}")
        print("\nCopy .env.example to .env and add your API keys.")
        sys.exit(1)

    return hydra_key, tenant_id, llm_key, sub_tenant_id, user_id


def wait_for_memories(harness, user_id: str, expected: int) -> list:
    """Poll HydraDB until stored memories are visible in list API."""
    narrate("Waiting for HydraDB to index memories…")
    deadline = time.time() + INDEX_TIMEOUT_SECONDS
    while time.time() < deadline:
        recent = harness.get_recent_memories(user_id, limit=expected + 5)
        if len(recent) >= expected:
            return recent
        time.sleep(INDEX_POLL_SECONDS)
    return harness.get_recent_memories(user_id, limit=expected + 5)


def demo() -> None:
    hydra_key, tenant_id, llm_key, sub_tenant_id, user_id = require_env()

    banner("sagent — Cross-Session Memory Demo")
    print(f"  User:       {user_id}")
    print(f"  Sub-tenant: {sub_tenant_id}  (isolated memory — clean slate each run)")
    narrate(
        "Each demo run writes to a dedicated HydraDB sub-tenant so judges see "
        "fresh memory, not leftovers from development."
    )

    harness = AgentHarness(
        api_key=hydra_key,
        tenant_id=tenant_id,
        sub_tenant_id=sub_tenant_id,
        llm_api_key=llm_key,
    )

    # --- Act 1: Session 1 — teach the agent --------------------------------
    banner("ACT 1 — Session 1: First meeting")
    session1 = harness.start_session(user_id)
    print(f"\n  Session started: {session1.id}")

    section("Storing memories")
    for memory_type, content in SESSION_1_MEMORIES:
        harness.remember(
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            session_id=session1.id,
        )
        print_memory(memory_type, content)

    harness.end_session(session1.id)
    print(f"\n  Session ended:   {session1.id}")
    narrate(
        "Session 1 complete. If this were a normal chatbot, everything above "
        "would vanish when we close the process."
    )

    expected_count = len(SESSION_1_MEMORIES)
    wait_for_memories(harness, user_id, expected_count)

    # --- Act 2: Session 2 — prove memory survived --------------------------
    banner("ACT 2 — Session 2: New process, same agent")
    session2 = harness.start_session(user_id)
    print(f"\n  Session started: {session2.id}  (different ID — in-memory state is fresh)")

    recent = harness.get_recent_memories(user_id, limit=10)
    section(f"Recalled {len(recent)} memories from HydraDB")
    for entry in recent:
        print_memory(entry.type, entry.content)

    profile = harness.profile(user_id)
    print_profile(user_id, profile)

    section(f"Asking: {FINAL_PROMPT}")
    narrate(
        "The LLM has no conversation history from Session 1. "
        "ContextBuilder retrieved the memories above and injected them into the prompt."
    )

    response = harness.think(
        prompt=FINAL_PROMPT,
        user_id=user_id,
        session_id=session2.id,
        store_interaction=False,
    )
    print(f"\n  Agent:\n{textwrap.fill(response, WIDTH - 4, initial_indent='    ', subsequent_indent='    ')}")

    harness.end_session(session2.id)
    print(f"\n  Session ended:   {session2.id}")

    # --- Closing summary ---------------------------------------------------
    banner("DEMO COMPLETE")
    print(f"  Memories stored:  {len(SESSION_1_MEMORIES)}")
    print(f"  Sessions:         2  ({session1.id[:8]}… → {session2.id[:8]}…)")
    print("  Memory backend:   HydraDB  (persistent across restarts)")
    print("  Session tracking: in-memory only  (discarded each run — by design)")
    narrate(
        "sagent separates durable memory (HydraDB) from ephemeral session state. "
        "Multiple agents can share the same memory store."
    )

    pendo.track(
        "demo_completed",
        visitor_id=user_id,
        account_id=tenant_id,
        properties={
            "sub_tenant_id": sub_tenant_id,
            "memories_stored": len(SESSION_1_MEMORIES),
            "memories_recalled": len(recent),
            "sessions_count": 2,
            "llm_response_length": len(response),
        },
    )


if __name__ == "__main__":
    demo()
