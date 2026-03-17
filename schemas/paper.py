from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.utils import HalResponse


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", text)
    return cleaned.strip()


class PaperResponse(HalResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

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


class CitationPaperResponse(PaperResponse):
    direction: Literal["cited_by", "references"]


class CitationPaperList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CitationPaperResponse]
    total: int
    page: int
    size: int


class PaperAuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    position: int


class PaperAuthorList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[PaperAuthorResponse]
    total: int
    page: int
    size: int


class AnnotationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    body: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_html_from_text_fields(cls, value: str | None):
        if value is None:
            return value
        return _strip_html(value)

    @field_validator("tags", mode="before")
    @classmethod
    def strip_html_from_tags(cls, value):
        if value is None:
            return []
        return [_strip_html(tag) for tag in value]


class AnnotationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    body: str | None = None
    tags: list[str] | None = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_html_from_text_fields(cls, value: str | None):
        if value is None:
            return value
        return _strip_html(value)

    @field_validator("tags", mode="before")
    @classmethod
    def strip_html_from_tags(cls, value):
        if value is None:
            return value
        return [_strip_html(tag) for tag in value]


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


class RankedPaperResponse(PaperResponse):
    rank: int


class RankedPaperList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[RankedPaperResponse]
    total: int
    limit: int
    category: str | None = None


class SemanticSearchQueryParams(BaseModel):
    q: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    category: str | None = None

    @field_validator("q", mode="before")
    @classmethod
    def strip_html_from_query(cls, value: str):
        return _strip_html(value)


class SemanticSearchPaperResponse(PaperResponse):
    similarity_score: float


class SemanticSearchPaperList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[SemanticSearchPaperResponse]
    total: int
    limit: int
    query: str
    category: str | None = None