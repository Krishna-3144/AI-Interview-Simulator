# backend/agents/report_generation.py
from __future__ import annotations
import re, json
from collections import defaultdict

from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.state import InterviewState
from backend.core.llm import get_main_llm

_llm = get_main_llm(temperature=0.2)

REPORT_PROMPT = """
You are a senior technical interviewer writing a post-interview assessment.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Use this exact structure:
{
  "summary": "2-3 sentence overall summary",
  "hiring_recommendation": "Strong Hire",
  "recommendation_reasoning": "detailed reasoning",
  "technical_strengths": ["strength1", "strength2"],
  "technical_weaknesses": ["weakness1", "weakness2"],
  "communication_assessment": "paragraph about communication",
  "confidence_assessment": "paragraph about confidence",
  "behavioral_insights": "paragraph about behavior",
  "improvement_suggestions": ["suggestion1", "suggestion2"]
}
Hiring criteria: Strong Hire>=0.80, Hire>=0.65, Borderline>=0.50, Reject<0.50
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

def _aggregate_scores(records: list[dict]) -> dict:
    by_topic = defaultdict(list)
    all_scores = []
    for r in records:
        sat = r.get("satisfaction", {})
        overall = sat.get("overall", 0.0)
        by_topic[r.get("topic", "General")].append(overall)
        all_scores.append(overall)
    return {
        "by_topic": {t: round(sum(s)/len(s), 3) for t, s in by_topic.items()},
        "overall": round(sum(all_scores)/len(all_scores), 3) if all_scores else 0.0,
    }

def _aggregate_confidence(timeline: list[dict]) -> dict:
    if not timeline:
        return {}
    keys = ["confidence_score", "hesitation_score", "filler_word_count",
            "long_pause_count", "words_per_second", "silence_ratio"]
    return {k: round(sum(m.get(k,0) for m in timeline)/len(timeline), 3) for k in keys}

def report_generation_agent(state: InterviewState) -> dict:
    answer_records = state.get("answer_records", [])
    confidence_timeline = state.get("confidence_timeline", [])
    contradictions = state.get("contradictions_detected", [])
    profile = state.get("candidate_profile", {})

    score_summary = _aggregate_scores(answer_records)
    conf_summary = _aggregate_confidence(confidence_timeline)

    messages = [
        SystemMessage(content=REPORT_PROMPT),
        HumanMessage(content=json.dumps({
            "candidate_name": profile.get("name", "Candidate"),
            "target_role": profile.get("target_role", ""),
            "overall_score": score_summary["overall"],
            "topic_scores": score_summary["by_topic"],
            "avg_confidence": conf_summary.get("confidence_score", 0),
            "contradiction_count": len(contradictions),
            "answer_count": len(answer_records),
            "answer_sample": [
                {"topic": r.get("topic"), "score": r.get("satisfaction", {}).get("overall", 0),
                 "reasoning": r.get("satisfaction", {}).get("reasoning", "")[:300]}
                for r in answer_records[-6:]
            ],
        }, indent=2)),
    ]
    report_data = _parse(_llm.invoke(messages).content)

    report_data.update({
        "score_by_topic": score_summary["by_topic"],
        "overall_score": score_summary["overall"],
        "confidence_summary": conf_summary,
        "confidence_timeline": confidence_timeline,
        "contradictions": contradictions,
        "total_questions": len(answer_records),
        "candidate_name": profile.get("name", ""),
        "target_role": profile.get("target_role", ""),
        "answer_scores": [
            {"question": r.get("question_text", "")[:80], "topic": r.get("topic", ""),
             "overall": r.get("satisfaction", {}).get("overall", 0),
             "technical_accuracy": r.get("satisfaction", {}).get("technical_accuracy", 0),
             "depth": r.get("satisfaction", {}).get("depth", 0),
             "communication": r.get("satisfaction", {}).get("communication", 0)}
            for r in answer_records
        ],
    })

    return {"final_report": report_data, "phase": "report"}