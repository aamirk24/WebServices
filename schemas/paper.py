from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    arxiv_id: str
    title: str
    abstract: str | None
    published_date: date | None
    updated_date: datetime | None
    primary_category: str | None
    all_categories: list[str] | None
    pdf_url: str | None
    pagerank_score: float
    created_at: datetime


class PaperList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[PaperResponse]
    total: int
    page: int
    size: int


class AnnotationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    body: str
    tags: list[str] = Field(default_factory=list)


class AnnotationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    body: str | None = None
    tags: list[str] | None = None


class AnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    paper_id: uuid.UUID
    title: str | None
    body: str
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime