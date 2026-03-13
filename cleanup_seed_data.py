import asyncio

from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from models.paper import Paper
from models.user import User

SEEDED_ARXIV_IDS = [
    "2401.00001",
    "2401.00002",
    "2401.00003",
    "2401.00004",
    "2401.00005",
]

SEEDED_USER_EMAILS = [
    "alice@example.com",
    "bob@example.com",
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        try:
            # Count papers before delete
            papers_before = await db.execute(
                select(Paper).where(Paper.arxiv_id.in_(SEEDED_ARXIV_IDS))
            )
            papers_to_delete = papers_before.scalars().all()

            # Count users before delete
            users_before = await db.execute(
                select(User).where(User.email.in_(SEEDED_USER_EMAILS))
            )
            users_to_delete = users_before.scalars().all()

            # Delete seeded papers
            paper_result = await db.execute(
                delete(Paper).where(Paper.arxiv_id.in_(SEEDED_ARXIV_IDS))
            )

            # Delete seeded users
            user_result = await db.execute(
                delete(User).where(User.email.in_(SEEDED_USER_EMAILS))
            )

            await db.commit()

            print("Cleanup complete.")
            print(f"Seeded papers found: {len(papers_to_delete)}")
            print(f"Seeded users found: {len(users_to_delete)}")
            print(f"Papers deleted: {paper_result.rowcount or 0}")
            print(f"Users deleted: {user_result.rowcount or 0}")

        except Exception:
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())