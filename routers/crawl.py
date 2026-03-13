from __future__ import annotations

import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.dependencies import get_current_active_user
from models.user import User
from services.crawler import crawl_topic

logger = logging.getLogger(__name__)

router = APIRouter()

# Temporary admin allowlist until you add a real role/is_admin field
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("CRAWL_ADMIN_EMAILS", "your-email@example.com").split(",")
    if email.strip()
}


class CrawlRequest(BaseModel):
    topic: str = Field(..., examples=["cs.AI"])
    max_papers: int = Field(default=200, ge=1, le=1000)


class CrawlAcceptedResponse(BaseModel):
    message: str
    topic: str
    query: str
    max_papers: int


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.email.lower() not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def topic_to_query(topic: str) -> str:
    """
    Convert shorthand topics like 'cs.AI' into arXiv query syntax 'cat:cs.AI'.
    If the caller already passes something like 'cat:cs.AI' or 'ti:transformer',
    leave it unchanged.
    """
    topic = topic.strip()
    if ":" in topic:
        return topic
    return f"cat:{topic}"


async def run_crawl_job(topic_query: str, max_papers: int) -> None:
    """
    Background crawl task.

    Opens its own AsyncSession because request-scoped DB sessions are gone by the
    time FastAPI runs background tasks.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await crawl_topic(
                db=db,
                topic=topic_query,
                max_papers=max_papers,
            )
            logger.info(
                "Background crawl finished | query=%r max_papers=%d result=%r",
                topic_query,
                max_papers,
                result,
            )
        except Exception:
            logger.exception(
                "Background crawl failed | query=%r max_papers=%d",
                topic_query,
                max_papers,
            )


@router.post(
    "",
    response_model=CrawlAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_crawl(
    crawl_request: CrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user),
) -> CrawlAcceptedResponse:
    """
    Start a background crawl job for an arXiv topic.

    This endpoint is JWT-protected and temporarily restricted to admin users.
    It returns immediately with HTTP 202 Accepted while the crawl continues
    in the background.
    """
    topic_query = topic_to_query(crawl_request.topic)

    background_tasks.add_task(
        run_crawl_job,
        topic_query,
        crawl_request.max_papers,
    )

    return CrawlAcceptedResponse(
        message="Crawl job accepted and started in the background",
        topic=crawl_request.topic,
        query=topic_query,
        max_papers=crawl_request.max_papers,
    )