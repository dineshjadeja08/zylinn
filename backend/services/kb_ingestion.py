"""
Knowledge Base Ingestion Service
Handles website crawling, PDF extraction, and FAQ ingestion.
Chunks text and generates OpenAI embeddings stored in PgVector.

Supports three source types:
  - url:  Crawl a webpage (or limited sitemap) with Playwright
  - pdf:  Extract text from a PDF file (pypdf)
  - faq:  Accept structured FAQ JSON/YAML directly

Embedding: OpenAI text-embedding-3-small (1536 dimensions)
Storage:   PgVector (knowledge_base_chunks table)
"""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

# Chunk configuration
CHUNK_SIZE = 400        # tokens (approximate — using char/4 heuristic)
CHUNK_OVERLAP = 80
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Uses sentence boundaries where possible to avoid cutting mid-sentence.
    """
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Split on sentence boundaries first
    sentences = re.split(r"(?<=[.!?।])\s+", text)

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    char_limit = chunk_size * 4  # ~4 chars per token

    for sentence in sentences:
        sentence_len = len(sentence)
        if current_len + sentence_len > char_limit and current:
            chunks.append(" ".join(current))
            # Overlap: keep last N chars worth of sentences
            overlap_chars = overlap * 4
            overlap_sentences: list[str] = []
            ol = 0
            for s in reversed(current):
                if ol + len(s) > overlap_chars:
                    break
                overlap_sentences.insert(0, s)
                ol += len(s)
            current = overlap_sentences
            current_len = ol

        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if len(c.strip()) > 20]


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

async def generate_embeddings(texts: list[str], api_key: Optional[str] = None) -> list[list[float]]:
    """
    Generate OpenAI embeddings for a list of texts.

    Args:
        texts:   List of text chunks to embed.
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).

    Returns:
        List of embedding vectors (one per text).
    """
    import openai

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    client = openai.AsyncOpenAI(api_key=api_key)

    # Batch in groups of 100 (OpenAI limit per request)
    embeddings: list[list[float]] = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            input=batch,
            model=EMBEDDING_MODEL,
        )
        embeddings.extend([e.embedding for e in response.data])
        logger.debug("embeddings_batch_done", batch=i // batch_size + 1, count=len(batch))

    return embeddings


# ---------------------------------------------------------------------------
# Source extractors
# ---------------------------------------------------------------------------

async def extract_from_url(url: str, max_pages: int = 5) -> str:
    """
    Extract visible text from a URL using Playwright.

    Follows internal links up to max_pages for simple crawling.
    JavaScript-rendered pages are supported.

    Args:
        url:       Starting URL to crawl.
        max_pages: Max pages to crawl from the same domain.

    Returns:
        Concatenated plain text from all crawled pages.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("playwright not installed. Run: pip install playwright && playwright install chromium")

    from urllib.parse import urlparse, urljoin

    base_domain = urlparse(url).netloc
    visited: set[str] = set()
    queue = [url]
    all_text: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        while queue and len(visited) < max_pages:
            current_url = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                await page.goto(current_url, wait_until="networkidle", timeout=15000)

                # Extract main content (avoid nav/footer noise)
                text = await page.evaluate("""() => {
                    const remove = ['nav', 'footer', 'header', 'script', 'style', 'aside'];
                    remove.forEach(tag => document.querySelectorAll(tag).forEach(el => el.remove()));
                    return document.body?.innerText || '';
                }""")

                if text:
                    all_text.append(f"[Source: {current_url}]\n{text}")
                    logger.info("url_page_extracted", url=current_url, chars=len(text))

                # Find internal links for further crawling
                if len(visited) < max_pages:
                    links = await page.evaluate("""() =>
                        Array.from(document.querySelectorAll('a[href]'))
                            .map(a => a.href)
                            .filter(h => h.startsWith('http'))
                    """)
                    for link in links:
                        if urlparse(link).netloc == base_domain and link not in visited:
                            queue.append(link)

            except Exception as exc:
                logger.warning("url_page_failed", url=current_url, error=str(exc))

        await browser.close()

    return "\n\n".join(all_text)


