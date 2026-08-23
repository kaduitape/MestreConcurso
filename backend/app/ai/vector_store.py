"""Banco vetorial (Qdrant) — isolamento por tenant embutido na própria porta.

O filtro de tenant é montado aqui, nunca pelo chamador: é impossível esquecer e
vazar material de um aluno para outro.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GLOBAL_TENANT = "global"


@dataclass(frozen=True, slots=True)
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchHit:
    id: str
    score: float
    payload: dict[str, Any]


def new_vector_id() -> str:
    return str(uuid.uuid4())


class VectorStore(Protocol):
    """Porta do banco vetorial."""

    async def ensure_collection(self, name: str, dimensions: int) -> None: ...

    async def upsert(self, collection: str, points: list[VectorPoint]) -> int: ...

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        tenant: str,
        limit: int = 8,
        extra_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    async def delete_by_owner(self, collection: str, owner_key: str, owner_id: int) -> int: ...


class QdrantVectorStore:
    """Adaptador Qdrant. Aceita servidor remoto ou modo local (usado em teste)."""

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        from qdrant_client import AsyncQdrantClient

        location = url or settings.qdrant_url
        if location in {":memory:", "memory"}:
            self.client = AsyncQdrantClient(location=":memory:")
        else:
            self.client = AsyncQdrantClient(url=location, api_key=api_key or None)

    async def ensure_collection(self, name: str, dimensions: int) -> None:
        from qdrant_client import models

        if await self.client.collection_exists(name):
            return
        await self.client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
        )
        for field_name in ("tenant", "owner_type", "owner_id", "document_id"):
            await self.client.create_payload_index(
                collection_name=name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD
                if field_name in {"tenant", "owner_type"}
                else models.PayloadSchemaType.INTEGER,
            )
        logger.info("vector_store.collection_created", name=name, dimensions=dimensions)

    async def upsert(self, collection: str, points: list[VectorPoint]) -> int:
        from qdrant_client import models

        if not points:
            return 0
        await self.client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(id=point.id, vector=point.vector, payload=point.payload)
                for point in points
            ],
        )
        return len(points)

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        tenant: str,
        limit: int = 8,
        extra_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        from qdrant_client import models

        conditions: list[models.FieldCondition] = [
            models.FieldCondition(key="tenant", match=models.MatchAny(any=[tenant, GLOBAL_TENANT]))
        ]
        for key, value in (extra_filter or {}).items():
            conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))

        response = await self.client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=models.Filter(must=conditions),
            limit=limit,
            with_payload=True,
        )
        return [
            SearchHit(id=str(point.id), score=float(point.score), payload=point.payload or {})
            for point in response.points
        ]

    async def delete_by_owner(self, collection: str, owner_key: str, owner_id: int) -> int:
        from qdrant_client import models

        if not await self.client.collection_exists(collection):
            return 0
        await self.client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key=owner_key, match=models.MatchValue(value=owner_id)
                        )
                    ]
                )
            ),
        )
        return 1

    async def close(self) -> None:
        await self.client.close()


COLLECTION_NOTICES = "notices"
