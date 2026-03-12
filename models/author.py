from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.paper import Paper

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class Author(Base):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name_normalised: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    arxiv_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    paper_links: Mapped[list["PaperAuthor"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
    )


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("papers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("authors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    paper: Mapped["Paper"] = relationship(
        "Paper",
        back_populates="author_links",
    )
    author: Mapped["Author"] = relationship(
        back_populates="paper_links",
    )