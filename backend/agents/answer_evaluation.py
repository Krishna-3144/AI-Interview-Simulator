import time
from typing import Dict, Any
from backend.core.utils import parse_json
from backend.core.llm import get_main_llm
from backend.core.state import InterviewState, EvaluationResult, AnswerRecord, Contradiction

CONTRADICTION_PROMPT = """
You are a logical consistency checker. Compare the candidate's CURRENT answer against their PREVIOUS answers.

Flag a contradiction ONLY if:
- The candidate makes two INCOMPATIBLE statements about the SAME specific thing (same project, same tool, same experience)
- Example: "I used PostgreSQL in my chat app" earlier vs "I used MySQL in my chat app" now -> CONTRADICTION
- Example: "I have 2 years of Python experience" earlier vs "I've never used Python" now -> CONTRADICTION

Do NOT flag as contradiction:
- Different details about DIFFERENT projects (e.g., "used 10 agents in Project A" vs "used 1 agent in Project B")
- Elaborating or expanding on earlier points
- Using different but compatible terminology
- Giving different numbers for different contexts
- Opinions or preferences that naturally evolve during conversation

Return ONLY a valid JSON object:
{"found": false, "earlier": "", "current": ""}

If found is true, fill earlier and current with the specific contradicting statements.
"""

TECHNICAL_EVALUATION_PROMPT = """
You are an expert technical interviewer evaluating a candidate's answer.

Score the answer out of 10.0 based on:
- Technical accuracy and correctness
- Depth of understanding (examples, edge cases, tradeoffs)
- Clarity of explanation

Return ONLY a valid JSON object:
{"score": 8.4, "summary": "brief evaluation", "strengths": ["concept A"], "missing_topics": ["concept X"]}
"""

def evaluate_answer(state: InterviewState) -> Dict[str, Any]:
    phase = state.get("phase", "intro")
    raw_answer = state.get("raw_answer", "")
    current_question = state.get("current_question", "")
    current_topic = state.get("current_topic", "")
    difficulty = state.get("difficulty", 1)
    answers = state.get("answers", [])
    contradictions = state.get("contradictions", [])
    history = state.get("history", [])

    if not raw_answer:
        return {}

    llm = get_main_llm(temperature=0.1)
    eval_result: EvaluationResult
    selected_project = state.get("selected_project")
    contradiction_found = state.get("contradiction_found", False)
    
    is_q3 = len(answers) == 2

    if phase == "intro":
        eval_result = {
            "score": 10.0,
            "summary": "Intro response",
            "strengths": [],
            "missing_topics": []
        }
        if is_q3:
            selected_project = raw_answer.strip()
    else:
        # 1. Grade the answer
        eval_sys_prompt = TECHNICAL_EVALUATION_PROMPT
        eval_user_prompt = f"Question: {current_question}\nCandidate Answer: {raw_answer}\nEvaluate."
        eval_resp = llm.invoke([
            {"role": "system", "content": eval_sys_prompt}, 
            {"role": "user", "content": eval_user_prompt}
        ])
        parsed_eval = parse_json(eval_resp.content if hasattr(eval_resp, "content") else eval_resp)
        eval_result = {
            "score": float(parsed_eval.get("score", 5.0)),
            "summary": parsed_eval.get("summary", ""),
            "strengths": parsed_eval.get("strengths", []),
            "missing_topics": parsed_eval.get("missing_topics", [])
        }

        # 2. Check for contradiction if there are previous answers
        if answers:
            prev_answers_text = "\n".join([f"Q: {a['question']}\nA: {a['answer']}" for a in answers])
            contra_user_prompt = f"Previous Q&A:\n{prev_answers_text}\n\nCurrent Q: {current_question}\nCurrent A: {raw_answer}"
            contra_resp = llm.invoke([
                {"role": "system", "content": CONTRADICTION_PROMPT}, 
                {"role": "user", "content": contra_user_prompt}
            ])
            parsed_contra = parse_json(contra_resp.content if hasattr(contra_resp, "content") else contra_resp)
            
            if parsed_contra.get("found"):
                contradiction_found = True
                contradictions.append({
                    "earlier": parsed_contra.get("earlier", ""),
                    "current": parsed_contra.get("current", ""),
                    "topic": current_topic or ""
                })

    # 4. Build AnswerRecord
    record: AnswerRecord = {
        "question": current_question,
        "answer": raw_answer,
        "topic": current_topic or "",
        "difficulty": difficulty,
        "evaluation": eval_result,
        "timestamp": time.time()
    }
    answers.append(record)

    # 5. Append to history
    history.append({
        "role": "candidate",
        "content": raw_answer
    })

    updates = {
        "answers": answers,
        "history": history,
        "latest_eval": eval_result,
        "contradictions": contradictions,
        "contradiction_found": contradiction_found
    }
    if phase == "intro" and is_q3:
        updates["selected_project"] = selected_project

    return updates