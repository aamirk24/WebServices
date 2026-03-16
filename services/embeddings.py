from __future__ import annotations

import hashlib
import html
import logging
import re
from functools import lru_cache
from typing import Any
from math import ceil
from sentence_transformers import SentenceTransformer

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.paper import Paper

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

_model: SentenceTransformer | None = None
_TEXT_REGISTRY: dict[str, str] = {}


def load_embedding_model() -> SentenceTransformer:
    global _model

    if _model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info(
            "Embedding model loaded | name=%s dimension=%d",
            EMBEDDING_MODEL_NAME,
            EMBEDDING_DIMENSION,
        )

    return _model


def get_embedding_model() -> SentenceTransformer:
    if _model is None:
        raise RuntimeError(
            "Embedding model has not been loaded yet. "
            "Call load_embedding_model() during app startup."
        )
    return _model


def set_embedding_model_on_app(app: FastAPI) -> None:
    """
    Load the embedding model once and store it on FastAPI app.state.
    """
    app.state.embedding_model = load_embedding_model()


def unload_embedding_model() -> None:
    """
    Clear the cached embedding model and embedding cache.
    """
    global _model
    _model = None
    _TEXT_REGISTRY.clear()
    _generate_embedding_cached.cache_clear()


def _strip_html(text: str) -> str:
    text = html.unescape(text)
    return re.sub(r"<[^>]+>", " ", text)


def _normalise_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _get_tokenizer(model: SentenceTransformer) -> Any:
    """
    Get the underlying Hugging Face tokenizer from the SentenceTransformer model.
    """
    if hasattr(model, "tokenizer"):
        return model.tokenizer

    first_module = model._first_module()
    if hasattr(first_module, "tokenizer"):
        return first_module.tokenizer

    raise RuntimeError("Could not access tokenizer from embedding model.")


def _truncate_to_512_tokens(text: str) -> str:
    """
    Truncate text to 512 model tokens and decode back to text.
    """
    model = get_embedding_model()
    tokenizer = _get_tokenizer(model)

    encoded = tokenizer(
        text,
        truncation=True,
        max_length=512,
        return_attention_mask=False,
        return_token_type_ids=False,
    )

    input_ids = encoded["input_ids"]

    # Convert truncated token ids back into text for a stable cached payload
    return tokenizer.decode(
        input_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ).strip()


def _preprocess_text(text: str) -> str:
    """
    Preprocess text before embedding:
    - strip HTML
    - normalise whitespace
    - truncate to 512 tokens
    """
    cleaned = _strip_html(text)
    cleaned = _normalise_whitespace(cleaned)
    cleaned = _truncate_to_512_tokens(cleaned)
    cleaned = _normalise_whitespace(cleaned)
    return cleaned


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=2048)
def _generate_embedding_cached(text_hash: str) -> tuple[float, ...]:
    """
    Cached internal embedding generator.

    Uses the hashed, preprocessed text as the cache key, while the actual
    preprocessed text is looked up from the in-memory registry.
    """
    text = _TEXT_REGISTRY.get(text_hash)
    if text is None:
        raise RuntimeError("Cached text payload not found for embedding hash.")

    model = get_embedding_model()
    vector = model.encode(text, convert_to_numpy=True)
    return tuple(float(x) for x in vector.tolist())


def generate_embedding(text: str) -> list[float]:
    """
    Generate a 384-dimensional embedding vector for text.

    Steps:
    - strip HTML
    - normalise whitespace
    - truncate to 512 tokens
    - cache repeated requests in memory using an LRU cache on the hashed text key

    Returns:
        list[float]
    """
    processed_text = _preprocess_text(text)
    text_hash = _hash_text(processed_text)

    existing = _TEXT_REGISTRY.get(text_hash)
    if existing is None:
        _TEXT_REGISTRY[text_hash] = processed_text
    elif existing != processed_text:
        raise RuntimeError("Hash collision detected in embedding text registry.")

    return list(_generate_embedding_cached(text_hash))


async def embed_all_papers(
    db: AsyncSession,
    batch_size: int = 32,
) -> dict[str, int]:
    """
    Embed all papers whose abstract_embedding is currently NULL.

    Behavior:
    - fetch all papers with NULL abstract_embedding and non-null abstract
    - preprocess abstracts before embedding
    - encode in batches of 32 for efficient CPU inference
    - store each embedding into papers.abstract_embedding
    - commit after each batch
    - log progress to console

    Returns:
        {
            "found": int,
            "embedded": int,
            "skipped_empty": int,
            "errors": int,
        }
    """
    model = get_embedding_model()

    result = await db.execute(
        select(Paper)
        .where(
            Paper.abstract_embedding.is_(None),
            Paper.abstract.is_not(None),
        )
        .order_by(Paper.created_at.asc(), Paper.id.asc())
    )
    papers = list(result.scalars().all())

    total = len(papers)
    if total == 0:
        logger.info("embed_all_papers: no papers with NULL abstract_embedding found.")
        return {
            "found": 0,
            "embedded": 0,
            "skipped_empty": 0,
            "errors": 0,
        }

    logger.info(
        "embed_all_papers: starting | papers_to_embed=%d batch_size=%d",
        total,
        batch_size,
    )

    embedded = 0
    skipped_empty = 0
    errors = 0
    total_batches = ceil(total / batch_size)

    for batch_index, start in enumerate(range(0, total, batch_size), start=1):
        batch = papers[start : start + batch_size]

        batch_papers: list[Paper] = []
        batch_texts: list[str] = []

        for paper in batch:
            raw_text = paper.abstract or ""
            processed_text = _preprocess_text(raw_text)

            if not processed_text:
                skipped_empty += 1
                continue

            batch_papers.append(paper)
            batch_texts.append(processed_text)

        if not batch_texts:
            logger.info(
                "embed_all_papers: batch %d/%d skipped | all texts empty after preprocessing",
                batch_index,
                total_batches,
            )
            continue

        try:
            vectors = model.encode(
                batch_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            for paper, vector in zip(batch_papers, vectors, strict=True):
                paper.abstract_embedding = vector.tolist()
                embedded += 1

            await db.commit()

            logger.info(
                "embed_all_papers: batch %d/%d complete | embedded=%d/%d skipped_empty=%d errors=%d",
                batch_index,
                total_batches,
                embedded,
                total,
                skipped_empty,
                errors,
            )

        except Exception:
            await db.rollback()
            errors += len(batch_papers)
            logger.exception(
                "embed_all_papers: batch %d/%d failed",
                batch_index,
                total_batches,
            )

    logger.info(
        "embed_all_papers: finished | found=%d embedded=%d skipped_empty=%d errors=%d",
        total,
        embedded,
        skipped_empty,
        errors,
    )

    return {
        "found": total,
        "embedded": embedded,
        "skipped_empty": skipped_empty,
        "errors": errors,
    }