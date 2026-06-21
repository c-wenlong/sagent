"""
memory.py - MemoryEntry dataclass and MemoryStore for HydraDB operations
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .client import HydraDBClient

# Embedded in stored text so list API can recover type/user (HydraDB list has no metadata).
_MEMORY_HEADER_RE = re.compile(
    r"^\[(?P<type>\w+)(?::(?P<user>[^\]]+))?\]\s+(?P<body>.+)$",
    re.DOTALL,
)


class MemoryType(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    INTERACTION = "interaction"
    THOUGHT = "thought"
    EVENT = "event"


@dataclass
class MemoryEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MemoryType = MemoryType.FACT
    content: str = ""
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    session_id: str | None = None
    user_id: str | None = None
    source_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        created = data.get("created_at")
        updated = data.get("updated_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MemoryType(data.get("type", "fact")),
            content=data.get("content", ""),
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            created_at=created or datetime.utcnow(),
            updated_at=updated or datetime.utcnow(),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            source_id=data.get("source_id"),
        )


def _encode_stored_content(content: str, memory_type: MemoryType, user_id: str | None) -> str:
    """Prefix content so list API can recover type and user without metadata."""
    user_part = f":{user_id}" if user_id else ""
    return f"[{memory_type.value}{user_part}] {content}"


def _decode_stored_content(content: str) -> tuple[MemoryType | None, str | None, str]:
    """Parse embedded header; returns (type, user_id, clean_content)."""
    match = _MEMORY_HEADER_RE.match(content)
    if not match:
        return None, None, content
    try:
        memory_type = MemoryType(match.group("type").lower())
    except ValueError:
        memory_type = None
    return memory_type, match.group("user"), match.group("body")


def _resolve_memory_type(metadata: dict[str, Any], content: str) -> MemoryType:
    raw = metadata.get("memory_type")
    if raw:
        try:
            return MemoryType(str(raw).lower())
        except ValueError:
            pass
    parsed_type, _, _ = _decode_stored_content(content)
    return parsed_type or MemoryType.FACT


def _resolve_user_id(metadata: dict[str, Any], content: str) -> str | None:
    if metadata.get("user_id"):
        return metadata["user_id"]
    _, parsed_user, _ = _decode_stored_content(content)
    return parsed_user


def _clean_content(content: str) -> str:
    _, _, body = _decode_stored_content(content)
    return body


class MemoryStore:
    def __init__(self, client: HydraDBClient):
        self.client = client

    def add(self, entry: MemoryEntry) -> str:
        metadata = {
            "memory_id": entry.id,
            "memory_type": entry.type.value,
            "session_id": entry.session_id,
            "user_id": entry.user_id,
            "created_at": entry.created_at.isoformat(),
            **entry.metadata,
        }
        stored_content = _encode_stored_content(entry.content, entry.type, entry.user_id)
        source_id = self.client.add_memory(
            text=stored_content,
            user_id=entry.user_id,
            metadata=metadata,
            infer=True,
        )
        entry.source_id = source_id
        return entry.id

    def _entry_from_raw(
        self,
        source_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        metadata = metadata or {}
        memory_type = _resolve_memory_type(metadata, content)
        user_id = _resolve_user_id(metadata, content)
        created_str = metadata.get("created_at")
        try:
            created_at = (
                datetime.fromisoformat(str(created_str).replace("Z", "+00:00"))
                if created_str
                else datetime.utcnow()
            )
        except (ValueError, TypeError):
            created_at = datetime.utcnow()
        return MemoryEntry(
            id=metadata.get("memory_id", source_id),
            type=memory_type,
            content=_clean_content(content),
            metadata=metadata,
            created_at=created_at,
            source_id=source_id,
            user_id=user_id,
        )

    def recall(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        results = self.client.recall(
            query=query,
            user_id=user_id,
            max_results=limit,
        )
        return [self._entry_from_raw(r["source_id"], r["content"], r.get("metadata")) for r in results]

    def get_recent(
        self,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        page_size = min(max(limit * 3, limit), 100)
        all_memories = self.client.get_memories(kind="memories", page_size=page_size)
        entries = []
        for m in all_memories:
            content = m.get("content", "")
            metadata = m.get("metadata") or {}
            entry_user = _resolve_user_id(metadata, content)
            if user_id and entry_user and entry_user != user_id:
                continue
            entries.append(
                self._entry_from_raw(m.get("source_id", ""), content, metadata)
            )
            if len(entries) >= limit:
                break
        return entries

    def get_by_type(
        self,
        memory_type: MemoryType,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        page_size = min(max(limit * 3, limit), 100)
        all_memories = self.client.get_memories(kind="memories", page_size=page_size)
        entries = []
        for m in all_memories:
            content = m.get("content", "")
            metadata = m.get("metadata") or {}
            if _resolve_memory_type(metadata, content) != memory_type:
                continue
            entry_user = _resolve_user_id(metadata, content)
            if user_id and entry_user and entry_user != user_id:
                continue
            entries.append(
                self._entry_from_raw(m.get("source_id", ""), content, metadata)
            )
            if len(entries) >= limit:
                break
        return entries

    def update(self, id: str, content: str) -> bool:
        return False

    def delete(self, id: str) -> bool:
        return False

    def get(self, id: str) -> MemoryEntry | None:
        return None
