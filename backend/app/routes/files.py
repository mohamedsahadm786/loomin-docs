import os
import logging
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pydantic import BaseModel

from app.services import rag

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("./uploads")
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class FileMetadata(BaseModel):
    filename: str
    size_bytes: int
    content_type: str
    chunks_indexed: int


class FileListItem(BaseModel):
    filename: str
    size_bytes: int
    path: str


@router.post("/upload", response_model=FileMetadata, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)) -> FileMetadata:
    """
    Upload a PDF, MD, or TXT file and index it into FAISS for RAG retrieval.
    """
    _ensure_upload_dir()

    # Validate extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Save file to disk
    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        logger.info("Saved uploaded file: %s (%d bytes)", safe_filename, len(contents))
    except Exception as e:
        logger.error("Failed to save file %s: %s", file.filename, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    # Extract text and index
    try:
        file_type = suffix.lstrip(".")
        text = rag.extract_text(str(file_path), file_type)
        chunks = rag.chunk_text(text, source=file.filename)
        rag.build_index(chunks)
        logger.info("Indexed %d chunks for file: %s", len(chunks), file.filename)
    except Exception as e:
        # Clean up saved file if indexing fails
        file_path.unlink(missing_ok=True)
        logger.error("Indexing failed for %s: %s", file.filename, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File saved but indexing failed: {str(e)}",
        )

    return FileMetadata(
        filename=file.filename,
        size_bytes=len(contents),
        content_type=file.content_type or "application/octet-stream",
        chunks_indexed=len(chunks),
    )


@router.get("", response_model=List[FileListItem])
async def list_files() -> List[FileListItem]:
    """List all uploaded files."""
    _ensure_upload_dir()
    items = []
    for f in sorted(UPLOAD_DIR.iterdir()):
        if f.is_file():
            # Strip the UUID prefix we added on upload
            parts = f.name.split("_", 1)
            display_name = parts[1] if len(parts) == 2 else f.name
            items.append(FileListItem(
                filename=display_name,
                size_bytes=f.stat().st_size,
                path=str(f),
            ))
    return items


@router.delete("/{filename}", status_code=status.HTTP_200_OK)
async def delete_file(filename: str) -> dict:
    """
    Remove a file from disk and remove its chunks from the FAISS index.
    """
    _ensure_upload_dir()

    # Find the file on disk (it has a UUID prefix)
    matched = None
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and f.name.endswith(filename):
            matched = f
            break

    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}",
        )

    # Remove from FAISS index first
    removed_chunks = rag.remove_file_from_index(filename)
    logger.info("Removed %d chunks for file: %s", removed_chunks, filename)

    # Delete from disk
    matched.unlink()
    logger.info("Deleted file from disk: %s", matched.name)

    return {
        "message": f"File '{filename}' deleted successfully.",
        "chunks_removed": removed_chunks,
    }