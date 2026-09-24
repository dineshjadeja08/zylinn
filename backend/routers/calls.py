"""
Calls Router
API for fetching call history for the tenant.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/calls", tags=["calls"])

@router.get("/")
async def list_calls(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch all calls for the tenant."""
    rows = db.execute(
        text("""
            SELECT call_id, caller_number, called_number, call_type, 
                   duration_seconds, status, summary, call_cost_usd, created_at
            FROM call_records
            WHERE customer_id = :customer_id
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {"customer_id": str(user.customer_id)}
    ).fetchall()
    
    return [
        {
            "call_id": r[0],
            "caller_number": r[1],
            "called_number": r[2],
            "call_type": r[3],
            "duration_seconds": r[4],
            "status": r[5],
            "summary": r[6],
            "call_cost_usd": float(r[7]) if r[7] else 0.0,
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]
