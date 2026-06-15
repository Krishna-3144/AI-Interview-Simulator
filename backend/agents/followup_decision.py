# backend/agents/followup_decision.py
"""
Agent 5 — Follow-Up Decision
The adaptive brain of the system.
Reads satisfaction scores + context and decides next_action.
Also decides WHAT kind of follow-up if probing is needed.
"""
from __future__ import annotations

from backend.core.state import InterviewState
from backend.core.config import settings


def followup_decision_agent(state: InterviewState) -> dict:
    satisfaction = state.get("latest_satisfaction") or {}
    overall = satisfaction.get("overall", 0.0)
    follow_up_depth = state.get("follow_up_depth", 0)
    phase = state.get("phase", "technical")
    topic_statuses = state.get("topic_statuses", {})
    current_topic = state.get("current_topic", "")
    contradictions = state.get("contradictions_detected", [])
    answer_records = state.get("answer_records", [])
    profile = state.get("candidate_profile", {})

    # ── Wrap-up / end conditions ──────────────────────────────────────────────
    if phase in ("wrap_up", "report"):
        return {"next_action": "generate_report"}

    # All topics complete?
    remaining = [t for t in topic_statuses if not topic_statuses[t].get("complete")]
    if not remaining and topic_statuses:
        return {"next_action": "generate_report"}

    # No answer yet (first question of session)
    if not state.get("raw_answer"):
        return {"next_action": "idle"}

    # ── Contradiction — challenge it before moving on ─────────────────────────
    # Check if latest answer triggered a new contradiction
    latest_contradiction = None
    if contradictions:
        last = contradictions[-1]
        if last.get("question_id") == state.get("current_question_id"):
            latest_contradiction = last

    if latest_contradiction and follow_up_depth < settings.MAX_FOLLOW_UPS:
        return {
            "next_action": "ask_follow_up",
            "follow_up_depth": follow_up_depth + 1,
            # Inject contradiction context into satisfaction reasoning
            "latest_satisfaction": {
                **satisfaction,
                "reasoning": (
                    f"CONTRADICTION DETECTED: Earlier you said "
                    f'"{latest_contradiction.get("earlier_statement", "")}" '
                    f'but now "{latest_contradiction.get("current_statement", "")}". '
                    f"Please clarify. " + satisfaction.get("reasoning", "")
                ),
            },
        }

    # ── Project deep-dive trigger ─────────────────────────────────────────────
    # If candidate mentions a known project and we haven't deep-dived yet
    raw_answer = state.get("raw_answer", "").lower()
    known_projects = [p.get("name", "").lower() for p in profile.get("projects", [])]
    project_mentioned = any(p and p in raw_answer for p in known_projects)
    already_in_deep_dive = phase == "project_deep_dive"

    if (
        project_mentioned
        and not already_in_deep_dive
        and follow_up_depth == 0
        and overall >= 0.50  # only deep-dive if they know the project somewhat
    ):
        return {
            "next_action": "project_deep_dive",
            "follow_up_depth": follow_up_depth + 1,
            "phase": "project_deep_dive",
        }

    # ── Satisfactory — move on ────────────────────────────────────────────────
    threshold = settings.SATISFACTION_THRESHOLD
    if overall >= threshold:
        # Check if we should deepen (strong candidate)
        if overall >= 0.85 and follow_up_depth == 0:
            return {
                "next_action": "deepen_difficulty",
                "follow_up_depth": follow_up_depth + 1,
            }
        return {
            "next_action": "advance_topic",
            "follow_up_depth": 0,
        }

    # ── Unsatisfactory — probe ────────────────────────────────────────────────
    if follow_up_depth < settings.MAX_FOLLOW_UPS:
        return {
            "next_action": "ask_follow_up",
            "follow_up_depth": follow_up_depth + 1,
        }

    # Max follow-ups reached — move on regardless
    return {
        "next_action": "advance_topic",
        "follow_up_depth": 0,
    }
