# backend/agents/question_generation.py
from __future__ import annotations
import re, json, uuid, time

from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.state import InterviewState
from backend.core.llm import get_fast_llm

_llm = get_fast_llm(temperature=0.6)

SYSTEM_PROMPT = """
You are an expert technical interviewer. Generate exactly ONE interview question.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Use this exact structure:
{
  "question": "your question here",
  "question_type": "technical",
  "depth_markers": ["what a good answer mentions"],
  "explanation": "why this question was chosen"
}
Modes:
- new_question: fresh question at given difficulty (1=basic, 3=intermediate, 5=expert)
- follow_up: probe the weakness, reference the candidate's actual answer
- deepen: ask for edge cases, tradeoffs, system-level thinking
- project_deep_dive: ask about project internals, decisions, challenges
- intro: warm-up question
"""

def _parse(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {
            "question": text[:300],
            "question_type": "technical",
            "depth_markers": [],
            "explanation": "Auto-generated"
        }

def _get_mode(next_action: str) -> str:
    return {
        "ask_follow_up": "follow_up",
        "deepen_difficulty": "deepen",
        "project_deep_dive": "project_deep_dive",
    }.get(next_action, "new_question")

def _recent_history(history: list[dict], n: int = 4) -> str:
    return "\n".join(
        f"{'Interviewer' if t['role']=='interviewer' else 'Candidate'}: {t['content'][:300]}"
        for t in history[-n:]
    )

def question_generation_agent(state: InterviewState) -> dict:
    profile = state.get("candidate_profile", {})
    topic = state.get("current_topic", "General")
    difficulty = state.get("current_difficulty", 2)
    next_action = state.get("next_action", "idle")
    latest_sat = state.get("latest_satisfaction") or {}
    phase = state.get("phase", "technical")
    history = state.get("conversation_history", [])
    last_answer = state.get("raw_answer", "")

    mode = "intro" if phase == "intro" else _get_mode(next_action)

    context = {
        "candidate_name": profile.get("name", "candidate"),
        "topic": topic,
        "difficulty": difficulty,
        "mode": mode,
        "technologies": profile.get("technologies", [])[:5],
        "projects": [p.get("name") for p in profile.get("projects", [])][:3],
        "last_answer": last_answer[:300],
        "weakness_to_probe": latest_sat.get("reasoning", "")[:200],
        "recent_conversation": _recent_history(history, n=4),
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Context:\n{json.dumps(context, separators=(',', ':'))}"),
    ]
    response = _llm.invoke(messages)
    data = _parse(response.content)

    question_id = str(uuid.uuid4())
    history = list(history) + [{
        "role": "interviewer",
        "content": data["question"],
        "timestamp": time.time(),
    }]

    return {
        "current_question": data["question"],
        "current_question_id": question_id,
        "current_question_explanation": data.get("explanation", ""),
        "conversation_history": history,
        "raw_answer": "",
    }