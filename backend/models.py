"""
Database Models for Zylin Voice Agent
Defines SQLAlchemy models for call records, transcripts, agent replies, customers, and usage tracking.
"""
from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, ARRAY, DECIMAL
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

Base = declarative_base()


class Customer(Base):
    """
    Represents a customer/organization (multi-tenancy).
    """
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    company_name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    api_key_hash = Column(String(255), nullable=False)
    
    # Plan and limits
    plan_type = Column(String(50), nullable=False, default="free")  # free, starter, pro, enterprise
    max_calls_per_month = Column(Integer, default=100)
    calls_this_month = Column(Integer, default=0)
    
    status = Column(String(50), nullable=False, default="active")  # active, suspended, cancelled
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    usage_logs = relationship("UsageLog", back_populates="customer", cascade="all, delete-orphan")
    webhook_configs = relationship("WebhookConfig", back_populates="customer", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Customer(company='{self.company_name}', plan='{self.plan_type}')>"


class UsageLog(Base):
    """
    Tracks usage for billing and analytics.
    """
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False, index=True)
    call_id = Column(String(100), nullable=False)
    
    duration_seconds = Column(Float)
    stt_characters = Column(Integer)
    llm_tokens = Column(Integer)
    tts_characters = Column(Integer)
    cost_usd = Column(DECIMAL(10, 4))
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="usage_logs")
    
    def __repr__(self):
        return f"<UsageLog(call='{self.call_id}', cost=${self.cost_usd})>"


class WebhookConfig(Base):
    """
    Customer webhook configurations.
    """
    __tablename__ = "webhook_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False, index=True)
    webhook_url = Column(Text, nullable=False)
    events = Column(ARRAY(String))  # Array of event types
    secret_key = Column(String(255), nullable=False)  # For HMAC signature
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="webhook_configs")
    
    def __repr__(self):
        return f"<WebhookConfig(url='{self.webhook_url[:50]}...')>"


class CallRecord(Base):
    """
    Represents a single call session.
    """
    __tablename__ = "call_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=True, index=True)  # Null for legacy calls
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
    appointments = relationship("Appointment", back_populates="call", cascade="all, delete-orphan")
    
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


class Appointment(Base):
    """
    Represents a confirmed appointment booking.
    """
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), ForeignKey("call_records.call_id"), nullable=False, index=True)
    
    # Appointment details
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(50), nullable=True)
    customer_email = Column(String(200), nullable=True)
    
    appointment_date = Column(String(50), nullable=False)  # e.g., "2024-03-15"
    appointment_time = Column(String(50), nullable=False)  # e.g., "2:30 PM"
    service_type = Column(String(200), nullable=True)  # e.g., "consultation", "checkup"
    
    notes = Column(Text, nullable=True)  # Additional notes or special requests
    status = Column(String(50), nullable=False, default="confirmed")  # confirmed, cancelled, completed
    
    # Metadata
    booked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_by_agent = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    call = relationship("CallRecord", back_populates="appointments")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Appointment(customer='{self.customer_name}', date='{self.appointment_date}', time='{self.appointment_time}')>"


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


def create_appointment_record(
    session: Session,
    call_id: str,
    customer_name: str,
    appointment_date: str,
    appointment_time: str,
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
    service_type: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = "confirmed"
) -> Appointment:
    """Create a new appointment record"""
    appointment = Appointment(
        call_id=call_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        service_type=service_type,
        notes=notes,
        status=status,
        confirmed_by_agent=True
    )
    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    return appointment


def get_appointments_for_call(session: Session, call_id: str):
    """Get all appointments for a specific call"""
    return session.query(Appointment).filter(
        Appointment.call_id == call_id
    ).order_by(Appointment.booked_at).all()


def get_all_appointments(
    session: Session,
    status: Optional[str] = None,
    limit: Optional[int] = None
):
    """Get all appointments, optionally filtered by status"""
    query = session.query(Appointment)
    if status:
        query = query.filter(Appointment.status == status)
    query = query.order_by(Appointment.appointment_date, Appointment.appointment_time)
    if limit:
        query = query.limit(limit)
    return query.all()


def update_appointment_status(
    session: Session,
    appointment_id: int,
    status: str
) -> Optional[Appointment]:
    """Update appointment status"""
    appointment = session.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment:
        appointment.status = status
        session.commit()
        session.refresh(appointment)
    return appointment


# Customer management helper functions
def create_customer(
    session: Session,
    customer_name: str,
    email: str,
    api_key_hash: str,
    plan_type: str = "free",
    max_calls_per_month: int = 100,
    max_minutes_per_call: int = 10
) -> Customer:
    """Create a new customer"""
    customer = Customer(
        customer_name=customer_name,
        email=email,
        api_key_hash=api_key_hash,
        plan_type=plan_type,
        max_calls_per_month=max_calls_per_month,
        max_minutes_per_call=max_minutes_per_call,
        is_active=True
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


def get_customer_by_id(session: Session, customer_id: str) -> Optional[Customer]:
    """Get customer by ID"""
    return session.query(Customer).filter(Customer.customer_id == customer_id).first()


def get_customer_by_email(session: Session, email: str) -> Optional[Customer]:
    """Get customer by email"""
    return session.query(Customer).filter(Customer.email == email).first()


def increment_customer_usage(session: Session, customer_id: str) -> bool:
    """Increment customer's monthly call counter"""
    customer = session.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        customer.calls_this_month += 1
        customer.last_call_at = datetime.utcnow()
        session.commit()
        return True
    return False


def log_usage(
    session: Session,
    customer_id: str,
    call_id: str,
    duration_seconds: float,
    tokens_used: int = 0,
    cost_usd: float = 0.0
) -> UsageLog:
    """Log usage for billing"""
    usage = UsageLog(
        customer_id=customer_id,
        call_id=call_id,
        duration_seconds=duration_seconds,
        tokens_used=tokens_used,
        cost_usd=cost_usd
    )
    session.add(usage)
    session.commit()
    session.refresh(usage)
    return usage


def get_customer_usage_logs(
    session: Session,
    customer_id: str,
    limit: Optional[int] = 100
):
    """Get usage logs for a customer"""
    query = session.query(UsageLog).filter(UsageLog.customer_id == customer_id)
    query = query.order_by(UsageLog.timestamp.desc())
    if limit:
        query = query.limit(limit)
    return query.all()
