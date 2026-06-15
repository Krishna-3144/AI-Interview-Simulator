# backend/agents/answer_evaluation.py
from __future__ import annotations
import re, json, time
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.state import InterviewState, SatisfactionScore, AnswerRecord
from backend.core.llm import get_main_llm
from backend.services import memory_service

_llm = get_main_llm(temperature=0.1)

EVALUATION_PROMPT = """
You are an expert technical interviewer evaluating a candidate's answer.
Also check if the answer contradicts any provided previous answers in `previous_answers_context`. Only flag genuine logical contradictions, not just different phrasings.

Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Use this exact structure:
{
  "technical_accuracy": 0.0,
  "depth": 0.0,
  "communication": 0.0,
  "confidence": 0.0,
  "consistency": 0.0,
  "overall": 0.0,
  "reasoning": "specific explanation referencing actual content",
  "technical_gaps": ["missing concept X", "incorrect assumption Y"],
  "contradiction": {
    "contradiction_found": false,
    "earlier_statement": "the specific earlier statement contradicted, if found",
    "current_statement": "the specific current statement contradicting, if found",
    "explanation": "why they contradict, if found"
  }
}
Score each 0.0 to 1.0. Overall = technical*0.35 + depth*0.25 + communication*0.2 + confidence*0.1 + consistency*0.1
Be specific in reasoning — reference actual content of the answer.
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

def answer_evaluation_agent(state: InterviewState) -> dict:
    answer = state.get("raw_answer", "")
    if not answer:
        return {}

    question = state.get("current_question", "")
    question_id = state.get("current_question_id", "")
    topic = state.get("current_topic", "General")
    difficulty = state.get("current_difficulty", 2)
    session_id = state.get("session_id", "")
    confidence_metrics = state.get("latest_confidence")
    history = list(state.get("conversation_history", []))
    follow_up_depth = state.get("follow_up_depth", 0)

    audio_confidence = confidence_metrics.get("confidence_score") if confidence_metrics else None

    # Retrieve similar answers to pass as context for contradiction checking
    similar = memory_service.search_similar(session_id, answer, n_results=3)
    close = [s for s in similar if s["distance"] < 0.35]
    prior_text = ""
    if close:
        prior_text = "\n---\n".join(
            f"Topic: {s['metadata'].get('topic','?')}\n{s['document']}" for s in close
        )

    eval_payload = {
        "question": question,
        "answer": answer,
        "topic": topic,
        "difficulty": difficulty,
        "audio_confidence_score": audio_confidence,
    }
    if prior_text:
        eval_payload["previous_answers_context"] = prior_text[:2000]

    messages = [
        SystemMessage(content=EVALUATION_PROMPT),
        HumanMessage(content=json.dumps(eval_payload, separators=(',', ':'))),
    ]
    scores = _parse(_llm.invoke(messages).content)

    conf = scores.get("confidence", 0.5)
    if audio_confidence is not None:
        conf = round(conf * 0.4 + audio_confidence * 0.6, 3)

    overall = round(
        scores.get("technical_accuracy", 0) * 0.35
        + scores.get("depth", 0) * 0.25
        + scores.get("communication", 0) * 0.20
        + conf * 0.10
        + scores.get("consistency", 0) * 0.10,
        3,
    )

    satisfaction = SatisfactionScore(
        technical_accuracy=scores.get("technical_accuracy", 0),
        depth=scores.get("depth", 0),
        communication=scores.get("communication", 0),
        confidence=conf,
        consistency=scores.get("consistency", 0),
        overall=overall,
        reasoning=scores.get("reasoning", ""),
        technical_gaps=scores.get("technical_gaps", []),
    )

    contradictions = list(state.get("contradictions_detected", []))
    contradiction_res = scores.get("contradiction")
    if contradiction_res and contradiction_res.get("contradiction_found"):
        contradiction_res["question_id"] = question_id
        contradictions.append(contradiction_res)

    memory_service.store_answer(session_id, question_id, question, answer, topic)

    history.append({"role": "candidate", "content": answer, "timestamp": time.time()})

    record = AnswerRecord(
        question_id=question_id,
        question_text=question,
        topic=topic,
        difficulty=difficulty,
        answer_text=answer,
        satisfaction=satisfaction,
        confidence_metrics=confidence_metrics,
        follow_up_count=follow_up_depth,
        timestamp=time.time(),
    )

    return {
        "latest_satisfaction": satisfaction,
        "answer_records": list(state.get("answer_records", [])) + [record],
        "contradictions_detected": contradictions,
        "conversation_history": history,
    }