from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Any

import httpx
import xmltodict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.author import Author, PaperAuthor
from models.paper import Paper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = (
    "ScholarGraph/0.1 (COMP3011 academic project; "
    "contact: your-email@leeds.ac.uk)"
)


class ArxivClient:
    """
    Async HTTP client for the arXiv Atom API.

    Handles:
    - polite rate limiting (3 seconds between requests)
    - retry logic with exponential backoff
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float | None = None

    async def __aenter__(self) -> "ArxivClient":
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.8",
            },
            timeout=httpx.Timeout(30.0),
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _respect_rate_limit(self) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()

        if self._last_request_time is not None:
            elapsed = now - self._last_request_time
            wait_time = max(0.0, 3.0 - elapsed)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self._last_request_time = loop.time()

    async def fetch_papers(
        self,
        query: str,
        start: int = 0,
        max_results: int = 100,
    ) -> str:
        """
        Fetch a batch of papers from the arXiv API.

        Args:
            query: arXiv search query, e.g. "cat:cs.AI" or "ti:transformer"
            start: pagination offset (0-indexed)
            max_results: number of results to fetch

        Returns:
            Raw Atom XML string.
        """
        if self._client is None:
            raise RuntimeError(
                "ArxivClient must be used as an async context manager."
            )

        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        max_attempts = 3
        base_delay = 5.0  # retry delays: 5s, 10s, 20s

        for attempt in range(1, max_attempts + 1):
            try:
                await self._respect_rate_limit()

                logger.info(
                    "Fetching arXiv papers | query=%r start=%d max=%d attempt=%d",
                    query,
                    start,
                    max_results,
                    attempt,
                )

                response = await self._client.get(ARXIV_API_URL, params=params)
                response.raise_for_status()
                return response.text

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning(
                    "arXiv request failed on attempt %d: %s",
                    attempt,
                    exc,
                )
                if attempt == max_attempts:
                    raise

                delay = base_delay * (2 ** (attempt - 1))
                logger.info("Retrying in %.0f seconds...", delay)
                await asyncio.sleep(delay)

        raise RuntimeError("Unreachable: retries exhausted")


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split()).strip()
    return str(value).strip()


def _normalise_author_name(raw: str) -> str:
    """
    Normalize an author name for de-duplication.
    Example:
    - 'Yann LeCun'
    - 'yann lecun'
    - 'Yann LéCun'
    all map to the same normalized key.
    """
    normalised = unicodedata.normalize("NFD", raw)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only).strip().lower()


def _extract_pdf_url(links: list[dict] | dict | None) -> str | None:
    if links is None:
        return None

    if isinstance(links, dict):
        links = [links]

    for link in links:
        if not isinstance(link, dict):
            continue

        if link.get("@type") == "application/pdf":
            return link.get("@href")

        if link.get("@title") == "pdf":
            return link.get("@href")

    return None


def _extract_categories(entry: dict[str, Any]) -> tuple[str | None, list[str]]:
    primary_category: str | None = None

    primary_raw = entry.get("arxiv:primary_category")
    if isinstance(primary_raw, dict):
        primary_category = primary_raw.get("@term")

    categories_raw = entry.get("category", [])
    categories_raw = _ensure_list(categories_raw)

    all_categories: list[str] = []
    for category in categories_raw:
        if isinstance(category, dict):
            term = category.get("@term")
            if term:
                all_categories.append(term)

    if primary_category is None and all_categories:
        primary_category = all_categories[0]

    return primary_category, all_categories


def parse_papers(xml_string: str) -> list[dict[str, Any]]:
    """
    Parse an arXiv Atom XML response into paper dictionaries.

    Each dict contains:
    - arxiv_id
    - title
    - abstract
    - authors
    - published
    - updated
    - primary_category
    - all_categories
    - pdf_url
    """
    try:
        parsed = xmltodict.parse(xml_string)
    except Exception as exc:
        logger.error("Failed to parse arXiv XML: %s", exc)
        return []

    feed = parsed.get("feed", {})
    entries = _ensure_list(feed.get("entry"))

    if not entries:
        logger.info("arXiv response contained 0 entries.")
        return []

    papers: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        try:
            raw_id = _clean_text(entry.get("id"))
            arxiv_id = raw_id.split("/abs/")[-1]
            arxiv_id = re.sub(r"v\d+$", "", arxiv_id).strip()

            if not arxiv_id:
                logger.warning("Skipping entry with no parseable arXiv ID: %r", raw_id)
                continue

            title = _clean_text(entry.get("title"))
            abstract = _clean_text(entry.get("summary"))

            authors_raw = _ensure_list(entry.get("author"))
            authors = [
                _clean_text(author.get("name"))
                for author in authors_raw
                if isinstance(author, dict) and author.get("name")
            ]

            published_raw = _clean_text(entry.get("published"))
            updated_raw = _clean_text(entry.get("updated"))

            published: date | None = None
            updated: datetime | None = None

            if published_raw:
                try:
                    published_dt = datetime.fromisoformat(
                        published_raw.replace("Z", "+00:00")
                    )
                    published = published_dt.date()
                except ValueError:
                    pass

            if updated_raw:
                try:
                    updated = datetime.fromisoformat(
                        updated_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            primary_category, all_categories = _extract_categories(entry)
            pdf_url = _extract_pdf_url(entry.get("link"))

            papers.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "published": published,
                    "updated": updated,
                    "primary_category": primary_category,
                    "all_categories": all_categories,
                    "pdf_url": pdf_url,
                }
            )

        except Exception as exc:
            logger.warning("Skipping malformed entry: %s", exc, exc_info=True)
            continue

    logger.info("Parsed %d papers from XML.", len(papers))
    return papers


async def save_paper_to_db(
    db: AsyncSession,
    paper_dict: dict[str, Any],
) -> Paper:
    """
    Upsert a paper and its author links into the database.

    - If arxiv_id already exists, update mutable metadata
    - If not, insert a new paper
    - Deduplicate authors by normalized name
    - Rebuild PaperAuthor links so author order stays correct

    This function flushes but does not commit.
    """
    arxiv_id: str = paper_dict["arxiv_id"]

    result = await db.execute(
        select(Paper).where(Paper.arxiv_id == arxiv_id)
    )
    paper = result.scalar_one_or_none()

    if paper is None:
        paper = Paper(arxiv_id=arxiv_id)
        db.add(paper)
        logger.debug("Inserting new paper: %s", arxiv_id)
    else:
        logger.debug("Updating existing paper: %s", arxiv_id)

    paper.title = paper_dict["title"]
    paper.abstract = paper_dict["abstract"]
    paper.published_date = paper_dict["published"]
    paper.updated_date = paper_dict["updated"]
    paper.primary_category = paper_dict["primary_category"]
    paper.all_categories = paper_dict["all_categories"]
    paper.pdf_url = paper_dict["pdf_url"]

    await db.flush()

    await db.execute(
        delete(PaperAuthor).where(PaperAuthor.paper_id == paper.id)
    )
    await db.flush()

    for position, raw_name in enumerate(paper_dict["authors"], start=1):
        normalised = _normalise_author_name(raw_name)
        if not normalised:
            continue

        author_result = await db.execute(
            select(Author).where(Author.name_normalised == normalised)
        )
        author = author_result.scalar_one_or_none()

        if author is None:
            author = Author(
                name=raw_name.strip(),
                name_normalised=normalised,
                arxiv_ids=None,
            )
            db.add(author)
            await db.flush()

        db.add(
            PaperAuthor(
                paper_id=paper.id,
                author_id=author.id,
                position=position,
            )
        )

    await db.flush()
    await db.refresh(paper)
    return paper


async def crawl_topic(
    db: AsyncSession,
    topic: str,
    max_papers: int = 200,
) -> dict[str, int]:
    """
    Crawl arXiv for a topic and persist papers in batches.

    Commits after each batch so partial progress is retained.
    """
    batch_size = 100
    total_fetched = 0
    inserted = 0
    updated = 0
    start = 0

    logger.info("Starting crawl | topic=%r max_papers=%d", topic, max_papers)

    async with ArxivClient() as client:
        while total_fetched < max_papers:
            remaining = max_papers - total_fetched
            this_batch = min(batch_size, remaining)

            try:
                xml = await client.fetch_papers(
                    query=topic,
                    start=start,
                    max_results=this_batch,
                )
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.error("Crawl aborted at offset %d: %s", start, exc)
                break

            papers = parse_papers(xml)

            if not papers:
                logger.info("No more papers returned at offset %d. Stopping.", start)
                break

            for paper_dict in papers:
                exists_result = await db.execute(
                    select(Paper.id).where(Paper.arxiv_id == paper_dict["arxiv_id"])
                )
                is_new = exists_result.scalar_one_or_none() is None

                await save_paper_to_db(db, paper_dict)

                if is_new:
                    inserted += 1
                else:
                    updated += 1

            await db.commit()

            batch_count = len(papers)
            total_fetched += batch_count
            start += batch_count

            logger.info(
                "Batch complete | offset=%d batch=%d total=%d inserted=%d updated=%d",
                start,
                batch_count,
                total_fetched,
                inserted,
                updated,
            )

            if batch_count < this_batch:
                logger.info("Partial batch returned. End of results reached.")
                break

    logger.info(
        "Crawl finished | topic=%r inserted=%d updated=%d total=%d",
        topic,
        inserted,
        updated,
        total_fetched,
    )

    return {
        "inserted": inserted,
        "updated": updated,
        "total_fetched": total_fetched,
    }