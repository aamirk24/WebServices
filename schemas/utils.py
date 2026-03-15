from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class HalResponse(BaseModel):
    """
    Base schema for HAL/HATEOAS-style responses.

    Uses `links` internally, but serializes as `_links`.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    links: dict[str, dict[str, str]] | None = Field(
        default=None,
        alias="_links",
    )


def build_links(
    paper_id: uuid.UUID | str,
    base_url: str,
) -> dict[str, dict[str, str]]:
    pid = str(paper_id)
    base = str(base_url).rstrip("/")

    return {
        "self": {"href": f"{base}/papers/{pid}"},
        "citations": {"href": f"{base}/papers/{pid}/citations"},
        "authors": {"href": f"{base}/papers/{pid}/authors"},
        "similar": {"href": f"{base}/papers/{pid}/similar"},
    }