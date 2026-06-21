"""
client.py - HydraDB client wrapper using the official hydra-db-python SDK
"""

from typing import Any

from hydra_db import HydraDB


class HydraDBClient:
    def __init__(self, api_key: str, tenant_id: str, sub_tenant_id: str | None = None):
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.sub_tenant_id = sub_tenant_id or "default"
        self._client: HydraDB | None = None

    def _get_client(self) -> HydraDB:
        if self._client is None:
            self._client = HydraDB(token=self.api_key)
        return self._client

    def add_memory(
        self,
        text: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        infer: bool = True,
    ) -> str:
        client = self._get_client()
        memories = [{"text": text, "infer": infer}]
        if user_id:
            memories[0]["user_name"] = user_id
        if metadata:
            memories[0]["metadata"] = metadata

        result = client.upload.add_memory(
            tenant_id=self.tenant_id,
            sub_tenant_id=self.sub_tenant_id,
            upsert=True,
            memories=memories,
        )
        if result.results:
            return result.results[0].source_id
        return ""

    def recall(
        self,
        query: str,
        user_id: str | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        client = self._get_client()
        if user_id:
            results = client.recall.recall_preferences(
                tenant_id=self.tenant_id,
                sub_tenant_id=self.sub_tenant_id,
                query=query,
                max_results=max_results,
            )
        else:
            results = client.recall.full_recall(
                tenant_id=self.tenant_id,
                sub_tenant_id=self.sub_tenant_id,
                query=query,
                max_results=max_results,
            )
        entries = []
        for chunk in results.chunks or []:
            metadata: dict[str, Any] = {}
            doc_meta = getattr(chunk, "document_metadata", None) or {}
            tenant_meta = getattr(chunk, "tenant_metadata", None) or {}
            metadata.update({k: v for k, v in doc_meta.items() if v is not None})
            metadata.update({k: v for k, v in tenant_meta.items() if v is not None})
            entries.append(
                {
                    "source_id": chunk.source_id,
                    "content": chunk.chunk_content,
                    "metadata": metadata,
                }
            )
        return entries

    def get_memories(
        self,
        kind: str = "memories",
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        client = self._get_client()
        result = client.fetch.list_data(
            tenant_id=self.tenant_id,
            sub_tenant_id=self.sub_tenant_id,
            kind=kind,
            page=page,
            page_size=page_size,
        )
        return [
            {
                "source_id": item.memory_id,
                "content": item.memory_content,
            }
            for item in result.user_memories
        ]

    def delete_memory(self, memory_id: str) -> bool:
        client = self._get_client()
        try:
            client.data.delete(
                tenant_id=self.tenant_id,
                sub_tenant_id=self.sub_tenant_id,
                ids=[memory_id],
            )
            return True
        except Exception:
            return False
