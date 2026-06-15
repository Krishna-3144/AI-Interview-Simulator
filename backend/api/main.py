# backend/api/main.py
"""
FastAPI application.
Routes:
  POST /api/sessions          — create session, upload resume
  GET  /api/sessions/{id}     — get session info
  POST /api/sessions/{id}/answer  — submit text answer
  POST /api/sessions/{id}/audio   — submit audio answer
  GET  /api/sessions/{id}/report  — get final report
  WS   /ws/{session_id}       — real-time interview WebSocket
"""
from __future__ import annotations
import os, uuid, json, shutil, time
from pathlib import Path

from fastapi import (
    FastAPI, UploadFile, File, Form, Depends,
    WebSocket, WebSocketDisconnect, HTTPException
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.db.models import init_db, get_db
from backend.core.graph import interview_graph
from backend.core.config import settings
from backend.services import session_service, memory_service
from backend.services.audio_service import process_answer_audio

app = FastAPI(title="AI Interview Simulator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()


# ── Static files + HTML pages ─────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("backend/static/index.html")

@app.get("/interview", response_class=HTMLResponse)
def interview_page():
    return FileResponse("backend/static/interview.html")

@app.get("/report", response_class=HTMLResponse)
def report_page():
    return FileResponse("backend/static/report.html")


# ── REST API ──────────────────────────────────────────────────────────────────

@app.post("/api/sessions")
async def create_session(
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload resume PDF and create a new interview session."""
    session_id = session_service.create_session(db)

    # Save PDF
    resume_path = UPLOAD_DIR / f"{session_id}_resume.pdf"
    with open(resume_path, "wb") as f:
        shutil.copyfileobj(resume.file, f)

    # Build initial state
    state = session_service.build_initial_state(
        session_id=session_id,
        resume_path=str(resume_path),
    )

    # Run resume analysis + planning + first question generation
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    return {
        "session_id":   session_id,
        "candidate":    state.get("candidate_profile", {}),
        "first_question": state.get("current_question"),
        "explanation":  state.get("current_question_explanation"),
        "phase":        state.get("phase"),
        "topic":        state.get("current_topic"),
        "difficulty":   state.get("current_difficulty"),
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    row = session_service.get_session(db, session_id)
    if not row:
        raise HTTPException(404, "Session not found")
    return {
        "session_id":  row.id,
        "phase":       row.phase,
        "is_complete": row.is_complete,
        "candidate_name": row.candidate_name,
        "target_role": row.target_role,
        "created_at":  str(row.created_at),
    }

@app.get("/api/sessions/{session_id}/analysis")
def get_session_analysis(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    return {
        "answer_records": state.get("answer_records", []),
        "contradictions": state.get("contradictions_detected", []),
    }

@app.post("/api/sessions/{session_id}/answer")
async def submit_text_answer(
    session_id: str,
    answer: str = Form(...),
    db: Session = Depends(get_db),
):
    """Submit a typed text answer and get the next question."""
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    state["raw_answer"] = answer

    # Run evaluation → follow-up decision → next question
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {
            "done": True,
            "session_id": session_id,
        }

    return {
        "done":        False,
        "question":    state.get("current_question"),
        "explanation": state.get("current_question_explanation"),
        "topic":       state.get("current_topic"),
        "difficulty":  state.get("current_difficulty"),
        "phase":       state.get("phase"),
        "next_action": state.get("next_action"),
        "follow_up_depth": state.get("follow_up_depth", 0),
        "latest_scores": state.get("latest_satisfaction"),
        "contradictions": state.get("contradictions_detected", []),
    }

@app.post("/api/sessions/{session_id}/skip_followup")
def skip_followup(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    state["skip_action"] = "skip_followup"
    state["follow_up_depth"] = 0
    state["next_action"] = "advance_topic"

    state = interview_graph.invoke(state)
    state["skip_action"] = None
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    return {
        "done":        False,
        "question":    state.get("current_question"),
        "explanation": state.get("current_question_explanation"),
        "topic":       state.get("current_topic"),
        "difficulty":  state.get("current_difficulty"),
        "phase":       state.get("phase"),
        "next_action": state.get("next_action"),
        "follow_up_depth": state.get("follow_up_depth", 0),
        "latest_scores": state.get("latest_satisfaction"),
        "contradictions": state.get("contradictions_detected", []),
    }


@app.post("/api/sessions/{session_id}/skip_topic")
def skip_topic(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    current_topic = state.get("current_topic")
    if current_topic and current_topic in state.get("topic_statuses", {}):
        state["topic_statuses"][current_topic]["complete"] = True

    state["skip_action"] = "skip_topic"
    state["follow_up_depth"] = 0
    state["next_action"] = "advance_topic"

    state = interview_graph.invoke(state)
    state["skip_action"] = None
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    return {
        "done":        False,
        "question":    state.get("current_question"),
        "explanation": state.get("current_question_explanation"),
        "topic":       state.get("current_topic"),
        "difficulty":  state.get("current_difficulty"),
        "phase":       state.get("phase"),
        "next_action": state.get("next_action"),
        "follow_up_depth": state.get("follow_up_depth", 0),
        "latest_scores": state.get("latest_satisfaction"),
        "contradictions": state.get("contradictions_detected", []),
    }


@app.post("/api/sessions/{session_id}/end_interview")
def end_interview(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    state["skip_action"] = "force_report"
    state["phase"] = "report"

    state = interview_graph.invoke(state)
    state["skip_action"] = None
    session_service.save_state(db, session_id, state)

    return {"done": True, "session_id": session_id}


@app.post("/api/sessions/{session_id}/audio")
async def submit_audio_answer(
    session_id: str,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Submit voice answer — transcribe, analyze, then evaluate."""
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    # Save audio file
    audio_path = UPLOAD_DIR / f"{session_id}_{uuid.uuid4()}.wav"
    with open(audio_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    # Transcribe + analyze
    transcript, confidence_metrics = process_answer_audio(str(audio_path))

    # Inject into state
    state["raw_answer"]       = transcript
    state["audio_path"]       = str(audio_path)
    state["latest_confidence"] = confidence_metrics

    # Add to timeline
    timeline = list(state.get("confidence_timeline", []))
    timeline.append(confidence_metrics)
    state["confidence_timeline"] = timeline

    # Run agent pipeline
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    return {
        "done":             False,
        "transcript":       transcript,
        "confidence":       confidence_metrics,
        "question":         state.get("current_question"),
        "explanation":      state.get("current_question_explanation"),
        "topic":            state.get("current_topic"),
        "difficulty":       state.get("current_difficulty"),
        "phase":            state.get("phase"),
        "next_action":      state.get("next_action"),
        "follow_up_depth":  state.get("follow_up_depth", 0),
        "latest_scores":    state.get("latest_satisfaction"),
        "contradictions":   state.get("contradictions_detected", []),
    }


@app.get("/api/sessions/{session_id}/report")
def get_report(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    report = state.get("final_report")
    if not report:
        raise HTTPException(400, "Interview not complete yet")
    return report
