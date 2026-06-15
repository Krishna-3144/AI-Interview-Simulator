# backend/agents/resume_analysis.py
from __future__ import annotations
import re, json
import fitz

from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.state import InterviewState
from backend.core.llm import get_fast_llm

_llm = get_fast_llm(temperature=0.1)

SYSTEM_PROMPT = """
You are an expert technical recruiter parsing a resume.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Use this exact structure:
{
  "name": "string",
  "email": "string",
  "skills": ["skill1"],
  "technologies": ["tech1"],
  "projects": [{"name": "...", "description": "...", "tech_stack": ["..."], "role": "..."}],
  "experience": [{"company": "...", "role": "...", "duration": "...", "achievements": ["..."]}],
  "education": [{"institution": "...", "degree": "...", "year": "..."}],
  "coding_profiles": ["url1"],
  "strongest_subjects": ["subject1"],
  "target_role": "string",
  "topic_queue": ["topic1", "topic2", "topic3", "topic4"],
  "planning_rationale": "brief explanation"
}
Rules for topic_queue:
- Pick 4-5 topics from the candidate's actual skills and technologies
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

def _extract_pdf_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)

def resume_analysis_agent(state: InterviewState) -> dict:
    resume_text = state.get("resume_raw_text", "")
    if not resume_text and state.get("resume_path"):
        resume_text = _extract_pdf_text(state["resume_path"])
    if not resume_text:
        raise ValueError("No resume text or PDF path in state.")

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Resume text:\n\n{resume_text[:3000]}"),
    ]
    response = _llm.invoke(messages)
    parsed = _parse(response.content)

    topic_queue = parsed.pop("topic_queue", [])
    planning_rationale = parsed.pop("planning_rationale", "")
    profile = parsed

    return {
        "candidate_profile": profile,
        "resume_raw_text": "",  # Clear the raw text to save state token usage
        "phase": "intro",
        "topic_queue": topic_queue,
        "topic_statuses": {},
        "answer_records": [],
        "conversation_history": [],
        "contradictions_detected": [],
        "confidence_timeline": [],
        "follow_up_depth": 0,
        "current_difficulty": 2,
        "next_action": "idle",
    }