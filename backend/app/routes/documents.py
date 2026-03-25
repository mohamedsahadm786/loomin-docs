import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db, Document, DocumentVersion

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DocumentCreate(BaseModel):
    title: str
    content: Optional[str] = ""


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class VersionItem(BaseModel):
    version: int
    content: str
    saved_at: str


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    version: int
    created_at: str
    updated_at: str
    version_history: Optional[list[VersionItem]] = None


class DocumentSummary(BaseModel):
    id: str
    title: str
    version: int
    updated_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Create a new document."""
    doc = Document(
        id=str(uuid.uuid4()),
        title=payload.title,
        content=payload.content or "",
        version=1,
        deleted=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(doc)
    try:
        await db.commit()
        await db.refresh(doc)
        logger.info("Created document: %s | title=%s", doc.id, doc.title)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to create document: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create document.",
        )

    return _to_response(doc)


@router.get("", response_model=list[DocumentSummary])
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[DocumentSummary]:
    """List all non-deleted documents."""
    try:
        result = await db.execute(
            select(Document)
            .where(Document.deleted == False)  # noqa: E712
            .order_by(Document.updated_at.desc())
        )
        docs = result.scalars().all()
        return [
            DocumentSummary(
                id=d.id,
                title=d.title,
                version=d.version,
                updated_at=d.updated_at.isoformat(),
            )
            for d in docs
        ]
    except Exception as e:
        logger.error("Failed to list documents: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents.",
        )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get a single document including its full version history."""
    doc = await _get_or_404(doc_id, db)

    # Fetch version history
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version.desc())
    )
    versions = result.scalars().all()
    version_history = [
        VersionItem(
            version=v.version,
            content=v.content,
            saved_at=v.saved_at.isoformat(),
        )
        for v in versions
    ]

    response = _to_response(doc)
    response.version_history = version_history
    return response


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    payload: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Update document title or content.
    Automatically saves the previous content as a version snapshot.
    """
    doc = await _get_or_404(doc_id, db)

    # Save current content as a version snapshot before overwriting
    if payload.content is not None and payload.content != doc.content:
        snapshot = DocumentVersion(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            version=doc.version,
            content=doc.content,
            saved_at=datetime.utcnow(),
        )
        db.add(snapshot)
        doc.version = doc.version + 1
        logger.info(
            "Saved version snapshot %d for document %s",
            doc.version - 1, doc_id,
        )

    if payload.title is not None:
        doc.title = payload.title
    if payload.content is not None:
        doc.content = payload.content

    doc.updated_at = datetime.utcnow()

    try:
        await db.commit()
        await db.refresh(doc)
        logger.info("Updated document %s to version %d", doc_id, doc.version)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to update document %s: %s", doc_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document.",
        )

    return _to_response(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete a document (sets deleted=True, data is preserved)."""
    doc = await _get_or_404(doc_id, db)
    doc.deleted = True
    doc.updated_at = datetime.utcnow()

    try:
        await db.commit()
        logger.info("Soft-deleted document %s", doc_id)
        return {"message": f"Document '{doc_id}' deleted successfully."}
    except Exception as e:
        await db.rollback()
        logger.error("Failed to delete document %s: %s", doc_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document.",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_404(doc_id: str, db: AsyncSession) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.deleted == False,  # noqa: E712
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )
    return doc


def _to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        version=doc.version,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
    )