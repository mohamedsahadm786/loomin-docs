import time
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db, ChatHistory
from app.services.ollama import ollama_client
from app.services import rag, pii
from app.services.tracing import TraceContext, compute_trace
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

SYSTEM_PROMPT = (
    "You are a professional enterprise document assistant. "
    "You only answer questions grounded in the provided document context. "
    "Always cite your sources. Never fabricate information. "
    "If the answer is not in the context, say so clearly."
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    document_id: Optional[str] = None
    model: Optional[str] = None
    document_content: Optional[str] = ""
    skip_rag: bool = False


class CitationItem(BaseModel):
    source: str
    chunk_id: int
    preview_text: str


class ChatResponse(BaseModel):
    response: str
    citations: list[CitationItem]
    redacted_fields: list[str]
    trace: dict


class HistoryItem(BaseModel):
    id: str
    role: str
    content: str
    citations: list
    trace: dict
    timestamp: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Main chat endpoint.
    Flow: PII sanitize → RAG retrieve → build prompt → Ollama → return with citations + trace
    """
    trace_ctx = TraceContext()
    model = request.model or settings.ollama_default_model

    # 1. PII interception
    sanitized_message, redacted_fields = pii.sanitize(request.message)
    if redacted_fields:
        logger.warning(
            "Request %s: PII redacted before LLM — types: %s",
            trace_ctx.request_id, redacted_fields,
        )

    # 2. RAG retrieval
    trace_ctx.retrieval_start = time.perf_counter()
    retrieved_chunks = [] if request.skip_rag else rag.retrieve(sanitized_message, top_k=3)
    trace_ctx.retrieval_end = time.perf_counter()

    # 3. Build citations
    citations = [
        CitationItem(
            source=chunk["source"],
            chunk_id=chunk["chunk_id"],
            preview_text=chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
        )
        for chunk in retrieved_chunks
    ]

    # 4. Build prompt
    context_parts = []

    if request.document_content and request.document_content.strip():
        context_parts.append(
            f"=== ACTIVE DOCUMENT ===\n{request.document_content[:3000]}"
        )

    if retrieved_chunks:
        chunks_text = "\n\n".join(
            f"[Source: {c['source']} | Chunk {c['chunk_id']}]\n{c['text']}"
            for c in retrieved_chunks
        )
        context_parts.append(f"=== RETRIEVED CONTEXT ===\n{chunks_text}")

    context_block = "\n\n".join(context_parts) if context_parts else "No additional context available."

    prompt = (
        f"{context_block}\n\n"
        f"=== USER QUESTION ===\n{sanitized_message}\n\n"
        f"=== YOUR RESPONSE ===\n"
    )

    # 5. Ollama call
    trace_ctx.llm_start = time.perf_counter()
    try:
        ollama_response = await ollama_client.generate(
            prompt=prompt,
            model=model,
            system_prompt=SYSTEM_PROMPT,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    trace_ctx.llm_end = time.perf_counter()

    trace_ctx.prompt_tokens = ollama_response["prompt_tokens"]
    trace_ctx.completion_tokens = ollama_response["completion_tokens"]

    # 6. Compute trace
    trace = compute_trace(trace_ctx)

    # 7. Persist to chat history
    try:
        history_entry = ChatHistory(
            id=str(uuid.uuid4()),
            document_id=request.document_id,
            role="user",
            content=request.message,   # store original, not sanitized
            citations=[],
            trace={},
        )
        assistant_entry = ChatHistory(
            id=str(uuid.uuid4()),
            document_id=request.document_id,
            role="assistant",
            content=ollama_response["text"],
            citations=[c.model_dump() for c in citations],
            trace=trace,
        )
        db.add(history_entry)
        db.add(assistant_entry)
        await db.commit()
    except Exception as e:
        logger.error("Failed to persist chat history: %s", e)
        # Non-fatal — response still returns even if persistence fails

    return ChatResponse(
        response=ollama_response["text"],
        citations=citations,
        redacted_fields=redacted_fields,
        trace=trace,
    )


@router.get("/history/{document_id}", response_model=list[HistoryItem])
async def get_chat_history(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[HistoryItem]:
    """Return full chat history for a document."""
    try:
        result = await db.execute(
            select(ChatHistory)
            .where(ChatHistory.document_id == document_id)
            .order_by(ChatHistory.timestamp)
        )
        rows = result.scalars().all()
        return [
            HistoryItem(
                id=row.id,
                role=row.role,
                content=row.content,
                citations=row.citations or [],
                trace=row.trace or {},
                timestamp=row.timestamp.isoformat(),
            )
            for row in rows
        ]
    except Exception as e:
        logger.error("Failed to fetch chat history for %s: %s", document_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat history.",
        )