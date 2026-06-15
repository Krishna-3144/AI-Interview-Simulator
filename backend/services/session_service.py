# backend/services/session_service.py
"""
Manages interview sessions:
- create new session
- save state snapshot to DB
- load state from DB
- mark session complete
"""
from __future__ import annotations
import uuid, json, time
from sqlalchemy.orm import Session

from backend.db.models import InterviewSession, AnswerRecord as DBAnswerRecord
from backend.core.state import InterviewState


def create_session(db: Session) -> str:
    session_id = str(uuid.uuid4())
    row = InterviewSession(id=session_id)
    db.add(row)
    db.commit()
    return session_id


def build_initial_state(session_id: str, resume_text: str = "", resume_path: str = "") -> InterviewState:
    return InterviewState(
        session_id=session_id,
        phase="resume_analysis",
        candidate_profile=None,
        resume_raw_text=resume_text,
        resume_path=resume_path,
        conversation_history=[],
        current_question=None,
        current_question_id=None,
        current_question_explanation=None,
        current_topic=None,
        raw_answer="",
        topic_queue=[],
        topic_statuses={},
        current_difficulty=2,
        follow_up_depth=0,
        next_action="idle",
        answer_records=[],
        latest_satisfaction=None,
        contradictions_detected=[],
        audio_path=None,
        latest_confidence=None,
        confidence_timeline=[],
        memory_collection_id=session_id,
        final_report=None,
    )


def save_state(db: Session, session_id: str, state: InterviewState):
    row = db.query(InterviewSession).filter_by(id=session_id).first()
    if not row:
        return
    row.state_snapshot = dict(state)
    row.phase = state.get("phase", "unknown")
    profile = state.get("candidate_profile") or {}
    row.candidate_name  = profile.get("name")
    row.candidate_email = profile.get("email")
    row.target_role     = profile.get("target_role")
    if state.get("final_report"):
        row.final_report = state["final_report"]
        row.hiring_recommendation = state["final_report"].get("hiring_recommendation")
        row.overall_score = state["final_report"].get("overall_score")
        row.is_complete = True
        import datetime
        row.completed_at = datetime.datetime.utcnow()
    db.commit()


def load_state(db: Session, session_id: str) -> InterviewState | None:
    row = db.query(InterviewSession).filter_by(id=session_id).first()
    if not row or not row.state_snapshot:
        return None
    return InterviewState(**row.state_snapshot)


def get_session(db: Session, session_id: str) -> InterviewSession | None:
    return db.query(InterviewSession).filter_by(id=session_id).first()
