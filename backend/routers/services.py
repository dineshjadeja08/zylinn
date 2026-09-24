"""
Service Catalog Router
CRUD for per-tenant service catalog (used by lookup_service agent tool).
"""
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import ServiceCatalog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/services", tags=["service-catalog"])


class ServiceCreate(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    price_inr: Optional[float] = None
    duration_minutes: Optional[int] = None


class ServiceUpdate(BaseModel):
    service_name: Optional[str] = None
    description: Optional[str] = None
    price_inr: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None


class ServiceResponse(BaseModel):
    id: int
    customer_id: UUID
    service_name: str
    description: Optional[str]
    price_inr: Optional[float]
    duration_minutes: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ServiceResponse])
async def list_services(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(ServiceCatalog).filter(
        ServiceCatalog.customer_id == user.customer_id,
        ServiceCatalog.is_active == True
    ).order_by(ServiceCatalog.service_name).all()


@router.post("/", response_model=ServiceResponse, status_code=201)
async def create_service(
    request: ServiceCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    svc = ServiceCatalog(
        customer_id=user.customer_id,
        service_name=request.service_name,
        description=request.description,
        price_inr=request.price_inr,
        duration_minutes=request.duration_minutes,
        is_active=True,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    logger.info("service_created", id=svc.id, name=svc.service_name)
    return svc


@router.patch("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    request: ServiceUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    svc = db.query(ServiceCatalog).filter(
        ServiceCatalog.id == service_id,
        ServiceCatalog.customer_id == user.customer_id
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    for k, v in request.model_dump(exclude_unset=True).items():
        setattr(svc, k, v)
    db.commit()
    db.refresh(svc)
    return svc


@router.delete("/{service_id}", status_code=204)
async def delete_service(
    service_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    svc = db.query(ServiceCatalog).filter(
        ServiceCatalog.id == service_id,
        ServiceCatalog.customer_id == user.customer_id
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    svc.is_active = False
    db.commit()


@router.get("/lookup")
async def lookup_service_api(
    query: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search service catalog by name (for testing the lookup_service agent tool).
    Used internally by the agent via DB lookup.
    """
    services = db.query(ServiceCatalog).filter(
        ServiceCatalog.customer_id == user.customer_id,
        ServiceCatalog.is_active == True,
        ServiceCatalog.service_name.ilike(f"%{query}%")
    ).all()
    return [{"service_name": s.service_name, "price_inr": float(s.price_inr) if s.price_inr else None,
             "duration_minutes": s.duration_minutes, "description": s.description} for s in services]
