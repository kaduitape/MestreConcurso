"""Banco vetorial: isolamento por tenant e busca por similaridade."""

from __future__ import annotations

import pytest

from app.ai.vector_store import QdrantVectorStore, VectorPoint, new_vector_id


@pytest.fixture
async def store() -> QdrantVectorStore:
    # Modo local do Qdrant: mesmo cliente, sem servidor externo.
    instance = QdrantVectorStore(url=":memory:")
    await instance.ensure_collection("notices", dimensions=4)
    return instance


async def test_upsert_and_search(store: QdrantVectorStore) -> None:
    await store.upsert(
        "notices",
        [
            VectorPoint(
                id=new_vector_id(),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"tenant": "global", "document_id": 1, "page": 3},
            ),
            VectorPoint(
                id=new_vector_id(),
                vector=[0.0, 1.0, 0.0, 0.0],
                payload={"tenant": "global", "document_id": 1, "page": 9},
            ),
        ],
    )

    hits = await store.search("notices", [1.0, 0.05, 0.0, 0.0], tenant="global", limit=1)
    assert len(hits) == 1
    assert hits[0].payload["page"] == 3


async def test_tenant_isolation(store: QdrantVectorStore) -> None:
    await store.upsert(
        "notices",
        [
            VectorPoint(
                id=new_vector_id(),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"tenant": "user:1", "document_id": 10},
            ),
            VectorPoint(
                id=new_vector_id(),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"tenant": "user:2", "document_id": 20},
            ),
        ],
    )

    hits = await store.search("notices", [1.0, 0.0, 0.0, 0.0], tenant="user:1", limit=10)
    documents = {hit.payload["document_id"] for hit in hits}
    # O material do outro aluno não aparece em hipótese alguma.
    assert documents == {10}


async def test_global_content_is_visible_to_every_tenant(store: QdrantVectorStore) -> None:
    await store.upsert(
        "notices",
        [
            VectorPoint(
                id=new_vector_id(),
                vector=[0.0, 0.0, 1.0, 0.0],
                payload={"tenant": "global", "document_id": 99},
            )
        ],
    )
    hits = await store.search("notices", [0.0, 0.0, 1.0, 0.0], tenant="user:7", limit=5)
    assert [hit.payload["document_id"] for hit in hits] == [99]


async def test_extra_filter_narrows_results(store: QdrantVectorStore) -> None:
    await store.upsert(
        "notices",
        [
            VectorPoint(
                id=new_vector_id(),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"tenant": "global", "document_id": 1},
            ),
            VectorPoint(
                id=new_vector_id(),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"tenant": "global", "document_id": 2},
            ),
        ],
    )
    hits = await store.search(
        "notices", [1.0, 0.0, 0.0, 0.0], tenant="global", extra_filter={"document_id": 2}
    )
    assert [hit.payload["document_id"] for hit in hits] == [2]


async def test_upsert_empty_is_noop(store: QdrantVectorStore) -> None:
    assert await store.upsert("notices", []) == 0
