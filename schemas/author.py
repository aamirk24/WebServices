from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from schemas.paper import PaperResponse


class AuthorListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    paper_count: int
    avg_pagerank_score: float | None


class AuthorListResponse(BaseModel):
    items: list[AuthorListItem]
    total: int


class AuthorDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    paper_count: int
    avg_pagerank_score: float | None
    papers: list[PaperResponse]