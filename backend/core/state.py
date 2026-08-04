# backend/core/state.py
"""
Simplified InterviewState — 18 fields, 4 TypedDicts.
This is the single source of truth passed across all LangGraph nodes.
"""
from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict


class CandidateProfile(TypedDict):
    name: str
    email: str
    skills: list[str]
    projects: list[dict]       # [{name, description, tech_stack}]
    experience: list[dict]     # [{company, role, duration}]
    education: list[dict]      # [{institution, degree, year}]
    target_role: str


class EvaluationResult(TypedDict):
    score: float               # 0.0 to 10.0
    summary: str
    strengths: list[str]
    missing_topics: list[str]


class AnswerRecord(TypedDict):
    question: str
    answer: str
    topic: str
    difficulty: int
    evaluation: EvaluationResult
    timestamp: float


class Contradiction(TypedDict):
    earlier: str
    current: str
    topic: str


class InterviewState(TypedDict):
    # ── Session ──
    session_id: str
    phase: str                          # resume_analysis | intro | project_deep_dive | technical | report
    interview_type: str                 # SDE | Backend | ML | Internship | HR

    # ── Candidate ──
    candidate: Optional[CandidateProfile]
    resume_path: Optional[str]

    # ── Conversation ──
    history: list[dict]                 # [{role: "interviewer"|"candidate", content: str}]
    current_question: Optional[str]
    current_topic: Optional[str]
    raw_answer: str

    # ── Adaptive Planning ──
    topics: list[str]                   # ordered topic queue
    topic_questions: dict[str, int]     # topic → number of questions asked
    difficulty: int                     # current difficulty 1-5
    follow_ups: int                     # current follow-up depth counter
    next_action: str                    # idle | ask_follow_up | clarify_contradiction | advance_topic | generate_report

    # ── Scoring ──
    answers: list[AnswerRecord]
    latest_eval: Optional[EvaluationResult]
    contradiction_found: bool           # flag set when contradiction detected on current turn
    contradictions: list[Contradiction]  # accumulated list shown in final report

    # ── Audio ──
    confidence_timeline: list[dict]     # audio metrics, populated only in voice mode

    # ── Project Deep Dive ──
    selected_project: Optional[str]
    project_dive_index: int

    # ── Final ──
    final_report: Optional[dict]
