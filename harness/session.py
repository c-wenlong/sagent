"""
session.py - SessionManager tracks session state and manages session-bound memory
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from . import pendo
from .memory import MemoryEntry, MemoryStore


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    entry_ids: list[str] = field(default_factory=list)
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "entry_ids": self.entry_ids,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        started = data.get("started_at")
        ended = data.get("ended_at")
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if isinstance(ended, str) and ended:
            ended = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            user_id=data.get("user_id", ""),
            started_at=started or datetime.utcnow(),
            ended_at=ended,
            entry_ids=data.get("entry_ids", []),
            active=data.get("active", True),
        )


class SessionManager:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self._sessions: dict[str, Session] = {}

    def start_session(self, user_id: str) -> Session:
        session = Session(user_id=user_id)
        self._sessions[session.id] = session

        pendo.track(
            "session_started",
            visitor_id=user_id,
            account_id=self.memory_store.client.tenant_id,
            properties={
                "session_id": session.id,
            },
        )

        return session

    def end_session(self, session_id: str) -> Session | None:
        if session_id not in self._sessions:
            return None
        session = self._sessions[session_id]
        session.ended_at = datetime.utcnow()
        session.active = False

        duration = (session.ended_at - session.started_at).total_seconds()
        pendo.track(
            "session_ended",
            visitor_id=session.user_id,
            account_id=self.memory_store.client.tenant_id,
            properties={
                "session_id": session_id,
                "duration_seconds": round(duration, 1),
                "memory_count": len(session.entry_ids),
            },
        )

        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def add_memory_to_session(self, session_id: str, entry_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].entry_ids.append(entry_id)

    def get_session_context(self, session_id: str) -> list[MemoryEntry]:
        session = self.get_session(session_id)
        if not session:
            return []
        entries = []
        for entry_id in session.entry_ids:
            entries.append(MemoryEntry(id=entry_id))
        return entries

    def merge_to_long_term(self, session_id: str) -> list[str]:
        session = self.get_session(session_id)
        if not session:
            return []
        return list(session.entry_ids)

    def get_user_sessions(self, user_id: str, limit: int = 10) -> list[Session]:
        user_sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        return sorted(user_sessions, key=lambda s: s.started_at, reverse=True)[:limit]
