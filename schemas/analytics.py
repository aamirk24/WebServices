from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from schemas.paper import PaperResponse


class PageRankResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    paper_id: uuid.UUID
    title: str
    score: float
    rank: int


class TrendPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    count: int


class SemanticSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    paper: PaperResponse
    similarity_score: float


class AuthorImpact(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author: str
    total_citations: int
    top_papers: list[PaperResponse]