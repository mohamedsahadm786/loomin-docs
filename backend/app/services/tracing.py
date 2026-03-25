import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TraceContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retrieval_start: float = 0.0
    retrieval_end: float = 0.0
    llm_start: float = 0.0
    llm_end: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


def compute_trace(ctx: TraceContext) -> dict:
    """
    Compute latency metrics from a TraceContext and return
    the trace dict that is attached to every /chat response.
    """
    retrieval_ms = round((ctx.retrieval_end - ctx.retrieval_start) * 1000, 1)
    llm_ms = round((ctx.llm_end - ctx.llm_start) * 1000, 1)
    total_ms = round(retrieval_ms + llm_ms, 1)

    llm_seconds = (ctx.llm_end - ctx.llm_start)
    tokens_per_second = (
        round(ctx.completion_tokens / llm_seconds, 1)
        if llm_seconds > 0 and ctx.completion_tokens > 0
        else 0.0
    )

    trace = {
        "request_id": ctx.request_id,
        "retrieval_ms": retrieval_ms,
        "llm_ms": llm_ms,
        "total_ms": total_ms,
        "tokens_per_second": tokens_per_second,
        "prompt_tokens": ctx.prompt_tokens,
        "completion_tokens": ctx.completion_tokens,
    }

    logger.info(
        "Trace [%s] | retrieval=%sms | llm=%sms | tps=%s",
        ctx.request_id, retrieval_ms, llm_ms, tokens_per_second,
    )

    return trace