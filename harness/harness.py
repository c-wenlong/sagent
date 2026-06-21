"""
harness.py - AgentHarness main class wrapping memory + context + session + LLM
"""

import os
from typing import Any, TypeVar

from openai import OpenAI

from .client import HydraDBClient
from .context import ContextBuilder, TimeRange
from .memory import MemoryEntry, MemoryStore, MemoryType
from .session import Session, SessionManager
from .utils import truncate_to_token_limit

DEFAULT_MODEL = "zai-org/GLM-5.2"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


T = TypeVar("T")


class UserProfile:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.preferences: list[str] = []
        self.facts: list[str] = []
        self.interactions: list[str] = []
        self.thoughts: list[str] = []
        self.events: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preferences": self.preferences,
            "facts": self.facts,
            "interactions": self.interactions,
            "thoughts": self.thoughts,
            "events": self.events,
        }


class AgentHarness:
    def __init__(
        self,
        api_key: str,
        tenant_id: str,
        sub_tenant_id: str = "default",
        llm_api_key: str | None = None,
        llm_model: str = DEFAULT_MODEL,
        max_context_tokens: int = 4000,
    ):
        self.db_client = HydraDBClient(api_key, tenant_id, sub_tenant_id)
        self.memory_store = MemoryStore(self.db_client)
        self.context_builder = ContextBuilder(self.memory_store)
        self.session_manager = SessionManager(self.memory_store)

        self.llm_api_key = llm_api_key or os.environ.get("NEBIUS_API_KEY")
        self.llm_model = llm_model
        self.max_context_tokens = max_context_tokens

        if self.llm_api_key:
            self.llm = OpenAI(
                base_url=DEFAULT_BASE_URL,
                api_key=self.llm_api_key,
            )
        else:
            self.llm = None

    def think(
        self,
        prompt: str,
        user_id: str,
        session_id: str | None = None,
        store_interaction: bool = False,
        include_types: list[MemoryType] | None = None,
        time_range: TimeRange | None = None,
    ) -> str:
        context = self.context_builder.build(
            prompt=prompt,
            user_id=user_id,
            max_tokens=self.max_context_tokens,
            include_types=include_types,
            time_range=time_range,
        )

        full_prompt = self._build_prompt(context, prompt)
        response = self._call_llm(full_prompt)

        if store_interaction:
            self.remember(
                content=f"User asked: {prompt}. Agent responded: {response[:200]}",
                user_id=user_id,
                memory_type=MemoryType.INTERACTION,
                session_id=session_id,
            )

        return response

    def remember(
        self,
        content: str,
        user_id: str,
        memory_type: MemoryType = MemoryType.FACT,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        entry = MemoryEntry(
            type=memory_type,
            content=content,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
            embedding=embedding,
        )
        entry_id = self.memory_store.add(entry)

        if session_id:
            self.session_manager.add_memory_to_session(session_id, entry_id)

        return entry_id

    def recall(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        return self.memory_store.recall(query=query, user_id=user_id, limit=limit)

    def profile(self, user_id: str) -> UserProfile:
        all_entries = self.memory_store.get_recent(user_id, limit=100)
        profile = UserProfile(user_id)

        for entry in all_entries:
            if entry.type == MemoryType.PREFERENCE:
                profile.preferences.append(entry.content)
            elif entry.type == MemoryType.FACT:
                profile.facts.append(entry.content)
            elif entry.type == MemoryType.INTERACTION:
                profile.interactions.append(entry.content)
            elif entry.type == MemoryType.THOUGHT:
                profile.thoughts.append(entry.content)
            elif entry.type == MemoryType.EVENT:
                profile.events.append(entry.content)

        return profile

    def start_session(self, user_id: str) -> Session:
        return self.session_manager.start_session(user_id)

    def end_session(self, session_id: str) -> Session | None:
        return self.session_manager.end_session(session_id)

    def get_recent_memories(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        return self.memory_store.get_recent(user_id=user_id, limit=limit)

    def _build_prompt(self, context: str, prompt: str) -> str:
        system = (
            "You are a helpful AI assistant with long-term memory. "
            "You receive context from past interactions below. "
            "Use this context to provide personalized, informed responses. "
            "If the context is empty or irrelevant, respond based on general knowledge."
        )
        return f"{system}\n\n{context}\n\n## User\n{prompt}"

    def _call_llm(self, prompt: str) -> str:
        if not self.llm:
            return "[LLM not configured - set NEBIUS_API_KEY or pass llm_api_key]"

        truncated = truncate_to_token_limit(prompt, self.max_context_tokens - 200)
        response = self.llm.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": truncated}],
            max_tokens=1000,
            temperature=0.7,
        )
        return response.choices[0].message.content
