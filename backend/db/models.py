# backend/db/models.py
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float,
    DateTime, JSON, Boolean
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
    interview_type  = Column(String, default="Backend")
    is_complete     = Column(Boolean, default=False)

    # Full state snapshot (JSON blob) — lets us resume sessions
    state_snapshot  = Column(JSON, nullable=True)

    # Final report
    final_report    = Column(JSON, nullable=True)
    hiring_recommendation = Column(String, nullable=True)
    overall_score   = Column(Float, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
