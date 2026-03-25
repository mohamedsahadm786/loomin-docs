import os
import logging
import pickle
from typing import Optional
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Module-level singletons — loaded once, reused across requests
# ---------------------------------------------------------------------------
_model: Optional[SentenceTransformer] = None
_index: Optional[faiss.IndexFlatL2] = None
_chunks: list[dict] = []   # [{text, source, chunk_id}]



def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        import os
        # In air-gapped deployments, SENTENCE_TRANSFORMERS_HOME points to
        # the bundled model cache directory. Falls back to HuggingFace download
        # in development environments with internet access.
        cache_dir = os.environ.get("SENTENCE_TRANSFORMERS_HOME", None)
        logger.info(
            "Loading embedding model: %s (cache_dir=%s)",
            settings.embedding_model, cache_dir or "default HuggingFace cache"
        )
        _model = SentenceTransformer(
            settings.embedding_model,
            cache_folder=cache_dir,
        )
        logger.info("Embedding model loaded successfully.")
    return _model


def _index_path() -> Path:
    return Path(settings.faiss_index_path)


def _save_index() -> None:
    path = _index_path()
    path.mkdir(parents=True, exist_ok=True)
    faiss.write_index(_index, str(path / "index.faiss"))
    with open(path / "chunks.pkl", "wb") as f:
        pickle.dump(_chunks, f)
    logger.info("FAISS index saved. Total chunks: %d", len(_chunks))


def _load_index() -> None:
    global _index, _chunks
    path = _index_path()
    index_file = path / "index.faiss"
    chunks_file = path / "chunks.pkl"
    if index_file.exists() and chunks_file.exists():
        _index = faiss.read_index(str(index_file))
        with open(chunks_file, "rb") as f:
            _chunks = pickle.load(f)
        logger.info("FAISS index loaded from disk. Chunks: %d", len(_chunks))
    else:
        logger.info("No existing FAISS index found. Starting fresh.")
        _index = faiss.IndexFlatL2(384)   # all-MiniLM-L6-v2 outputs 384 dims
        _chunks = []


def ensure_index_loaded() -> None:
    """Call this on startup or before first use."""
    global _index
    if _index is None:
        _load_index()


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(file_path: str, file_type: str) -> str:
    """Extract raw text from PDF, MD, or TXT file."""
    file_type = file_type.lower().lstrip(".")

    if file_type == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
            logger.info("Extracted %d chars from PDF: %s", len(text), file_path)
            return text
        except Exception as e:
            logger.error("PDF extraction failed for %s: %s", file_path, e)
            raise

    elif file_type in ("md", "txt"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            logger.info("Extracted %d chars from %s: %s", len(text), file_type, file_path)
            return text
        except Exception as e:
            logger.error("Text extraction failed for %s: %s", file_path, e)
            raise

    elif file_type == "docx":
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            # .docx files are ZIP archives containing XML
            with zipfile.ZipFile(file_path, "r") as docx:
                with docx.open("word/document.xml") as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

            # Extract all text from XML paragraph nodes
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = root.findall(".//w:p", namespace)
            text_parts = []
            for para in paragraphs:
                texts = para.findall(".//w:t", namespace)
                para_text = "".join(t.text or "" for t in texts)
                if para_text.strip():
                    text_parts.append(para_text)

            text = "\n".join(text_parts)
            logger.info("Extracted %d chars from docx: %s", len(text), file_path)
            return text
        except Exception as e:
            logger.error("DOCX extraction failed for %s: %s", file_path, e)
            raise

    else:
        raise ValueError(f"Unsupported file type: {file_type}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    source: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    """
    Split text into overlapping word-based chunks.
    Returns list of {text, source, chunk_id}.
    """
    words = text.split()
    chunks = []
    start = 0
    chunk_id = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text_str = " ".join(words[start:end])
        chunks.append({
            "text": chunk_text_str,
            "source": source,
            "chunk_id": chunk_id,
        })
        chunk_id += 1
        if end == len(words):
            break
        start += chunk_size - overlap   # step forward with overlap

    logger.info("Created %d chunks from %s", len(chunks), source)
    return chunks


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def build_index(new_chunks: list[dict]) -> None:
    """Embed chunks and add them to the FAISS index."""
    global _index, _chunks

    ensure_index_loaded()

    if not new_chunks:
        logger.warning("build_index called with empty chunk list.")
        return

    model = _get_model()
    texts = [c["text"] for c in new_chunks]

    logger.info("Embedding %d chunks...", len(texts))
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    _index.add(embeddings)
    _chunks.extend(new_chunks)
    _save_index()
    logger.info("Indexed %d new chunks. Total: %d", len(new_chunks), len(_chunks))


def remove_file_from_index(source_filename: str) -> int:
    """
    Remove all chunks belonging to a specific source file.
    FAISS FlatL2 does not support deletion, so we rebuild the index.
    Returns number of chunks removed.
    """
    global _index, _chunks

    ensure_index_loaded()

    original_count = len(_chunks)
    remaining = [c for c in _chunks if c["source"] != source_filename]
    removed = original_count - len(remaining)

    if removed == 0:
        logger.info("No chunks found for source: %s", source_filename)
        return 0

    logger.info("Rebuilding index after removing %d chunks for: %s", removed, source_filename)

    # Rebuild from scratch with remaining chunks
    _index = faiss.IndexFlatL2(384)
    _chunks = []

    if remaining:
        model = _get_model()
        texts = [c["text"] for c in remaining]
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        embeddings = embeddings.astype(np.float32)
        _index.add(embeddings)
        _chunks = remaining

    _save_index()
    logger.info("Index rebuilt. Remaining chunks: %d", len(_chunks))
    return removed


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """
    Retrieve top_k most relevant chunks for a query.
    Returns list of {text, source, chunk_id, score}.
    """
    ensure_index_loaded()

    if len(_chunks) == 0:
        logger.info("FAISS index is empty — no chunks to retrieve.")
        return []

    model = _get_model()
    query_embedding = model.encode([query], convert_to_numpy=True).astype(np.float32)

    actual_k = min(top_k, len(_chunks))
    distances, indices = _index.search(query_embedding, actual_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        chunk = _chunks[idx].copy()
        chunk["score"] = float(dist)
        results.append(chunk)

    logger.info("Retrieved %d chunks for query (top %d requested)", len(results), top_k)
    return results


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_index_stats() -> dict:
    """Return number of indexed chunks and unique source files."""
    ensure_index_loaded()
    sources = list({c["source"] for c in _chunks})
    return {
        "total_chunks": len(_chunks),
        "indexed_files": sources,
        "index_exists": _index is not None,
    }