"""
Agent Configuration Router
CRUD endpoints for per-tenant AI receptionist configurations.
"""
import json
from typing import List, Optional
from uuid import UUID
import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models import AgentConfig, Customer
from auth import get_current_user
from database import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agent-configs"])


class AgentConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    persona_description: Optional[str] = None
    languages: List[str] = Field(default=["en"])
    voice_id: Optional[str] = None
    tts_provider: str = Field(default="elevenlabs")
    stt_provider: str = Field(default="assemblyai")
    greeting_message: Optional[str] = None
    system_prompt_override: Optional[str] = None
    working_hours: Optional[dict] = None
    tools_enabled: List[str] = Field(default=["appointment"])


class AgentConfigUpdate(BaseModel):
    name: Optional[str] = None
    persona_description: Optional[str] = None
    languages: Optional[List[str]] = None
    voice_id: Optional[str] = None
    tts_provider: Optional[str] = None
    stt_provider: Optional[str] = None
    greeting_message: Optional[str] = None
    system_prompt_override: Optional[str] = None
    working_hours: Optional[dict] = None
    tools_enabled: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AgentConfigResponse(BaseModel):
    config_id: UUID
    customer_id: UUID
    name: str
    persona_description: Optional[str]
    languages: List[str]
    voice_id: Optional[str]
    tts_provider: str
    stt_provider: str
    greeting_message: Optional[str]
    system_prompt_override: Optional[str]
    working_hours: Optional[dict]
    tools_enabled: List[str]
    is_active: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_json(cls, obj: AgentConfig):
        """Parse working_hours JSON string back to dict"""
        data = {
            "config_id": obj.config_id,
            "customer_id": obj.customer_id,
            "name": obj.name,
            "persona_description": obj.persona_description,
            "languages": obj.languages or ["en"],
            "voice_id": obj.voice_id,
            "tts_provider": obj.tts_provider,
            "stt_provider": obj.stt_provider,
            "greeting_message": obj.greeting_message,
            "system_prompt_override": obj.system_prompt_override,
            "working_hours": json.loads(obj.working_hours) if obj.working_hours else None,
            "tools_enabled": obj.tools_enabled or [],
            "is_active": obj.is_active,
        }
        return cls(**data)


@router.get("/", response_model=List[AgentConfigResponse])
async def list_agent_configs(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all agent configurations for the current tenant."""
    configs = db.query(AgentConfig).filter(
        AgentConfig.customer_id == user.customer_id
    ).order_by(AgentConfig.created_at.desc()).all()
    return [AgentConfigResponse.from_orm_with_json(c) for c in configs]


@router.post("/", response_model=AgentConfigResponse, status_code=201)
async def create_agent_config(
    request: AgentConfigCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new agent configuration for the current tenant."""
    config = AgentConfig(
        customer_id=user.customer_id,
        name=request.name,
        persona_description=request.persona_description,
        languages=request.languages,
        voice_id=request.voice_id,
        tts_provider=request.tts_provider,
        stt_provider=request.stt_provider,
        greeting_message=request.greeting_message,
        system_prompt_override=request.system_prompt_override,
        working_hours=json.dumps(request.working_hours) if request.working_hours else None,
        tools_enabled=request.tools_enabled,
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    logger.info("agent_config_created", config_id=str(config.config_id), customer_id=str(user.customer_id))
    return AgentConfigResponse.from_orm_with_json(config)


@router.get("/{config_id}", response_model=AgentConfigResponse)
async def get_agent_config(
    config_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific agent configuration."""
    config = db.query(AgentConfig).filter(
        AgentConfig.config_id == config_id,
        AgentConfig.customer_id == user.customer_id
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    return AgentConfigResponse.from_orm_with_json(config)


@router.patch("/{config_id}", response_model=AgentConfigResponse)
async def update_agent_config(
    config_id: UUID,
    request: AgentConfigUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an agent configuration (partial update)."""
    config = db.query(AgentConfig).filter(
        AgentConfig.config_id == config_id,
        AgentConfig.customer_id == user.customer_id
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "working_hours" and value is not None:
            setattr(config, field, json.dumps(value))
        else:
            setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    logger.info("agent_config_updated", config_id=str(config_id))
    return AgentConfigResponse.from_orm_with_json(config)


@router.delete("/{config_id}", status_code=204)
async def delete_agent_config(
    config_id: UUID,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent configuration."""
    config = db.query(AgentConfig).filter(
        AgentConfig.config_id == config_id,
        AgentConfig.customer_id == user.customer_id
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    db.delete(config)
    db.commit()
    logger.info("agent_config_deleted", config_id=str(config_id))
