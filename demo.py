#!/usr/bin/env python3
"""
demo.py - Cross-session memory demonstration

Run: python demo.py
"""

import os
from dotenv import load_dotenv

from harness import AgentHarness, MemoryType

load_dotenv()


def demo():
    hydra_key = os.getenv("HYDRA_DB_API_KEY", "your-api-key")
    tenant_id = os.getenv("HYDRA_DB_TENANT_ID", "your-tenant-id")
    sub_tenant_id = os.getenv("HYDRA_DB_SUB_TENANT_ID", "default")
    llm_key = os.getenv("NEBIUS_API_KEY", "your-nebius-key")

    harness = AgentHarness(
        api_key=hydra_key,
        tenant_id=tenant_id,
        llm_api_key=llm_key,
    )

    user_id = "demo_user_001"

    print("=" * 60)
    print("SESSION 1: Storing memories")
    print("=" * 60)

    session1 = harness.start_session(user_id)
    print(f"Started session: {session1.id}\n")

    harness.remember(
        content="I'm learning Rust and building a database project called OctoDB",
        user_id=user_id,
        memory_type=MemoryType.FACT,
        session_id=session1.id,
    )
    print("Stored: Learning Rust, building OctoDB")

    harness.remember(
        content="I prefer working in the morning, 8am-12pm is my peak productivity window",
        user_id=user_id,
        memory_type=MemoryType.PREFERENCE,
        session_id=session1.id,
    )
    print("Stored: Morning peak productivity")

    harness.remember(
        content="Had a great call with Sarah about the OctoDB architecture. She suggested using columnar storage.",
        user_id=user_id,
        memory_type=MemoryType.INTERACTION,
        session_id=session1.id,
    )
    print("Stored: Call with Sarah about OctoDB")

    harness.end_session(session1.id)
    print(f"\nEnded session: {session1.id}")

    print("\n" + "=" * 60)
    print("SESSION 2: Recalling memories")
    print("=" * 60)

    session2 = harness.start_session(user_id)
    print(f"Started session: {session2.id}\n")

    recent = harness.get_recent_memories(user_id, limit=10)
    print(f"Found {len(recent)} memories from previous sessions\n")

    for m in recent:
        print(f"  [{m.type.value}] {m.content}")

    print("\n" + "-" * 40)
    print("Asking: What am I working on?")
    print("-" * 40)

    response = harness.think(
        prompt="What am I currently working on and what are my preferences?",
        user_id=user_id,
        session_id=session2.id,
        store_interaction=False,
    )
    print(f"\nAgent: {response}")

    harness.end_session(session2.id)

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"\nUser profile summary:")
    profile = harness.profile(user_id)
    print(f"  Facts: {len(profile.facts)}")
    print(f"  Preferences: {len(profile.preferences)}")
    print(f"  Interactions: {len(profile.interactions)}")


if __name__ == "__main__":
    demo()
