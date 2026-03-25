import logging
from typing import Optional

import tiktoken
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Use cl100k_base as a universal approximation for all models
_ENCODING = tiktoken.get_encoding("cl100k_base")


class TokenCountRequest(BaseModel):
    document_text: Optional[str] = ""
    retrieved_chunks: Optional[str] = ""
    model_name: Optional[str] = "llama3"


class TokenCountResponse(BaseModel):
    document_tokens: int
    chunk_tokens: int
    total_tokens: int
    context_window: int
    percentage_used: float


@router.post("/token-count", response_model=TokenCountResponse, status_code=status.HTTP_200_OK)
async def token_count(request: TokenCountRequest) -> TokenCountResponse:
    """
    Count tokens in document + retrieved chunks and return
    percentage of the model context window consumed.
    """
    try:
        doc_tokens = len(_ENCODING.encode(request.document_text or ""))
        chunk_tokens = len(_ENCODING.encode(request.retrieved_chunks or ""))
        total = doc_tokens + chunk_tokens

        context_window = settings.context_windows.get(
            request.model_name,
            settings.context_windows.get(
                f"{request.model_name}:latest", 8192
            ),
        )

        percentage = round((total / context_window) * 100, 1) if context_window > 0 else 0.0
        percentage = min(percentage, 100.0)  # cap at 100%

        logger.info(
            "Token count | doc=%d | chunks=%d | total=%d | window=%d | pct=%.1f%%",
            doc_tokens, chunk_tokens, total, context_window, percentage,
        )

        return TokenCountResponse(
            document_tokens=doc_tokens,
            chunk_tokens=chunk_tokens,
            total_tokens=total,
            context_window=context_window,
            percentage_used=percentage,
        )

    except Exception as e:
        logger.error("Token count failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token counting failed: {str(e)}",
        )