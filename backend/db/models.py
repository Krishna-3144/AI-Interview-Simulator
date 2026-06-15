# backend/db/models.py
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    DateTime, Text, JSON, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.core.config import settings

Base = declarative_base()
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite only
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id              = Column(String, primary_key=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    completed_at    = Column(DateTime, nullable=True)
    candidate_name  = Column(String, nullable=True)
    candidate_email = Column(String, nullable=True)
    target_role     = Column(String, nullable=True)
    phase           = Column(String, default="resume_analysis")
    is_complete     = Column(Boolean, default=False)

    # Full state snapshot (JSON blob) — lets us resume sessions
    state_snapshot  = Column(JSON, nullable=True)

    # Final report
    final_report    = Column(JSON, nullable=True)
    hiring_recommendation = Column(String, nullable=True)
    overall_score   = Column(Float, nullable=True)


class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id              = Column(String, primary_key=True)
    session_id      = Column(String, index=True)
    question_id     = Column(String)
    question_text   = Column(Text)
    topic           = Column(String)
    difficulty      = Column(Integer)
    answer_text     = Column(Text)
    follow_up_count = Column(Integer, default=0)
    timestamp       = Column(Float)

    # Satisfaction scores
    score_technical = Column(Float)
    score_depth     = Column(Float)
    score_communication = Column(Float)
    score_confidence = Column(Float)
    score_consistency = Column(Float)
    score_overall   = Column(Float)
    score_reasoning = Column(Text)

    # Confidence metrics
    confidence_metrics = Column(JSON, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
