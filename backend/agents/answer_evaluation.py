import time
from typing import Dict, Any
from backend.core.utils import parse_json
from backend.core.llm import get_main_llm
from backend.core.state import InterviewState, EvaluationResult, AnswerRecord, Contradiction

CONTRADICTION_PROMPT = """
You are a logical consistency checker. Compare the candidate's CURRENT answer against their PREVIOUS answers and RESUME.

Step 1: Analyze the exact context of the statements.
Step 2: Check against the contradiction categories and anti-patterns below.
Step 3: If a true contradiction is found, output the evidence and reason.

### Contradiction Categories (FLAG THESE):
A. Factual Project Contradiction: Two mutually exclusive, simultaneous claims about the EXACT SAME phase of the EXACT SAME project.
B. Knowledge Persistence: Claiming to have used/built with a specific technology, but later explicitly denying knowing what it is (e.g., "What is FastAPI? I don't know.").
C. Resume Contradiction: Explicitly denying knowledge or experience with a core skill/project that is prominently listed on their uploaded resume.

### Anti-Patterns (DO NOT FLAG THESE):
D. Evolution / Temporal Context: Do NOT flag inconsistencies explained by migrations, technology replacement, project evolution, different project phases, different roles/components/projects, or learning something after an earlier statement.
E. Uncertainty & Corrections: Distinguish between "I think" and "We definitely". If a candidate expresses uncertainty and later corrects themselves, or admits partial knowledge/forgetting, do NOT flag it.
F. Resume Hierarchy & Contextual Clarification: Explicit candidate statement > explicit project context > resume > inferred knowledge. If a candidate clarifies their resume (e.g., "React is on my resume but I didn't write the frontend"), do NOT flag it. The resume is evidence of a claim, not absolute proof of personal contribution.

When in doubt, DO NOT FLAG a contradiction. Only flag if it is an egregious, undeniable violation of the categories above.

Return ONLY a valid JSON object matching this schema:
{
  "found": true or false,
  "category": "A, B, C, or null",
  "earlier_statement": "The exact quote from previous answers or resume",
  "current_statement": "The exact quote from the current answer",
  "reason": "String explaining the contradiction"
}
"""

TECHNICAL_EVALUATION_PROMPT = """
You are a Senior Staff Technical Interviewer evaluating a candidate's answer.

Grade the answer using this rubric (Total out of 10):
1. Technical Correctness (0-4 points): Are the core concepts accurate?
2. Depth & Nuance (0-3 points): Did they mention trade-offs, edge cases, or real-world examples?
3. Clarity & Structure (0-3 points): Is the answer logically structured and easy to follow?

Extract exact missing concepts if they failed to address core parts of the question.

Return ONLY a valid JSON object matching exactly this schema, ensuring the score is an INTEGER:
{"score": 8, "summary": "brief evaluation", "strengths": ["concept A"], "missing_topics": ["concept X"]}
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
    contradiction_found = False
    
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
            candidate = state.get("candidate") or {}
            resume_context = ""
            if candidate:
                resume_context = f"Resume Skills: {candidate.get('skills', [])}\nResume Projects: {candidate.get('projects', [])}"
            
            contra_user_prompt = f"{resume_context}\n\nPrevious Q&A:\n{prev_answers_text}\n\nCurrent Q: {current_question}\nCurrent A: {raw_answer}"
            contra_resp = llm.invoke([
                {"role": "system", "content": CONTRADICTION_PROMPT}, 
                {"role": "user", "content": contra_user_prompt}
            ])
            parsed_contra = parse_json(contra_resp.content if hasattr(contra_resp, "content") else contra_resp)
            
            if parsed_contra.get("found"):
                contradiction_found = True
                
                new_cat = parsed_contra.get("category", "Unknown")
                new_curr = parsed_contra.get("current_statement", "")
                
                is_dup = any(c.get("category") == new_cat and c.get("current_statement") == new_curr for c in contradictions)
                
                if not is_dup:
                    contradictions.append({
                        "category": new_cat,
                        "earlier_statement": parsed_contra.get("earlier_statement", ""),
                        "current_statement": new_curr,
                        "reason": parsed_contra.get("reason", ""),
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