async def extract_from_pdf(file_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Extract text from a PDF file using pypdf.

    Args:
        file_bytes: Raw PDF bytes.
        filename:   Original filename (for logging).

    Returns:
        Extracted plain text.
    """
    try:
        from pypdf import PdfReader
        import io
    except ImportError:
        raise RuntimeError("pypdf not installed. Run: pip install pypdf>=4.0.0")

    reader = PdfReader(io.BytesIO(file_bytes))
    pages_text: list[str] = []

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text and text.strip():
                pages_text.append(text)
        except Exception as exc:
            logger.warning("pdf_page_extract_failed", page=i, error=str(exc))

    full_text = "\n\n".join(pages_text)
    logger.info("pdf_extracted", filename=filename, pages=len(reader.pages), chars=len(full_text))
    return full_text


def extract_from_faq(faq_data: list[dict[str, str]]) -> str:
    """
    Convert structured FAQ data to text for chunking.

    Expected format: [{"question": "...", "answer": "..."}, ...]

    Args:
        faq_data: List of Q&A dicts.

    Returns:
        Formatted text ready for chunking.
    """
    lines: list[str] = []
    for item in faq_data:
        q = item.get("question", "").strip()
        a = item.get("answer", "").strip()
        if q and a:
            lines.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

async def ingest_document(
    doc_id: str,
    customer_id: str,
    source_type: str,
    db_session: Any,
    source_url: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    file_name: Optional[str] = None,
    faq_data: Optional[list[dict]] = None,
    agent_config_id: Optional[int] = None,
) -> dict:
    """
    Full ingestion pipeline: extract → chunk → embed → store.

    Updates doc status in DB at each stage.

    Args:
        doc_id:          UUID of the knowledge_base_docs row.
        customer_id:     Tenant UUID.
        source_type:     'url', 'pdf', or 'faq'.
        db_session:      SQLAlchemy session.
        source_url:      URL to crawl (source_type='url').
        file_bytes:      PDF bytes (source_type='pdf').
        file_name:       Original PDF filename.
        faq_data:        FAQ list (source_type='faq').
        agent_config_id: Optional agent config to scope this KB.

    Returns:
        Dict with status, chunk_count, and any error.
    """
    from models import DatabaseManager  # late import to avoid circular

    log = logger.bind(doc_id=doc_id, customer_id=customer_id, source_type=source_type)
    log.info("ingestion_started")

    # Mark as processing
    _update_doc_status(db_session, doc_id, "processing")

    try:
        # 1. Extract raw text
        log.info("extraction_started")
        if source_type == "url":
            if not source_url:
                raise ValueError("source_url required for url ingestion")
            raw_text = await extract_from_url(source_url)
        elif source_type == "pdf":
            if not file_bytes:
                raise ValueError("file_bytes required for pdf ingestion")
            raw_text = await extract_from_pdf(file_bytes, file_name or "document.pdf")
        elif source_type == "faq":
            if not faq_data:
                raise ValueError("faq_data required for faq ingestion")
            raw_text = extract_from_faq(faq_data)
        else:
            raise ValueError(f"Unknown source_type: {source_type}")

        if not raw_text.strip():
            raise ValueError("No text extracted from source")

        log.info("extraction_done", chars=len(raw_text))

        # 2. Save raw text to doc record
        _update_doc_raw_text(db_session, doc_id, raw_text)

        # 3. Chunk
        chunks = chunk_text(raw_text)
        log.info("chunking_done", chunk_count=len(chunks))

        if not chunks:
            raise ValueError("No chunks generated from extracted text")

        # 4. Generate embeddings
        log.info("embedding_started", chunk_count=len(chunks))
        vectors = await generate_embeddings(chunks)
        log.info("embedding_done")

        # 5. Store chunks in DB
        _store_chunks(db_session, doc_id, customer_id, chunks, vectors)
        log.info("chunks_stored", count=len(chunks))

        # 6. Mark as ready
        _update_doc_status(db_session, doc_id, "ready")

        return {"status": "ready", "chunk_count": len(chunks)}

    except Exception as exc:
        log.error("ingestion_failed", error=str(exc))
        _update_doc_status(db_session, doc_id, "error", error_message=str(exc))
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# RAG retrieval
# ---------------------------------------------------------------------------

async def search_knowledge_base(
    query: str,
    customer_id: str,
    db_session: Any,
    top_k: int = 3,
    agent_config_id: Optional[int] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    """
    Find the most relevant knowledge base chunks for a query.

    Uses cosine similarity search via PgVector.

    Args:
        query:          The caller's question or user turn text.
        customer_id:    Tenant UUID to scope search.
        db_session:     SQLAlchemy session.
        top_k:          Number of chunks to return.
        agent_config_id: Scope search to a specific agent config's KB.
        api_key:        OpenAI API key for embedding the query.

    Returns:
        List of {text, similarity, doc_id} dicts.
    """
    # Embed the query
    [query_vector] = await generate_embeddings([query], api_key=api_key)

    # PgVector cosine similarity query
    vector_str = f"[{','.join(str(v) for v in query_vector)}]"

    sql = """
        SELECT
            kbc.chunk_text,
            1 - (kbc.embedding <=> :query_vec::vector) AS similarity,
            kbc.doc_id
        FROM knowledge_base_chunks kbc
        JOIN knowledge_base_docs kbd ON kbc.doc_id = kbd.doc_id
        WHERE kbd.customer_id = :customer_id
          AND kbd.status = 'ready'
          {agent_filter}
        ORDER BY kbc.embedding <=> :query_vec::vector
        LIMIT :top_k
    """.format(
        agent_filter=(
            "AND kbd.agent_config_id = :agent_config_id"
            if agent_config_id else ""
        )
    )

    from sqlalchemy import text

    params: dict = {
        "query_vec": vector_str,
        "customer_id": str(customer_id),
        "top_k": top_k,
    }
    if agent_config_id:
        params["agent_config_id"] = agent_config_id

    rows = db_session.execute(text(sql), params).fetchall()

    results = [
        {"text": row[0], "similarity": float(row[1]), "doc_id": str(row[2])}
        for row in rows
        if float(row[1]) > 0.6  # Minimum relevance threshold
    ]

    logger.info(
        "kb_search_complete",
        query_preview=query[:50],
        results=len(results),
        customer_id=str(customer_id),
    )

    return results


def format_rag_context(results: list[dict]) -> str:
    """
    Format RAG results for injection into the LLM system prompt.

    Args:
        results: Output from search_knowledge_base().

    Returns:
        Formatted context string to prepend to the system prompt.
    """
    if not results:
        return ""

    lines = ["## Relevant information from our knowledge base:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['text'].strip()}")

    lines.append(
        "\nUse the above information to answer the caller's question. "
        "If the information doesn't cover the question, say you'll connect them to staff."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DB helpers (thin wrappers — actual models defined in models.py)
# ---------------------------------------------------------------------------

def _update_doc_status(
    session: Any, doc_id: str, status: str, error_message: Optional[str] = None
) -> None:
    from sqlalchemy import text

    params: dict = {"status": status, "doc_id": str(doc_id)}
    sql = "UPDATE knowledge_base_docs SET status = :status"
    if error_message:
        sql += ", error_message = :error_message"
        params["error_message"] = error_message[:1000]
    sql += " WHERE doc_id = :doc_id::uuid"
    session.execute(text(sql), params)
    session.commit()


def _update_doc_raw_text(session: Any, doc_id: str, raw_text: str) -> None:
    from sqlalchemy import text

    session.execute(
        text("UPDATE knowledge_base_docs SET raw_text = :raw_text WHERE doc_id = :doc_id::uuid"),
        {"raw_text": raw_text, "doc_id": str(doc_id)},
    )
    session.commit()


def _store_chunks(
    session: Any,
    doc_id: str,
    customer_id: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> None:
    from sqlalchemy import text

    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        vec_str = f"[{','.join(str(v) for v in vec)}]"
        session.execute(
            text("""
                INSERT INTO knowledge_base_chunks
                    (doc_id, customer_id, chunk_text, embedding, chunk_index)
                VALUES
                    (:doc_id::uuid, :customer_id::uuid, :chunk_text, :embedding::vector, :chunk_index)
            """),
            {
                "doc_id": str(doc_id),
                "customer_id": str(customer_id),
                "chunk_text": chunk,
                "embedding": vec_str,
                "chunk_index": i,
            },
        )
    session.commit()
