import asyncio
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from models import Paper, User


TEST_USERS = [
    {
        "username": "alice",
        "email": "alice@example.com",
        "hashed_password": "dev_only_hash_alice",
        "is_active": True,
    },
    {
        "username": "bob",
        "email": "bob@example.com",
        "hashed_password": "dev_only_hash_bob",
        "is_active": True,
    },
]

TEST_PAPERS = [
    {
        "arxiv_id": "2401.00001",
        "title": "ScholarGraph: Mapping Research Influence with Citation Graphs",
        "abstract": "A prototype system for analysing research influence using citation graphs, semantic search, and ranking.",
        "published_date": date(2024, 1, 5),
        "updated_date": datetime(2024, 1, 6, 10, 0, tzinfo=UTC),
        "primary_category": "cs.IR",
        "all_categories": ["cs.IR", "cs.DL"],
        "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
        "pagerank_score": 0.12,
    },
    {
        "arxiv_id": "2401.00002",
        "title": "Neural Retrieval for Scientific Documents",
        "abstract": "This paper explores dense retrieval techniques for scientific corpora with transformer embeddings.",
        "published_date": date(2024, 1, 12),
        "updated_date": datetime(2024, 1, 13, 9, 30, tzinfo=UTC),
        "primary_category": "cs.IR",
        "all_categories": ["cs.IR", "cs.LG"],
        "pdf_url": "https://arxiv.org/pdf/2401.00002.pdf",
        "pagerank_score": 0.25,
    },
    {
        "arxiv_id": "2401.00003",
        "title": "PageRank Variants for Academic Citation Networks",
        "abstract": "An evaluation of graph ranking methods on directed citation networks.",
        "published_date": date(2024, 2, 1),
        "updated_date": datetime(2024, 2, 2, 14, 15, tzinfo=UTC),
        "primary_category": "cs.SI",
        "all_categories": ["cs.SI", "cs.IR"],
        "pdf_url": "https://arxiv.org/pdf/2401.00003.pdf",
        "pagerank_score": 0.31,
    },
    {
        "arxiv_id": "2401.00004",
        "title": "Vector Search in Research Paper Repositories",
        "abstract": "A practical study of embedding-based semantic search over academic metadata and abstracts.",
        "published_date": date(2024, 2, 20),
        "updated_date": datetime(2024, 2, 21, 8, 45, tzinfo=UTC),
        "primary_category": "cs.DB",
        "all_categories": ["cs.DB", "cs.IR"],
        "pdf_url": "https://arxiv.org/pdf/2401.00004.pdf",
        "pagerank_score": 0.18,
    },
    {
        "arxiv_id": "2401.00005",
        "title": "Benchmarking Research Discovery APIs",
        "abstract": "We benchmark API design choices for paper search, filtering, ranking, and annotation workflows.",
        "published_date": date(2024, 3, 3),
        "updated_date": datetime(2024, 3, 4, 11, 0, tzinfo=UTC),
        "primary_category": "cs.SE",
        "all_categories": ["cs.SE", "cs.IR"],
        "pdf_url": "https://arxiv.org/pdf/2401.00005.pdf",
        "pagerank_score": 0.09,
    },
]


async def seed_users() -> int:
    created = 0
    async with AsyncSessionLocal() as session:
        for user_data in TEST_USERS:
            result = await session.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()

            if existing_user is None:
                session.add(User(**user_data))
                created += 1

        await session.commit()

    return created


async def seed_papers() -> int:
    created = 0
    async with AsyncSessionLocal() as session:
        for paper_data in TEST_PAPERS:
            result = await session.execute(
                select(Paper).where(Paper.arxiv_id == paper_data["arxiv_id"])
            )
            existing_paper = result.scalar_one_or_none()

            if existing_paper is None:
                session.add(Paper(**paper_data))
                created += 1

        await session.commit()

    return created


async def main() -> None:
    users_created = await seed_users()
    papers_created = await seed_papers()

    print(f"Seed complete. Users created: {users_created}, Papers created: {papers_created}")


if __name__ == "__main__":
    asyncio.run(main())