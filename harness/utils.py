"""
utils.py - Helper utilities for the agent harness
"""

import os
import tiktoken
from typing import List, Optional


def count_tokens(text: str, model: str = "gpt-4") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def truncate_to_token_limit(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoding.decode(tokens[:max_tokens])


def load_env(var_name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(var_name, default)


def format_memory_entry(entry, verbose: bool = False) -> str:
    date_str = entry.created_at.strftime("%Y-%m-%d %H:%M")
    base = f"[{date_str}] {entry.type.value.upper()}: {entry.content}"
    if verbose and entry.metadata:
        meta_str = ", ".join(f"{k}={v}" for k, v in entry.metadata.items())
        return f"{base} ({meta_str})"
    return base


def format_memories(entries: List, max_per_type: int = 5) -> str:
    if not entries:
        return "No memories found."

    from collections import defaultdict
    by_type = defaultdict(list)
    for e in entries:
        by_type[e.type].append(e)

    lines = []
    for mtype, items in by_type.items():
        lines.append(f"\n## {mtype.value.title()}s")
        for item in items[:max_per_type]:
            lines.append(f"  - {format_memory_entry(item)}")
    return "\n".join(lines)
