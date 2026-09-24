"""
Appointments Router
API for fetching and managing appointments for the tenant.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/appointments", tags=["appointments"])

@router.get("/")
async def list_appointments(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch all appointments for the tenant."""
    rows = db.execute(
        text("""
            SELECT appointment_uuid, customer_name, customer_phone, 
                   appointment_date, appointment_time, service_type, 
                   status, notes, created_at
            FROM appointments
            WHERE customer_id = :customer_id
            ORDER BY appointment_date DESC, appointment_time DESC
            LIMIT 100
        """),
        {"customer_id": str(user.customer_id)}
    ).fetchall()
    
    return [
        {
            "appointment_uuid": str(r[0]) if r[0] else None,
            "customer_name": r[1],
            "customer_phone": r[2],
            "appointment_date": r[3].isoformat() if r[3] else None,
            "appointment_time": r[4].isoformat() if r[4] else None,
            "service_type": r[5],
            "status": r[6],
            "notes": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]
