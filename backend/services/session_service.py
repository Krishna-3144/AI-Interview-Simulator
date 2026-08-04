# backend/services/session_service.py
"""
Session management: create, save, load, and query interview sessions.
"""
from __future__ import annotations
import uuid
from sqlalchemy.orm import Session

from backend.db.models import InterviewSession
from backend.core.state import InterviewState


def create_session(db: Session, interview_type: str = "Backend") -> str:
    session_id = str(uuid.uuid4())
    row = InterviewSession(id=session_id, interview_type=interview_type)
    db.add(row)
    db.commit()
    return session_id


def build_initial_state(
    session_id: str,
    resume_path: str = "",
    interview_type: str = "Backend",
) -> InterviewState:
    return InterviewState(
        session_id=session_id,
        phase="resume_analysis",
        interview_type=interview_type,
        candidate=None,
        resume_path=resume_path,
        history=[],
        current_question=None,
        current_topic=None,
        raw_answer="",
        topics=[],
        topic_questions={},
        difficulty=2,
        follow_ups=0,
        next_action="idle",
        answers=[],
        latest_eval=None,
        contradiction_found=False,
        contradictions=[],
        confidence_timeline=[],
        selected_project=None,
        project_dive_index=0,
        final_report=None,
    )


def save_state(db: Session, session_id: str, state: InterviewState):
    row = db.query(InterviewSession).filter_by(id=session_id).first()
    if not row:
        return
    row.state_snapshot = dict(state)
    row.phase = state.get("phase", "unknown")
    row.interview_type = state.get("interview_type", "Backend")
    profile = state.get("candidate") or {}
    row.candidate_name = profile.get("name")
    row.candidate_email = profile.get("email")
    row.target_role = profile.get("target_role")
    if state.get("final_report"):
        row.final_report = state["final_report"]
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
