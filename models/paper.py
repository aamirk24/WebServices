from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.author import PaperAuthor

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Float, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (
        Index("ix_papers_arxiv_id", "arxiv_id"),
        Index("ix_papers_published_date", "published_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    arxiv_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    abstract: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    updated_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    primary_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    all_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    pdf_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    pagerank_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    abstract_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    author_links: Mapped[list["PaperAuthor"]] = relationship(
    back_populates="paper",
    cascade="all, delete-orphan",
    )
