from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from models.paper import Paper
from routers import papers as papers_router


async def _seed_analytics_papers(test_db) -> list[Paper]:
    """
    Seed a small deterministic corpus for analytics tests.
    """
    papers = [
        Paper(
            arxiv_id=f"rank-{uuid4().hex[:8]}",
            title="Transformer Foundations",
            abstract="A paper about transformer architectures and attention mechanisms.",
            published_date=date(2020, 1, 15),
            updated_date=datetime(2020, 1, 16, 12, 0, 0, tzinfo=UTC),
            primary_category="cs.AI",
            all_categories=["cs.AI", "cs.LG"],
            pdf_url="https://arxiv.org/pdf/0001.00001.pdf",
            pagerank_score=0.900000,
            abstract_embedding=[0.10] * 384,
        ),
        Paper(
            arxiv_id=f"rank-{uuid4().hex[:8]}",
            title="Advanced Transformer Variants",
            abstract="A paper about improved transformer models and semantic search.",
            published_date=date(2021, 6, 10),
            updated_date=datetime(2021, 6, 11, 12, 0, 0, tzinfo=UTC),
            primary_category="cs.AI",
            all_categories=["cs.AI"],
            pdf_url="https://arxiv.org/pdf/0001.00002.pdf",
            pagerank_score=0.700000,
            abstract_embedding=[0.11] * 384,
        ),
        Paper(
            arxiv_id=f"rank-{uuid4().hex[:8]}",
            title="Graph Learning for Ranking",
            abstract="A machine learning paper focused on graphs and ranking signals.",
            published_date=date(2022, 3, 20),
            updated_date=datetime(2022, 3, 21, 12, 0, 0, tzinfo=UTC),
            primary_category="cs.LG",
            all_categories=["cs.LG"],
            pdf_url="https://arxiv.org/pdf/0001.00003.pdf",
            pagerank_score=0.500000,
            abstract_embedding=[0.30] * 384,
        ),
        Paper(
            arxiv_id=f"rank-{uuid4().hex[:8]}",
            title="Vision Transformers in Practice",
            abstract="A vision-focused paper connected to transformer representations.",
            published_date=date(2023, 9, 5),
            updated_date=datetime(2023, 9, 6, 12, 0, 0, tzinfo=UTC),
            primary_category="cs.CV",
            all_categories=["cs.CV", "cs.AI"],
            pdf_url="https://arxiv.org/pdf/0001.00004.pdf",
            pagerank_score=0.300000,
            abstract_embedding=[0.12] * 384,
        ),
    ]

    test_db.add_all(papers)
    await test_db.commit()

    for paper in papers:
        await test_db.refresh(paper)

    return papers


@pytest.mark.asyncio
async def test_get_papers_ranked_sorted_desc(async_client, test_db):
    papers = await _seed_analytics_papers(test_db)

    response = await async_client.get("/papers/ranked", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()

    assert "items" in body
    assert isinstance(body["items"], list)
    assert body["total"] >= len(papers)

    items = body["items"]
    assert len(items) >= 4

    scores = [item["pagerank_score"] for item in items]
    assert scores == sorted(scores, reverse=True)

    ranks = [item["rank"] for item in items]
    assert ranks == list(range(1, len(items) + 1))


@pytest.mark.asyncio
async def test_get_analytics_topics_returns_seeded_categories(async_client, test_db):
    await _seed_analytics_papers(test_db)

    response = await async_client.get("/analytics/topics", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()

    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)

    categories = {item["category"] for item in body["items"]}
    assert "cs.AI" in categories
    assert "cs.LG" in categories
    assert "cs.CV" in categories


@pytest.mark.asyncio
async def test_get_analytics_trend_chronological_order(async_client, test_db):
    await _seed_analytics_papers(test_db)

    response = await async_client.get(
        "/analytics/trend",
        params={"granularity": "year"},
    )

    assert response.status_code == 200
    body = response.json()

    assert "items" in body
    assert "total_points" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 4

    periods = [item["period"] for item in body["items"]]
    assert periods == sorted(periods)


@pytest.mark.asyncio
async def test_semantic_search_returns_list(async_client, test_db, monkeypatch):
    await _seed_analytics_papers(test_db)

    # Make semantic search deterministic and independent of the actual model.
    monkeypatch.setattr(
        papers_router,
        "generate_embedding",
        lambda _q: [0.10] * 384,
    )

    response = await async_client.get(
        "/papers/search/semantic",
        params={"q": "transformer", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()

    assert "items" in body
    assert "total" in body
    assert "query" in body
    assert isinstance(body["items"], list)
    assert body["query"] == "transformer"
    assert len(body["items"]) >= 1

    first = body["items"][0]
    assert "similarity_score" in first
    assert "title" in first
    assert "_links" in first


@pytest.mark.asyncio
async def test_get_similar_papers_excludes_self(async_client, test_db):
    papers = await _seed_analytics_papers(test_db)
    source_paper = papers[0]

    response = await async_client.get(
        f"/papers/{source_paper.id}/similar",
        params={"limit": 10},
    )

    assert response.status_code == 200
    body = response.json()

    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 1

    returned_ids = [item["id"] for item in body["items"]]
    assert str(source_paper.id) not in returned_ids

    for item in body["items"]:
        assert "similarity_score" in item
        assert "_links" in item