import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern definitions — UAE-specific + generic sensitive data
# ---------------------------------------------------------------------------

_PATTERNS = [
    (
        "EMIRATES-ID",
        re.compile(r"\b784-\d{4}-\d{7}-\d{1}\b"),
    ),
    (
        "UAE-IBAN",
        re.compile(r"\bAE\d{21}\b"),
    ),
    (
        "UAE-PHONE",
        re.compile(r"(\+971|00971|0)[\s\-]?[0-9]{8,9}\b"),
    ),
    (
        "CREDIT-CARD",
        re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"),
    ),
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "PASSPORT",
        re.compile(r"\b[A-Z]{1,2}[0-9]{6,9}\b"),
    ),
    (
        "API-KEY",
        # Long alphanumeric strings near key/token/secret keywords
        re.compile(
            r"(?:api[_\-]?key|token|secret|password|passwd|auth)[\"\':\s=]+[A-Za-z0-9\-_]{20,}",
            re.IGNORECASE,
        ),
    ),
]


def sanitize(text: str) -> Tuple[str, list[str]]:
    """
    Scan text for sensitive patterns and replace them with redaction tokens.

    Returns:
        sanitized_text (str): text with sensitive values replaced
        redacted_types (list[str]): list of pattern names that were found
    """
    redacted_types: list[str] = []

    for label, pattern in _PATTERNS:
        matches = pattern.findall(text)
        if matches:
            redacted_types.append(label)
            text = pattern.sub(f"[REDACTED-{label}]", text)
            logger.info("PII interceptor: redacted %d match(es) of type %s", len(matches), label)

    if redacted_types:
        logger.warning("PII sanitization removed types: %s", redacted_types)

    return text, redacted_types
    