"""
memory.py - MemoryEntry dataclass and MemoryStore for HydraDB operations
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .client import HydraDBClient


class MemoryType(str, Enum):
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
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    source_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        created = data.get("created_at")
        updated = data.get("updated_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)
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


class MemoryStore:
    def __init__(self, client: HydraDBClient):
        self.client = client

    def add(self, entry: MemoryEntry) -> str:
        metadata = {
            "memory_id": entry.id,
            "memory_type": entry.type.value,
            "session_id": entry.session_id,
            "user_id": entry.user_id,
            **entry.metadata,
        }
        source_id = self.client.add_memory(
            text=entry.content,
            user_id=entry.user_id,
            metadata=metadata,
            infer=True,
        )
        entry.source_id = source_id
        return entry.id

    def recall(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[MemoryEntry]:
        results = self.client.recall(
            query=query,
            user_id=user_id,
            max_results=limit,
        )
        entries = []
        for r in results:
            metadata = r.get("metadata", {})
            entry = MemoryEntry(
                id=metadata.get("memory_id", r.get("source_id", "")),
                type=MemoryType(metadata.get("memory_type", "fact")),
                content=r.get("content", ""),
                metadata=metadata,
                source_id=r.get("source_id"),
            )
            entries.append(entry)
        return entries

    def get_recent(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        all_memories = self.client.get_memories(kind="memories", page_size=limit)
        entries = []
        for m in all_memories:
            metadata = m.get("metadata", {})
            if user_id and metadata.get("user_id") != user_id:
                continue
            entry = MemoryEntry(
                id=metadata.get("memory_id", m.get("source_id", "")),
                type=MemoryType(metadata.get("memory_type", "fact")),
                content=m.get("content", ""),
                metadata=metadata,
                source_id=m.get("source_id"),
            )
            entries.append(entry)
        return entries[:limit]

    def get_by_type(
        self,
        memory_type: MemoryType,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        all_memories = self.client.get_memories(kind="memories", page_size=limit)
        entries = []
        for m in all_memories:
            metadata = m.get("metadata", {})
            if metadata.get("memory_type") != memory_type.value:
                continue
            if user_id and metadata.get("user_id") != user_id:
                continue
            entry = MemoryEntry(
                id=metadata.get("memory_id", m.get("source_id", "")),
                type=MemoryType(metadata.get("memory_type", "fact")),
                content=m.get("content", ""),
                metadata=metadata,
                source_id=m.get("source_id"),
            )
            entries.append(entry)
        return entries[:limit]

    def update(self, id: str, content: str) -> bool:
        return False

    def delete(self, id: str) -> bool:
        return False

    def get(self, id: str) -> Optional[MemoryEntry]:
        return None
