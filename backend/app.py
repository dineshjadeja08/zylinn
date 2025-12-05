"""
Zylin Backend API
FastAPI service for webhooks, transcript retrieval, and WebSocket support.
"""
import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import structlog
from dotenv import load_dotenv

from models import (
    DatabaseManager,
    CallRecord,
    TranscriptChunk,
    AgentReply,
    Appointment,
    get_call_record,
    get_call_transcripts,
    get_call_replies,
    get_appointments_for_call,
    get_all_appointments
)

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Zylin Voice Agent API",
    description="Backend API for Zylin AI Voice Agent",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db_manager = DatabaseManager()
db_manager.create_tables()


# Dependency for database sessions
def get_db():
    """Dependency to get database session"""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


# Pydantic models for API
class CallRecordResponse(BaseModel):
    """Call record response model"""
    call_id: str
    room_name: str
    agent_identity: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    status: str
    participant_sid: Optional[str]
    participant_identity: Optional[str]
    
    class Config:
        from_attributes = True


class TranscriptChunkResponse(BaseModel):
    """Transcript chunk response model"""
    id: int
    call_id: str
    text: str
    is_final: bool
    confidence: Optional[float]
    timestamp: datetime
    sequence_number: int
    speaker: Optional[str]
    
    class Config:
        from_attributes = True


class AgentReplyResponse(BaseModel):
    """Agent reply response model"""
    id: int
    call_id: str
    prompt: str
    response_text: str
    timestamp: datetime
    sequence_number: int
    model: Optional[str]
    tokens_used: Optional[int]
    generation_time_ms: Optional[float]
    
    class Config:
        from_attributes = True


class AppointmentResponse(BaseModel):
    """Appointment response model"""
    id: int
    call_id: str
    customer_name: str
    customer_phone: Optional[str]
    customer_email: Optional[str]
    appointment_date: str
    appointment_time: str
    service_type: Optional[str]
    notes: Optional[str]
    status: str
    booked_at: datetime
    confirmed_by_agent: bool
    
    class Config:
        from_attributes = True


class CallDetailResponse(BaseModel):
    """Complete call details with transcripts and replies"""
    call: CallRecordResponse
    transcripts: List[TranscriptChunkResponse]
    replies: List[AgentReplyResponse]


class WebhookPayload(BaseModel):
    """Generic webhook payload"""
    event_type: str
    call_id: str
    data: dict


# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Zylin Voice Agent API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test database connection
        session = db_manager.get_session()
        session.execute("SELECT 1")
        session.close()
        db_status = "healthy"
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/calls", response_model=List[CallRecordResponse])
async def list_calls(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List call records.
    
    Args:
        status: Filter by status (active, completed, failed)
        limit: Maximum number of records to return
    """
    query = db.query(CallRecord)
    
    if status:
        query = query.filter(CallRecord.status == status)
    
    calls = query.order_by(CallRecord.created_at.desc()).limit(limit).all()
    
    return calls


@app.get("/calls/{call_id}", response_model=CallDetailResponse)
async def get_call_details(call_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific call.
    
    Args:
        call_id: Unique call identifier
    """
    call = get_call_record(db, call_id)
    
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    
    transcripts = get_call_transcripts(db, call_id)
    replies = get_call_replies(db, call_id)
    
    return CallDetailResponse(
        call=CallRecordResponse.from_orm(call),
        transcripts=[TranscriptChunkResponse.from_orm(t) for t in transcripts],
        replies=[AgentReplyResponse.from_orm(r) for r in replies]
    )


@app.get("/calls/{call_id}/transcripts", response_model=List[TranscriptChunkResponse])
async def get_call_transcripts_endpoint(
    call_id: str,
    final_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get transcripts for a specific call.
    
    Args:
        call_id: Unique call identifier
        final_only: If True, return only final transcripts
    """
    call = get_call_record(db, call_id)
    
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    
    transcripts = get_call_transcripts(db, call_id, final_only=final_only)
    
    return [TranscriptChunkResponse.from_orm(t) for t in transcripts]


@app.get("/calls/{call_id}/replies", response_model=List[AgentReplyResponse])
async def get_call_replies_endpoint(call_id: str, db: Session = Depends(get_db)):
    """
    Get agent replies for a specific call.
    
    Args:
        call_id: Unique call identifier
    """
    call = get_call_record(db, call_id)
    
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    
    replies = get_call_replies(db, call_id)
    
    return [AgentReplyResponse.from_orm(r) for r in replies]


@app.get("/appointments", response_model=List[AppointmentResponse])
async def list_appointments(
    status: Optional[str] = None,
    limit: Optional[int] = 100,
    db: Session = Depends(get_db)
):
    """
    List all appointments.
    
    Args:
        status: Filter by status (confirmed, cancelled, completed)
        limit: Maximum number of appointments to return
    """
    appointments = get_all_appointments(db, status=status, limit=limit)
    
    return [AppointmentResponse.from_orm(a) for a in appointments]


@app.get("/calls/{call_id}/appointments", response_model=List[AppointmentResponse])
async def get_call_appointments_endpoint(call_id: str, db: Session = Depends(get_db)):
    """
    Get appointments for a specific call.
    
    Args:
        call_id: Unique call identifier
    """
    call = get_call_record(db, call_id)
    
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    
    appointments = get_appointments_for_call(db, call_id)
    
    return [AppointmentResponse.from_orm(a) for a in appointments]


@app.post("/webhook")
async def receive_webhook(payload: WebhookPayload, db: Session = Depends(get_db)):
    """
    Receive webhooks from external services.
    
    Can be used for LiveKit events, telephony events, etc.
    """
    logger.info(
        "webhook_received",
        event_type=payload.event_type,
        call_id=payload.call_id
    )
    
    # Process webhook based on event type
    # Add custom logic here as needed
    
    return {"status": "received", "event_type": payload.event_type}


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for live transcripts"""
    
    def __init__(self):
        self.active_connections: dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, call_id: str):
        """Connect a WebSocket for a specific call"""
        await websocket.accept()
        
        if call_id not in self.active_connections:
            self.active_connections[call_id] = []
        
        self.active_connections[call_id].append(websocket)
        logger.info("websocket_connected", call_id=call_id)
    
    def disconnect(self, websocket: WebSocket, call_id: str):
        """Disconnect a WebSocket"""
        if call_id in self.active_connections:
            self.active_connections[call_id].remove(websocket)
            
            if not self.active_connections[call_id]:
                del self.active_connections[call_id]
        
        logger.info("websocket_disconnected", call_id=call_id)
    
    async def broadcast_to_call(self, call_id: str, message: dict):
        """Broadcast message to all connections for a call"""
        if call_id in self.active_connections:
            dead_connections = []
            
            for connection in self.active_connections[call_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for conn in dead_connections:
                self.disconnect(conn, call_id)


manager = ConnectionManager()


@app.websocket("/ws/calls/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint for live transcript streaming.
    
    Clients can connect to receive real-time updates for a specific call.
    """
    await manager.connect(websocket, call_id)
    
    try:
        # Send initial call data
        db = db_manager.get_session()
        try:
            call = get_call_record(db, call_id)
            
            if call:
                await websocket.send_json({
                    "type": "call_info",
                    "data": {
                        "call_id": call.call_id,
                        "status": call.status,
                        "start_time": call.start_time.isoformat()
                    }
                })
        finally:
            db.close()
        
        # Keep connection alive and wait for client messages
        while True:
            data = await websocket.receive_text()
            
            # Echo back (or handle commands)
            await websocket.send_json({
                "type": "echo",
                "message": f"Received: {data}"
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, call_id)
    except Exception as e:
        logger.error("websocket_error", error=str(e), call_id=call_id)
        manager.disconnect(websocket, call_id)


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("backend_starting")
    db_manager.create_tables()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("backend_shutting_down")
    db_manager.close()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("BACKEND_PORT", "8000"))
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
