from __future__ import annotations

import logging
import uuid

from sqlalchemy import bindparam, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.citation import Citation
from models.paper import Paper

logger = logging.getLogger(__name__)


async def load_graph_from_db(
    db: AsyncSession,
) -> tuple[list[uuid.UUID], dict[uuid.UUID, list[uuid.UUID]], dict[uuid.UUID, int]]:
    """
    Load the citation graph from the database.

    Returns:
        paper_ids:
            List of all paper UUIDs in the corpus.

        in_links:
            Dict mapping paper_id -> list of paper_ids that cite it.

        out_count:
            Dict mapping paper_id -> number of outgoing citations.
    """
    paper_result = await db.execute(
        select(Paper.id).order_by(Paper.created_at.asc(), Paper.id.asc())
    )
    paper_ids = list(paper_result.scalars().all())

    in_links: dict[uuid.UUID, list[uuid.UUID]] = {
        paper_id: [] for paper_id in paper_ids
    }
    out_count: dict[uuid.UUID, int] = {
        paper_id: 0 for paper_id in paper_ids
    }

    citation_result = await db.execute(
        select(Citation.citing_paper_id, Citation.cited_paper_id)
    )
    citation_rows = citation_result.all()

    for citing_paper_id, cited_paper_id in citation_rows:
        if cited_paper_id in in_links:
            in_links[cited_paper_id].append(citing_paper_id)

        if citing_paper_id in out_count:
            out_count[citing_paper_id] += 1

    logger.info(
        "Loaded citation graph | papers=%d citations=%d dangling=%d",
        len(paper_ids),
        len(citation_rows),
        sum(1 for paper_id in paper_ids if out_count[paper_id] == 0),
    )

    return paper_ids, in_links, out_count


def _compute_pagerank_with_meta(
    graph_data: tuple[
        list[uuid.UUID],
        dict[uuid.UUID, list[uuid.UUID]],
        dict[uuid.UUID, int],
    ],
    damping: float = 0.85,
    max_iter: int = 100,
) -> tuple[dict[uuid.UUID, float], int]:
    """
    Internal PageRank implementation that also returns the convergence iteration.

    PageRank formula:
        PR(A) = (1-d)/N + d * Σ(PR(T_i)/C(T_i))

    Dangling nodes are handled by redistributing their score equally to all nodes.
    Convergence threshold:
        max absolute change < 0.0001
    """
    paper_ids, in_links, out_count = graph_data
    n = len(paper_ids)

    if n == 0:
        return {}, 0

    tolerance = 0.0001
    base_score = (1.0 - damping) / n

    scores: dict[uuid.UUID, float] = {
        paper_id: 1.0 / n for paper_id in paper_ids
    }

    converged_at = max_iter

    for iteration in range(1, max_iter + 1):
        new_scores: dict[uuid.UUID, float] = {}

        dangling_total = sum(
            scores[paper_id]
            for paper_id in paper_ids
            if out_count.get(paper_id, 0) == 0
        )
        dangling_contrib = dangling_total / n

        max_change = 0.0

        for paper_id in paper_ids:
            incoming_sum = 0.0

            for citer_id in in_links.get(paper_id, []):
                citer_out = out_count.get(citer_id, 0)
                if citer_out > 0:
                    incoming_sum += scores[citer_id] / citer_out

            new_score = base_score + damping * (incoming_sum + dangling_contrib)
            new_scores[paper_id] = new_score

            change = abs(new_score - scores[paper_id])
            if change > max_change:
                max_change = change

        scores = new_scores

        if max_change < tolerance:
            converged_at = iteration
            break

    return scores, converged_at


def compute_pagerank(
    graph_data: tuple[
        list[uuid.UUID],
        dict[uuid.UUID, list[uuid.UUID]],
        dict[uuid.UUID, int],
    ],
    damping: float = 0.85,
    max_iter: int = 100,
) -> dict[uuid.UUID, float]:
    """
    Public PageRank function.

    Initialises all nodes to 1/N, iterates until convergence or max_iter,
    handles dangling nodes, and returns:
        dict[paper_id] -> raw pagerank score
    """
    scores, _ = _compute_pagerank_with_meta(
        graph_data=graph_data,
        damping=damping,
        max_iter=max_iter,
    )
    return scores


async def save_pagerank_scores(
    db: AsyncSession,
    scores_dict: dict[uuid.UUID, float],
) -> None:
    """
    Bulk update the pagerank_score column on the papers table.

    Scores are normalised to the range 0..1 before saving by dividing
    by the maximum score.
    """
    if not scores_dict:
        return

    max_score = max(scores_dict.values()) if scores_dict else 0.0

    if max_score > 0:
        normalised_scores = {
            paper_id: score / max_score
            for paper_id, score in scores_dict.items()
        }
    else:
        normalised_scores = {
            paper_id: 0.0 for paper_id in scores_dict
        }

    rows = [
        {
            "b_paper_id": paper_id,
            "b_pagerank_score": normalised_score,
        }
        for paper_id, normalised_score in normalised_scores.items()
    ]

    stmt = (
        update(Paper.__table__)
        .where(Paper.__table__.c.id == bindparam("b_paper_id"))
        .values(pagerank_score=bindparam("b_pagerank_score"))
    )

    await db.execute(stmt, rows)
    await db.commit()


async def run_pagerank(
    db: AsyncSession,
    damping: float = 0.85,
    max_iter: int = 100,
) -> dict[str, int | float]:
    """
    Orchestrate PageRank on the live citation graph.

    Steps:
        1. load graph from DB
        2. compute pagerank
        3. save normalised scores back to papers table

    Logs:
        - N papers
        - M edges
        - converged at iteration K
    """
    graph_data = await load_graph_from_db(db)
    paper_ids, _, out_count = graph_data

    n_papers = len(paper_ids)
    m_edges = sum(out_count.values())

    if n_papers == 0:
        logger.info("PageRank skipped | papers=0 edges=0 converged_at=0")
        return {
            "papers": 0,
            "edges": 0,
            "iterations": 0,
            "max_score": 0.0,
        }

    scores, converged_at = _compute_pagerank_with_meta(
        graph_data=graph_data,
        damping=damping,
        max_iter=max_iter,
    )

    await save_pagerank_scores(db, scores)

    max_score = max(scores.values()) if scores else 0.0

    logger.info(
        "PageRank finished | papers=%d edges=%d converged_at=%d max_score=%.6f",
        n_papers,
        m_edges,
        converged_at,
        max_score,
    )

    return {
        "papers": n_papers,
        "edges": m_edges,
        "iterations": converged_at,
        "max_score": max_score,
    }