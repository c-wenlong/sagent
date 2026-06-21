"""
client.py - HydraDB client wrapper using the official hydra-db-python SDK
"""

from typing import Any, Dict, List, Optional

from hydra_db import HydraDB


class HydraDBClient:
    def __init__(self, api_key: str, tenant_id: str, sub_tenant_id: Optional[str] = None):
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.sub_tenant_id = sub_tenant_id or "default"
        self._client: Optional[HydraDB] = None

    def _get_client(self) -> HydraDB:
        if self._client is None:
            self._client = HydraDB(token=self.api_key)
        return self._client

    def add_memory(
        self,
        text: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
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
        user_id: Optional[str] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
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
        return [
            {
                "source_id": chunk.source_id,
                "content": chunk.content,
                "metadata": getattr(chunk, 'metadata', None) or {},
            }
            for chunk in results.chunks
        ]

    def get_memories(
        self,
        kind: str = "memories",
        page: int = 1,
        page_size: int = 50,
    ) -> List[Dict[str, Any]]:
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
