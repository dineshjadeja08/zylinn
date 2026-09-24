"""
Knowledge Base API Router
CRUD + ingestion endpoints for per-tenant knowledge base documents.

Endpoints:
  POST   /knowledge/ingest/url       — Crawl a website URL
  POST   /knowledge/ingest/pdf       — Upload and ingest a PDF
  POST   /knowledge/ingest/faq       — Submit FAQ JSON
  GET    /knowledge/docs             — List all docs for tenant
  DELETE /knowledge/docs/{doc_id}    — Delete a doc and its chunks
  POST   /knowledge/search           — Semantic search (for testing/debug)
"""
import uuid
from typing import Any, List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services.kb_ingestion import ingest_document, search_knowledge_base

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge-base"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class URLIngestRequest(BaseModel):
    url: str
    max_pages: int = 5
    agent_config_id: Optional[int] = None


class FAQItem(BaseModel):
    question: str
    answer: str


class FAQIngestRequest(BaseModel):
    items: List[FAQItem]
    agent_config_id: Optional[int] = None


class KBDocResponse(BaseModel):
    doc_id: UUID
    customer_id: UUID
    source_type: str
    source_url: Optional[str]
    file_name: Optional[str]
    status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3
    agent_config_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Background ingestion task wrapper
# ---------------------------------------------------------------------------

async def _run_ingestion(
    doc_id: str,
    customer_id: str,
    source_type: str,
    db_session: Any,
    **kwargs,
) -> None:
    """Wrapper to run ingestion as a FastAPI BackgroundTask."""
    try:
        await ingest_document(
            doc_id=doc_id,
            customer_id=customer_id,
            source_type=source_type,
            db_session=db_session,
            **kwargs,
        )
    finally:
        db_session.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest/url", status_code=202)
