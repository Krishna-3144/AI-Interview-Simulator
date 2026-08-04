# backend/api/main.py
"""
FastAPI application.
Routes:
  POST /api/sessions                — create session, upload resume
  GET  /api/sessions/{id}           — get session info
  GET  /api/sessions/{id}/analysis  — get detailed answer records
  GET  /api/sessions/{id}/report    — get final report
  POST /api/sessions/{id}/answer    — submit text answer
  POST /api/sessions/{id}/audio     — submit audio answer
  POST /api/sessions/{id}/skip_followup  — skip follow-up questions
  POST /api/sessions/{id}/skip_topic     — skip current topic
  POST /api/sessions/{id}/end_interview  — end and generate report
  GET  /api/sessions/{id}/question_audio — TTS audio for current question
"""
from __future__ import annotations
import os, uuid, shutil, time, threading, hashlib
from pathlib import Path

from fastapi import (
    FastAPI, UploadFile, File, Form, Depends, HTTPException,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.db.models import init_db, get_db
from backend.core.graph import interview_graph
from backend.core.config import settings
from backend.services import session_service
from backend.services.audio_service import process_answer_audio

app = FastAPI(title="AI Interview Simulator", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()


# ── TTS Precaching ───────────────────────────────────────────────────────────

def _precache_tts(session_id: str, state: dict):
    question_text = state.get("current_question")
    if question_text:
        from backend.services.tts_service import generate_tts_for_question
        q_hash = hashlib.md5(question_text.encode("utf-8")).hexdigest()
        generate_tts_for_question(session_id, q_hash, question_text)


def _precache_tts_async(session_id: str, state: dict):
    threading.Thread(target=_precache_tts, args=(session_id, state), daemon=True).start()


# ── Static files + HTML pages ────────────────────────────────────────────────

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


# ── Helper: build standard response ─────────────────────────────────────────

def _question_response(state: dict, **extra) -> dict:
    """Build a standard response dict for endpoints that return the next question."""
    return {
        "done": False,
        "question": state.get("current_question"),
        "topic": state.get("current_topic"),
        "difficulty": state.get("difficulty"),
        "phase": state.get("phase"),
        "next_action": state.get("next_action"),
        "follow_ups": state.get("follow_ups", 0),
        "latest_scores": state.get("latest_eval"),
        "contradictions": state.get("contradictions", []),
        **extra,
    }


# ── REST API ─────────────────────────────────────────────────────────────────

@app.post("/api/sessions")
async def create_session(
    resume: UploadFile = File(...),
    interview_type: str = Form("Backend"),
    db: Session = Depends(get_db),
):
    """Upload resume PDF and create a new interview session."""
    session_id = session_service.create_session(db, interview_type=interview_type)

    # Save PDF
    resume_path = UPLOAD_DIR / f"{session_id}_resume.pdf"
    with open(resume_path, "wb") as f:
        shutil.copyfileobj(resume.file, f)

    # Build initial state and run graph (resume analysis → planning → first question)
    state = session_service.build_initial_state(
        session_id=session_id,
        resume_path=str(resume_path),
        interview_type=interview_type,
    )
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)
    _precache_tts_async(session_id, state)

    return {
        "session_id": session_id,
        "candidate": state.get("candidate", {}),
        "first_question": state.get("current_question"),
        "phase": state.get("phase"),
        "topic": state.get("current_topic"),
        "difficulty": state.get("difficulty"),
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    row = session_service.get_session(db, session_id)
    if not row:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": row.id,
        "phase": row.phase,
        "is_complete": row.is_complete,
        "candidate_name": row.candidate_name,
        "target_role": row.target_role,
        "created_at": str(row.created_at),
    }


@app.get("/api/sessions/{session_id}/analysis")
def get_session_analysis(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    return {
        "answers": state.get("answers", []),
        "contradictions": state.get("contradictions", []),
    }


@app.get("/api/sessions/{session_id}/question_audio")
def get_question_audio(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    question_text = state.get("current_question")
    if not question_text:
        raise HTTPException(404, "No question found")

    from backend.services.tts_service import generate_tts_for_question
    q_hash = hashlib.md5(question_text.encode("utf-8")).hexdigest()
    audio_path = generate_tts_for_question(session_id, q_hash, question_text)
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(500, "Failed to generate question audio")
    return FileResponse(audio_path, media_type="audio/wav")


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
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    _precache_tts_async(session_id, state)
    return _question_response(state)


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
    state["raw_answer"] = transcript
    timeline = list(state.get("confidence_timeline", []))
    timeline.append(confidence_metrics)
    state["confidence_timeline"] = timeline

    # Run graph
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    _precache_tts_async(session_id, state)
    return _question_response(state, transcript=transcript, confidence=confidence_metrics)


@app.post("/api/sessions/{session_id}/skip_followup")
def skip_followup(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    state["follow_ups"] = 0
    state["next_action"] = "advance_topic"
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    _precache_tts_async(session_id, state)
    return _question_response(state)


@app.post("/api/sessions/{session_id}/skip_topic")
def skip_topic(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    # Mark current topic as done
    current_topic = state.get("current_topic")
    topic_questions = dict(state.get("topic_questions", {}))
    if current_topic and current_topic in topic_questions:
        topic_questions[current_topic] = 999  # mark as exhausted
        state["topic_questions"] = topic_questions

    if state.get("phase") == "project_deep_dive":
        state["phase"] = "technical"
        state["current_topic"] = ""

    state["follow_ups"] = 0
    state["next_action"] = "advance_topic"
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    if state.get("phase") == "report":
        return {"done": True, "session_id": session_id}

    _precache_tts_async(session_id, state)
    return _question_response(state)


@app.post("/api/sessions/{session_id}/end_interview")
def end_interview(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    state["phase"] = "report"
    state = interview_graph.invoke(state)
    session_service.save_state(db, session_id, state)

    return {"done": True, "session_id": session_id}


@app.get("/api/sessions/{session_id}/report")
def get_report(session_id: str, db: Session = Depends(get_db)):
    state = session_service.load_state(db, session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    report = state.get("final_report")
    if not report:
        raise HTTPException(400, "Interview not complete yet")
    return report
