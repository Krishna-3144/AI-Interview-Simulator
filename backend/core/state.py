# backend/core/state.py
from __future__ import annotations
from typing import Any, Literal, Optional
from typing_extensions import TypedDict


class CandidateProfile(TypedDict):
    name: str
    email: str
    skills: list[str]
    technologies: list[str]
    projects: list[dict]       # [{name, description, tech_stack, role}]
    experience: list[dict]     # [{company, role, duration, achievements}]
    education: list[dict]      # [{institution, degree, year}]
    coding_profiles: list[str]
    strongest_subjects: list[str]
    target_role: str


class SatisfactionScore(TypedDict):
    technical_accuracy: float  # 0-1
    depth: float               # 0-1
    communication: float       # 0-1
    confidence: float          # 0-1
    consistency: float         # 0-1
    overall: float             # weighted composite
    reasoning: str             # why this score (explainable AI)
    technical_gaps: Optional[list[str]]


class AnswerRecord(TypedDict):
    question_id: str
    question_text: str
    topic: str
    difficulty: int
    answer_text: str
    satisfaction: SatisfactionScore
    confidence_metrics: Optional[dict]
    follow_up_count: int
    timestamp: float


class ConversationTurn(TypedDict):
    role: Literal["interviewer", "candidate"]
    content: str
    timestamp: float


class TopicStatus(TypedDict):
    topic: str
    questions_asked: int
    avg_satisfaction: float
    difficulty_level: int      # 1-5
    complete: bool


class ConfidenceMetrics(TypedDict):
    duration_sec: float
    words: int
    words_per_second: float
    speech_rate_category: str  # "slow" | "normal" | "fast"
    long_pause_count: int
    long_pause_timestamps: list
    silence_ratio: float
    filler_word_count: int
    filler_words_found: list[str]
    pitch_variance: float
    energy_variance: float
    hesitation_score: float    # 0-1
    confidence_score: float    # 0-1
    probable_hesitation: bool


class InterviewState(TypedDict):
    # Session
    session_id: str
    phase: Literal[
        "resume_analysis", "intro", "technical",
        "behavioral", "project_deep_dive", "wrap_up", "report"
    ]

    # Candidate
    candidate_profile: Optional[CandidateProfile]
    resume_raw_text: str
    resume_path: Optional[str]

    # Conversation
    conversation_history: list[ConversationTurn]
    current_question: Optional[str]
    current_question_id: Optional[str]
    current_question_explanation: Optional[str]
    current_topic: Optional[str]
    raw_answer: str

    # Adaptive planning
    topic_queue: list[str]
    topic_statuses: dict[str, TopicStatus]
    current_difficulty: int
    follow_up_depth: int
    next_action: Literal[
        "ask_follow_up", "advance_topic", "deepen_difficulty",
        "project_deep_dive", "wrap_up", "generate_report", "idle"
    ]

    # Scoring
    answer_records: list[AnswerRecord]
    latest_satisfaction: Optional[SatisfactionScore]
    contradictions_detected: list[dict]

    # Audio
    audio_path: Optional[str]
    latest_confidence: Optional[ConfidenceMetrics]
    confidence_timeline: list[ConfidenceMetrics]

    # Memory
    memory_collection_id: str

    # Final
    final_report: Optional[dict]
