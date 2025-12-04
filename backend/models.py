"""
Database Models for Zylin Voice Agent
Defines SQLAlchemy models for call records, transcripts, and agent replies.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

Base = declarative_base()


class CallRecord(Base):
    """
    Represents a single call session.
    """
    __tablename__ = "call_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), unique=True, nullable=False, index=True)
    room_name = Column(String(200), nullable=False)
    agent_identity = Column(String(200), nullable=False)
    
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    participant_sid = Column(String(200), nullable=True)
    participant_identity = Column(String(200), nullable=True)
    
    status = Column(String(50), nullable=False, default="active")  # active, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Relationships
    transcripts = relationship("TranscriptChunk", back_populates="call", cascade="all, delete-orphan")
    replies = relationship("AgentReply", back_populates="call", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<CallRecord(call_id='{self.call_id}', status='{self.status}')>"


class TranscriptChunk(Base):
    """
    Represents a single transcript chunk from STT.
    """
    __tablename__ = "transcript_chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), ForeignKey("call_records.call_id"), nullable=False, index=True)
    
    text = Column(Text, nullable=False)
    is_final = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=True)
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    sequence_number = Column(Integer, nullable=False)  # Order within call
    
    # STT metadata
    speaker = Column(String(50), nullable=True, default="caller")  # caller, agent
    language = Column(String(10), nullable=True)
    
    # Relationships
    call = relationship("CallRecord", back_populates="transcripts")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TranscriptChunk(call_id='{self.call_id}', text='{self.text[:50]}...', is_final={self.is_final})>"


class AgentReply(Base):
    """
    Represents an agent's response (LLM generated).
    """
    __tablename__ = "agent_replies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), ForeignKey("call_records.call_id"), nullable=False, index=True)
    
    prompt = Column(Text, nullable=False)  # What was sent to LLM
    response_text = Column(Text, nullable=False)  # LLM response
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    sequence_number = Column(Integer, nullable=False)  # Order within call
    
    # LLM metadata
    model = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    generation_time_ms = Column(Float, nullable=True)
    
    # TTS metadata
    tts_generated = Column(Boolean, nullable=False, default=False)
    audio_duration_ms = Column(Float, nullable=True)
    
    # Relationships
    call = relationship("CallRecord", back_populates="replies")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<AgentReply(call_id='{self.call_id}', text='{self.response_text[:50]}...')>"


class DatabaseManager:
    """
    Manages database connections and operations.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./zylin.db")
        
        # Special handling for SQLite in-memory databases for testing
        if self.database_url == "sqlite:///:memory:":
            self.engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self.engine = create_engine(self.database_url)
        
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all tables in the database"""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database engine"""
        self.engine.dispose()


# Database operations helper functions
def create_call_record(
    session: Session,
    call_id: str,
    room_name: str,
    agent_identity: str,
    participant_sid: Optional[str] = None,
    participant_identity: Optional[str] = None
) -> CallRecord:
    """Create a new call record"""
    call = CallRecord(
        call_id=call_id,
        room_name=room_name,
        agent_identity=agent_identity,
        participant_sid=participant_sid,
        participant_identity=participant_identity,
        status="active"
    )
    session.add(call)
    session.commit()
    session.refresh(call)
    return call


def update_call_status(
    session: Session,
    call_id: str,
    status: str,
    error_message: Optional[str] = None
) -> Optional[CallRecord]:
    """Update call status"""
    call = session.query(CallRecord).filter(CallRecord.call_id == call_id).first()
    if call:
        call.status = status
        if error_message:
            call.error_message = error_message
        if status == "completed" or status == "failed":
            call.end_time = datetime.utcnow()
            if call.start_time:
                call.duration_seconds = (call.end_time - call.start_time).total_seconds()
        session.commit()
        session.refresh(call)
    return call


def add_transcript_chunk(
    session: Session,
    call_id: str,
    text: str,
    is_final: bool,
    confidence: float,
    sequence_number: int,
    speaker: str = "caller"
) -> TranscriptChunk:
    """Add a transcript chunk"""
    chunk = TranscriptChunk(
        call_id=call_id,
        text=text,
        is_final=is_final,
        confidence=confidence,
        sequence_number=sequence_number,
        speaker=speaker
    )
    session.add(chunk)
    session.commit()
    session.refresh(chunk)
    return chunk


def add_agent_reply(
    session: Session,
    call_id: str,
    prompt: str,
    response_text: str,
    sequence_number: int,
    model: Optional[str] = None,
    tokens_used: Optional[int] = None,
    generation_time_ms: Optional[float] = None
) -> AgentReply:
    """Add an agent reply"""
    reply = AgentReply(
        call_id=call_id,
        prompt=prompt,
        response_text=response_text,
        sequence_number=sequence_number,
        model=model,
        tokens_used=tokens_used,
        generation_time_ms=generation_time_ms
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)
    return reply


def get_call_transcripts(session: Session, call_id: str, final_only: bool = False):
    """Get all transcripts for a call"""
    query = session.query(TranscriptChunk).filter(TranscriptChunk.call_id == call_id)
    if final_only:
        query = query.filter(TranscriptChunk.is_final == True)
    return query.order_by(TranscriptChunk.sequence_number).all()


def get_call_replies(session: Session, call_id: str):
    """Get all agent replies for a call"""
    return session.query(AgentReply).filter(
        AgentReply.call_id == call_id
    ).order_by(AgentReply.sequence_number).all()


def get_call_record(session: Session, call_id: str) -> Optional[CallRecord]:
    """Get a specific call record"""
    return session.query(CallRecord).filter(CallRecord.call_id == call_id).first()