async def ingest_url(
    request: URLIngestRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start async ingestion of a website URL.

    Returns immediately with doc_id. Poll GET /knowledge/docs to check status.
    """
    doc_id = str(uuid.uuid4())
    _create_doc_record(
        db,
        doc_id=doc_id,
        customer_id=str(user.customer_id),
        source_type="url",
        source_url=str(request.url),
        agent_config_id=request.agent_config_id,
    )

    # Get a new session for background task (FastAPI closes the request session)
    from database import db_manager
    bg_session = db_manager.get_session()

    background_tasks.add_task(
        _run_ingestion,
        doc_id=doc_id,
        customer_id=str(user.customer_id),
        source_type="url",
        db_session=bg_session,
        source_url=str(request.url),
        agent_config_id=request.agent_config_id,
    )

    logger.info("url_ingest_queued", doc_id=doc_id, url=str(request.url))
    return {"doc_id": doc_id, "status": "processing", "message": "Ingestion started in background."}


@router.post("/ingest/pdf", status_code=202)
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    agent_config_id: Optional[int] = Form(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF and start async ingestion.

    Accepts: application/pdf
    Max size: 20MB (enforce at nginx level)
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20MB
        raise HTTPException(status_code=413, detail="PDF too large. Maximum size is 20MB.")

    doc_id = str(uuid.uuid4())
    _create_doc_record(
        db,
        doc_id=doc_id,
        customer_id=str(user.customer_id),
        source_type="pdf",
        file_name=file.filename,
        agent_config_id=agent_config_id,
    )

    from database import db_manager
    bg_session = db_manager.get_session()

    background_tasks.add_task(
        _run_ingestion,
        doc_id=doc_id,
        customer_id=str(user.customer_id),
        source_type="pdf",
        db_session=bg_session,
        file_bytes=file_bytes,
        file_name=file.filename,
        agent_config_id=agent_config_id,
    )

    logger.info("pdf_ingest_queued", doc_id=doc_id, filename=file.filename)
    return {"doc_id": doc_id, "status": "processing", "message": "PDF ingestion started in background."}


@router.post("/ingest/faq", status_code=202)
async def ingest_faq(
    request: FAQIngestRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit structured FAQ items for ingestion."""
    faq_data = [item.model_dump() for item in request.items]
    if not faq_data:
        raise HTTPException(status_code=400, detail="At least one FAQ item required.")

    doc_id = str(uuid.uuid4())
    _create_doc_record(
        db,
        doc_id=doc_id,
        customer_id=str(user.customer_id),
        source_type="faq",
        agent_config_id=request.agent_config_id,
    )

    from database import db_manager
    bg_session = db_manager.get_session()

    background_tasks.add_task(
        _run_ingestion,
        doc_id=doc_id,
        customer_id=str(user.customer_id),
        source_type="faq",
        db_session=bg_session,
        faq_data=faq_data,
        agent_config_id=request.agent_config_id,
    )

    logger.info("faq_ingest_queued", doc_id=doc_id, item_count=len(faq_data))
    return {"doc_id": doc_id, "status": "processing", "message": "FAQ ingestion started."}


@router.get("/docs")
async def list_docs(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all knowledge base documents for the current tenant."""
    from sqlalchemy import text

    rows = db.execute(
        text("""
            SELECT doc_id, customer_id, source_type, source_url, file_name, status, error_message,
                   (SELECT COUNT(*) FROM knowledge_base_chunks WHERE doc_id = d.doc_id) AS chunk_count,
                   created_at
            FROM knowledge_base_docs d
            WHERE customer_id = :customer_id
            ORDER BY created_at DESC
        """),
        {"customer_id": str(user.customer_id)},
    ).fetchall()

    return [
        {
            "doc_id": str(r[0]),
            "customer_id": str(r[1]),
            "source_type": r[2],
            "source_url": r[3],
            "file_name": r[4],
            "status": r[5],
            "error_message": r[6],
            "chunk_count": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


@router.delete("/docs/{doc_id}", status_code=204)
async def delete_doc(
    doc_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document and all its chunks from the knowledge base."""
    from sqlalchemy import text

    # Verify ownership
    row = db.execute(
        text("SELECT customer_id FROM knowledge_base_docs WHERE doc_id = :doc_id::uuid"),
        {"doc_id": str(doc_id)},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    if str(row[0]) != str(user.customer_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    # Chunks are CASCADE deleted
    db.execute(
        text("DELETE FROM knowledge_base_docs WHERE doc_id = :doc_id::uuid"),
        {"doc_id": str(doc_id)},
    )
    db.commit()
    logger.info("kb_doc_deleted", doc_id=str(doc_id))


@router.post("/search")
async def semantic_search(
    request: SearchRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Debug endpoint: run a semantic search against the tenant's knowledge base.
    Useful for testing knowledge base quality before deploying to an agent.
    """
    results = await search_knowledge_base(
        query=request.query,
        customer_id=str(user.customer_id),
        db_session=db,
        top_k=request.top_k,
        agent_config_id=request.agent_config_id,
    )
    return {"query": request.query, "results": results}


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _create_doc_record(
    session: Session,
    doc_id: str,
    customer_id: str,
    source_type: str,
    source_url: Optional[str] = None,
    file_name: Optional[str] = None,
    agent_config_id: Optional[int] = None,
) -> None:
    """Insert a new knowledge_base_docs row (status=pending)."""
    from sqlalchemy import text

    session.execute(
        text("""
            INSERT INTO knowledge_base_docs
                (doc_id, customer_id, source_type, source_url, file_name, agent_config_id, status)
            VALUES
                (:doc_id::uuid, :customer_id::uuid, :source_type, :source_url, :file_name, :agent_config_id, 'pending')
        """),
        {
            "doc_id": doc_id,
            "customer_id": customer_id,
            "source_type": source_type,
            "source_url": source_url,
            "file_name": file_name,
            "agent_config_id": agent_config_id,
        },
    )
    session.commit()
