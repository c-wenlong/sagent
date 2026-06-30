"""
context.py - ContextBuilder assembles memory entries into prompt context
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import pendo
from .memory import (
    MemoryEntry,
    MemoryStore,
    MemoryType,
    _clean_content,
    _resolve_memory_type,
    _resolve_user_id,
)


@dataclass
class TimeRange:
    last_n_days: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    def contains(self, dt: datetime) -> bool:
        if self.last_n_days:
            cutoff = datetime.utcnow() - timedelta(days=self.last_n_days)
            return dt >= cutoff
        if self.start_date and self.end_date:
            return self.start_date <= dt <= self.end_date
        if self.start_date:
            return dt >= self.start_date
        if self.end_date:
            return dt <= self.end_date
        return True


class ContextBuilder:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def build(
        self,
        prompt: str,
        user_id: str | None = None,
        max_tokens: int = 4000,
        include_types: list[MemoryType] | None = None,
        time_range: TimeRange | None = None,
    ) -> str:
        filters: list[dict[str, Any]] = []
        if user_id:
            filters.append({"field": "user_id", "operator": "==", "value": user_id})
        if include_types:
            filters.append({"field": "type", "operator": "in", "value": [t.value for t in include_types]})

        all_memories = self.memory_store.client.get_memories(
            kind="memories",
            page=1,
            page_size=100,
        )

        entries = []
        for m in all_memories:
            content = m.get("content", "")
            metadata = m.get("metadata") or {}
            entry_user = _resolve_user_id(metadata, content)
            if user_id and entry_user and entry_user != user_id:
                continue
            created_str = metadata.get("created_at", datetime.utcnow().isoformat())
            try:
                created_dt = datetime.fromisoformat(str(created_str).replace("Z", "+00:00"))
            except (ValueError, AttributeError, TypeError):
                created_dt = datetime.utcnow()
            if time_range is None or time_range.contains(created_dt):
                entry = MemoryEntry(
                    id=metadata.get("memory_id", m.get("source_id", "")),
                    type=_resolve_memory_type(metadata, content),
                    content=_clean_content(content),
                    metadata=metadata,
                    created_at=created_dt,
                    source_id=m.get("source_id"),
                    user_id=entry_user,
                )
                if include_types and entry.type not in include_types:
                    continue
                entries.append(entry)

        grouped = self._group_by_type(entries)
        sections = []

        if grouped.get(MemoryType.EVENT):
            sections.append(self._format_section("Recent Events", grouped[MemoryType.EVENT]))
        if grouped.get(MemoryType.INTERACTION):
            sections.append(self._format_section("Recent Interactions", grouped[MemoryType.INTERACTION]))
        if grouped.get(MemoryType.FACT):
            sections.append(self._format_section("Facts & Knowledge", grouped[MemoryType.FACT]))
        if grouped.get(MemoryType.PREFERENCE):
            sections.append(self._format_section("Preferences", grouped[MemoryType.PREFERENCE]))
        if grouped.get(MemoryType.THOUGHT):
            sections.append(self._format_section("Thoughts & Ideas", grouped[MemoryType.THOUGHT]))

        context_parts = []
        if sections:
            context_parts.append("## Memory Context\n")
            context_parts.extend(sections)
            context_parts.append("\n")
        context_parts.append("## Current Query\n")
        context_parts.append(f"{prompt}\n")

        result = "".join(context_parts)

        pendo.track(
            "context_built",
            visitor_id=user_id or "system",
            account_id=self.memory_store.client.tenant_id,
            properties={
                "prompt_length": len(prompt),
                "total_memories_fetched": len(all_memories),
                "memories_after_filter": len(entries),
                "has_time_range": time_range is not None,
                "context_length": len(result),
                "section_count": len(sections),
            },
        )

        return result

    def _group_by_type(self, entries: list[MemoryEntry]) -> dict[MemoryType, list[MemoryEntry]]:
        grouped: dict[MemoryType, list[MemoryEntry]] = {}
        for entry in entries:
            if entry.type not in grouped:
                grouped[entry.type] = []
            grouped[entry.type].append(entry)
        return grouped

    def _format_section(self, title: str, entries: list[MemoryEntry], limit: int = 10) -> str:
        lines = [f"\n### {title}\n"]
        for entry in entries[:limit]:
            date_str = entry.created_at.strftime("%Y-%m-%d")
            lines.append(f"- [{date_str}] {entry.type.value.upper()}: {entry.content}\n")
        return "".join(lines)

    def build_profile_summary(self, user_id: str) -> str:
        entries = self.memory_store.get_recent(user_id, limit=50)
        if not entries:
            return "No memory profile yet."

        grouped = self._group_by_type(entries)
        lines = ["## User Memory Profile\n"]

        for mtype, items in grouped.items():
            if items:
                lines.append(f"\n### {mtype.value.title()}s\n")
                seen = set()
                for item in items[:5]:
                    if item.content not in seen:
                        seen.add(item.content)
                        lines.append(f"- {item.content}\n")

        return "".join(lines)
