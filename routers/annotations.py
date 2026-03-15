from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from models.annotation import Annotation
from models.paper import Paper
from models.user import User
from schemas.paper import AnnotationCreate, AnnotationResponse, AnnotationUpdate

router = APIRouter()


async def _get_paper_or_404(
    db: AsyncSession,
    paper_id: uuid.UUID,
) -> Paper:
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id)
    )
    paper = result.scalar_one_or_none()

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with id '{paper_id}' was not found.",
        )

    return paper


async def _get_annotation_or_404(
    db: AsyncSession,
    annotation_id: uuid.UUID,
) -> Annotation:
    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id)
    )
    annotation = result.scalar_one_or_none()

    if annotation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation with id '{annotation_id}' was not found.",
        )

    return annotation


@router.post(
    "/papers/{paper_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    paper_id: uuid.UUID,
    annotation_create: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AnnotationResponse:
    """
    Create an annotation for a paper.

    The authenticated user becomes the annotation owner.
    """
    await _get_paper_or_404(db, paper_id)

    annotation = Annotation(
        user_id=current_user.id,
        paper_id=paper_id,
        title=annotation_create.title,
        body=annotation_create.body,
        tags=annotation_create.tags,
    )

    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)

    return AnnotationResponse.model_validate(annotation)


@router.get(
    "/papers/{paper_id}/annotations",
    response_model=list[AnnotationResponse],
)
async def list_annotations_for_paper(
    paper_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[AnnotationResponse]:
    """
    Return all annotations for a paper.

    This endpoint is public.
    """
    await _get_paper_or_404(db, paper_id)

    result = await db.execute(
        select(Annotation)
        .where(Annotation.paper_id == paper_id)
        .order_by(Annotation.created_at.desc())
    )
    annotations = result.scalars().all()

    return [AnnotationResponse.model_validate(annotation) for annotation in annotations]


@router.put(
    "/annotations/{annotation_id}",
    response_model=AnnotationResponse,
)
async def update_annotation(
    annotation_id: uuid.UUID,
    annotation_update: AnnotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AnnotationResponse:
    """
    Update an annotation.

    Only the annotation owner may update it.
    """
    annotation = await _get_annotation_or_404(db, annotation_id)

    if annotation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own annotations.",
        )

    update_data = annotation_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(annotation, field, value)

    await db.commit()
    await db.refresh(annotation)

    return AnnotationResponse.model_validate(annotation)


@router.delete(
    "/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_annotation(
    annotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """
    Delete an annotation.

    Only the annotation owner may delete it.
    """
    annotation = await _get_annotation_or_404(db, annotation_id)

    if annotation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own annotations.",
        )

    await db.delete(annotation)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)