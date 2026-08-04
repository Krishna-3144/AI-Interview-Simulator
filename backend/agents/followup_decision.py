from typing import Dict, Any
from backend.core.config import settings
from backend.core.state import InterviewState

def make_followup_decision(state: InterviewState) -> Dict[str, Any]:
    phase = state.get("phase", "intro")
    raw_answer = state.get("raw_answer", "")
    topics = state.get("topics", [])
    topic_questions = state.get("topic_questions", {})
    follow_ups = state.get("follow_ups", 0)
    contradiction_found = state.get("contradiction_found", False)
    latest_eval = state.get("latest_eval", {})

    if not raw_answer:
        return {"next_action": "idle"}

    if phase in ("wrap_up", "report"):
        return {"next_action": "generate_report"}

    if phase == "technical":
        all_topics_complete = True
        for t in topics:
            if topic_questions.get(t, 0) < settings.MAX_QUESTIONS_PER_TOPIC:
                all_topics_complete = False
                break
        if all_topics_complete and topics:
            return {"next_action": "generate_report"}

    if phase == "intro":
        return {"next_action": "advance_topic", "follow_ups": 0}
        
    if phase == "project_deep_dive":
        return {"next_action": "advance_topic", "follow_ups": 0}

    if contradiction_found:
        return {
            "next_action": "clarify_contradiction", 
            "follow_ups": follow_ups + 1, 
            "contradiction_found": False
        }

    missing_topics = latest_eval.get("missing_topics", [])
    if missing_topics and follow_ups < settings.MAX_FOLLOW_UPS:
        return {"next_action": "ask_follow_up", "follow_ups": follow_ups + 1}

    return {"next_action": "advance_topic", "follow_ups": 0}
