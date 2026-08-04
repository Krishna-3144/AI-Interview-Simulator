from typing import Dict, Any
import json
from backend.core.utils import parse_json
from backend.core.llm import get_main_llm
from backend.core.state import InterviewState

REPORT_PROMPT = """
You are an expert technical interviewer writing a final evaluation report for a candidate.

Given the interview transcript, contradictions, and confidence timeline, provide a structured evaluation.

Return ONLY a valid JSON object:
{
  "technical_score": 8.5,
  "communication_score": 9.0,
  "grammar_score": 8.0,
  "strong_areas": ["topic A", "topic B"],
  "overall_summary": "Detailed summary..."
}
"""

def generate_report(state: InterviewState) -> Dict[str, Any]:
    answers = state.get("answers", [])
    contradictions = state.get("contradictions", [])
    confidence_timeline = state.get("confidence_timeline", [])
    candidate = state.get("candidate", {})
    candidate_name = candidate.get("name", "Unknown") if candidate else "Unknown"
    target_role = candidate.get("target_role", "Unknown") if candidate else "Unknown"

    transcript = [
        {
            "question": a["question"],
            "answer": a["answer"],
            "topic": a["topic"],
            "score": a.get("evaluation", {}).get("score", 0.0)
        }
        for a in answers
    ]

    llm = get_main_llm(temperature=0.2)
    
    user_prompt = f"""
Transcript:
{json.dumps(transcript, indent=2)}

Contradictions:
{json.dumps(contradictions, indent=2)}

Confidence Timeline:
{json.dumps(confidence_timeline, indent=2)}
"""

    resp = llm.invoke([
        {"role": "system", "content": REPORT_PROMPT},
        {"role": "user", "content": user_prompt}
    ])
    
    parsed_report = parse_json(resp.content if hasattr(resp, "content") else resp)
    
    report_data = {
        "candidate_name": candidate_name,
        "target_role": target_role,
        "total_questions": len(answers),
        "technical_score": parsed_report.get("technical_score", 0.0),
        "communication_score": parsed_report.get("communication_score", 0.0),
        "grammar_score": parsed_report.get("grammar_score", 0.0),
        "strong_areas": parsed_report.get("strong_areas", []),
        "overall_summary": parsed_report.get("overall_summary", ""),
        "contradictions": contradictions
    }

    return {
        "final_report": report_data,
        "phase": "report"
    }