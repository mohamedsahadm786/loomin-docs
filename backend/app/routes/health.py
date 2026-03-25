import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.database import get_db
from app.services.ollama import ollama_client
from app.services.rag import get_index_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Check status of all system components:
    backend, Ollama, FAISS index, and SQLite database.
    """
    components = {}
    models_available = []
    indexed_files = []

    # 1. Backend — if this runs, backend is ok
    components["backend"] = "ok"

    # 2. Ollama
    try:
        ollama_ok = await ollama_client.ping()
        components["ollama"] = "ok" if ollama_ok else "unreachable"
        if ollama_ok:
            models_available = await ollama_client.list_models()
    except Exception as e:
        logger.error("Ollama health check failed: %s", e)
        components["ollama"] = f"error: {str(e)}"

    # 3. FAISS index
    try:
        stats = get_index_stats()
        components["faiss_index"] = "ok" if stats["index_exists"] else "not_initialized"
        indexed_files = stats["indexed_files"]
    except Exception as e:
        logger.error("FAISS health check failed: %s", e)
        components["faiss_index"] = f"error: {str(e)}"

    # 4. SQLite
    try:
        await db.execute(text("SELECT 1"))
        components["sqlite"] = "ok"
    except Exception as e:
        logger.error("SQLite health check failed: %s", e)
        components["sqlite"] = f"error: {str(e)}"

    # Overall status — ok only if all components are ok
    overall = "ok" if all(v == "ok" for v in components.values()) else "degraded"

    return {
        "status": overall,
        "components": components,
        "models_available": models_available,
        "indexed_files": indexed_files,
        "indexed_file_count": len(indexed_files),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }