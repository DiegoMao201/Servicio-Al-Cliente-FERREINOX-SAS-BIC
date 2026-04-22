from __future__ import annotations

import os
import time
from threading import Lock
from pathlib import Path
from typing import Optional

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIMENSIONS = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "1536"))
EMBEDDING_MIN_INTERVAL_SECONDS = float(os.getenv("GEMINI_EMBEDDING_MIN_INTERVAL_SECONDS", "0.6"))
EMBEDDING_MAX_RETRIES = int(os.getenv("GEMINI_EMBEDDING_MAX_RETRIES", "6"))

_EMBED_CALL_LOCK = Lock()
_LAST_EMBED_CALL_AT = 0.0


def _read_streamlit_secret_value(*keys: str) -> str | None:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists() or not keys:
        return None
    try:
        raw_text = secrets_path.read_text(encoding="utf-8")
    except Exception:
        return None

    current_value: Optional[str] = None
    for key in keys[::-1]:
        marker = f'{key} = "'
        if marker in raw_text:
            current_value = raw_text.split(marker, 1)[1].split('"', 1)[0].strip()
            break
    return current_value


def get_gemini_api_key() -> str | None:
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or _read_streamlit_secret_value("gemini", "api_key")
        or _read_streamlit_secret_value("GOOGLE_API_KEY")
    )


def _extract_embedding_values(result) -> list[float]:
    embeddings = getattr(result, "embeddings", None) or []
    if not embeddings:
        raise ValueError("Gemini no devolvio embeddings")
    first = embeddings[0]
    values = getattr(first, "values", None)
    if values is None and isinstance(first, dict):
        values = first.get("values")
    if values is None:
        raise ValueError("No se encontraron valores del embedding Gemini")
    return list(values)


def _sleep_for_rate_limit_floor():
    global _LAST_EMBED_CALL_AT
    if EMBEDDING_MIN_INTERVAL_SECONDS <= 0:
        return
    with _EMBED_CALL_LOCK:
        now = time.monotonic()
        wait_time = EMBEDDING_MIN_INTERVAL_SECONDS - (now - _LAST_EMBED_CALL_AT)
        if wait_time > 0:
            time.sleep(wait_time)
        _LAST_EMBED_CALL_AT = time.monotonic()


def _is_retryable_gemini_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True
    message = str(exc).lower()
    retryable_markers = [
        "resource_exhausted",
        "rate limit",
        "quota",
        "too many requests",
        "temporarily unavailable",
        "service unavailable",
        "deadline exceeded",
    ]
    return any(marker in message for marker in retryable_markers)


@retry(
    retry=retry_if_exception(_is_retryable_gemini_error),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(EMBEDDING_MAX_RETRIES),
    reraise=True,
)
def _embed_content_with_retry(*, model: str, contents, config):
    _sleep_for_rate_limit_floor()
    client, _ = get_gemini_client()
    return client.models.embed_content(
        model=model,
        contents=contents,
        config=config,
    )


def get_gemini_client():
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError("No se encontró GEMINI_API_KEY / GOOGLE_API_KEY")
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        raise RuntimeError("Falta la dependencia google-genai para usar gemini-embedding-2") from exc
    return genai.Client(api_key=api_key), types


def prepare_retrieval_query(text: str) -> str:
    return f"task: search result | query: {(text or '').strip()}"


def prepare_retrieval_document(text: str, title: str | None = None) -> str:
    clean_title = (title or "none").strip() or "none"
    clean_text = (text or "").strip()
    return f"title: {clean_title} | text: {clean_text}"


def generate_query_embedding(query_text: str) -> list[float]:
    _, types = get_gemini_client()
    result = _embed_content_with_retry(
        model=EMBEDDING_MODEL,
        contents=prepare_retrieval_query(query_text),
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    return _extract_embedding_values(result)


def generate_document_embedding(document_text: str, *, title: str | None = None) -> list[float]:
    _, types = get_gemini_client()
    result = _embed_content_with_retry(
        model=EMBEDDING_MODEL,
        contents=prepare_retrieval_document(document_text, title=title),
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    return _extract_embedding_values(result)


def generate_document_embeddings(documents: list[dict], *, sleep_seconds: float = 0.1) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for index, document in enumerate(documents):
        embeddings.append(
            generate_document_embedding(
                document.get("text") or "",
                title=document.get("title"),
            )
        )
        if sleep_seconds and index < len(documents) - 1:
            time.sleep(sleep_seconds)
    return embeddings


def generate_multimodal_product_embedding(
    *,
    title: str,
    summary_text: str,
    pdf_bytes: bytes | None = None,
    image_bytes: bytes | None = None,
    image_mime_type: str = "image/png",
) -> list[float]:
    _, types = get_gemini_client()
    contents = [prepare_retrieval_document(summary_text, title=title)]
    if pdf_bytes:
        contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type))

    result = _embed_content_with_retry(
        model=EMBEDDING_MODEL,
        contents=contents,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    return _extract_embedding_values(result)
