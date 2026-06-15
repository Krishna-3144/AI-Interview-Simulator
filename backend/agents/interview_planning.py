# backend/agents/interview_planning.py
from __future__ import annotations
import re, json

from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.state import InterviewState, TopicStatus
from backend.core.llm import get_fast_llm
from backend.core.config import settings

_llm = get_fast_llm(temperature=0.2)

PLANNING_PROMPT = """
You are a senior technical interviewer planning an interview.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Use this exact structure:
{
  "topic_queue": ["topic1", "topic2", "topic3", "topic4"],
  "rationale": "brief explanation"
}
Rules:
- Pick 4-5 topics from the candidate's actual skills
- Always end with: Communication & Problem Solving
- Order strongest areas first
- Topic names should be concise: Python, Machine Learning, SQL etc.
"""

def _parse(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise

def _build_topic_statuses(topics: list[str]) -> dict:
    return {
        t: {"topic": t, "questions_asked": 0, "avg_satisfaction": 0.0,
            "difficulty_level": 2, "complete": False}
        for t in topics
    }

def _adapt_difficulty(current: int, avg_sat: float) -> int:
    if avg_sat >= 0.78 and current < 5:
        return current + 1
    if avg_sat <= 0.42 and current > 1:
        return current - 1
    return current

def interview_planning_agent(state: InterviewState) -> dict:
    profile = state.get("candidate_profile", {})
    topic_queue = state.get("topic_queue", [])
    topic_statuses = state.get("topic_statuses", {})
    current_topic = state.get("current_topic", "")
    latest_sat = state.get("latest_satisfaction")
    current_phase = state.get("phase", "intro")
    answer_records = state.get("answer_records", [])
    num_answers = len(answer_records)

    # If topic queue is pre-populated by resume analyzer, initialize statuses deterministically
    if topic_queue and not topic_statuses:
        return {
            "topic_statuses": _build_topic_statuses(topic_queue),
            "current_topic": topic_queue[0],
            "current_difficulty": 2,
            "follow_up_depth": 0,
            "phase": "intro",
        }

    if not topic_queue:
        messages = [
            SystemMessage(content=PLANNING_PROMPT),
            HumanMessage(content=f"Candidate profile:\n{json.dumps(profile, separators=(',', ':'))[:3000]}"),
        ]
        response = _llm.invoke(messages)
        plan = _parse(response.content)
        topics = plan["topic_queue"]
        return {
            "topic_queue": topics,
            "topic_statuses": _build_topic_statuses(topics),
            "current_topic": topics[0],
            "current_difficulty": 2,
            "follow_up_depth": 0,
            "phase": "intro",
        }

    # Update stats ONLY if we were in the technical or project phase (not warm-up)
    if current_topic and latest_sat and current_topic in topic_statuses:
        if current_phase == "technical" or current_phase == "project_deep_dive":
            st = dict(topic_statuses[current_topic])
            n = st["questions_asked"]
            new_avg = (st["avg_satisfaction"] * n + latest_sat["overall"]) / (n + 1)
            topic_statuses[current_topic] = {
                **st,
                "questions_asked": n + 1,
                "avg_satisfaction": round(new_avg, 3),
                "difficulty_level": _adapt_difficulty(st["difficulty_level"], new_avg),
            }

    # Handle intro warm-up phase transition
    if num_answers < 2:
        return {
            "topic_statuses": topic_statuses,
            "current_difficulty": topic_statuses.get(current_topic, {}).get("difficulty_level", 2),
            "phase": "intro",
        }

    if current_phase == "intro" and num_answers >= 2:
        current_phase = "technical"

    # Check if current technical topic is done
    st = topic_statuses.get(current_topic, {})
    q_asked = st.get("questions_asked", 0)
    avg_sat = st.get("avg_satisfaction", 0.0)
    topic_done = (q_asked >= settings.MIN_QUESTIONS_PER_TOPIC and avg_sat >= 0.72) \
                 or q_asked >= settings.MAX_QUESTIONS_PER_TOPIC

    if topic_done:
        topic_statuses[current_topic]["complete"] = True
        remaining = [t for t in topic_queue if not topic_statuses[t].get("complete")]
        if not remaining:
            return {"topic_statuses": topic_statuses, "phase": "report"}
        next_topic = remaining[0]
        return {
            "topic_statuses": topic_statuses,
            "current_topic": next_topic,
            "current_difficulty": topic_statuses[next_topic].get("difficulty_level", 2),
            "follow_up_depth": 0,
            "phase": "technical",
        }

    return {
        "topic_statuses": topic_statuses,
        "current_difficulty": topic_statuses.get(current_topic, {}).get("difficulty_level", 2),
        "phase": current_phase,
    }