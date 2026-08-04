from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.llm import get_fast_llm
from backend.core.utils import parse_json
from backend.core.state import InterviewState

GENERAL_PROMPT = """
You are an expert technical interviewer. Generate exactly ONE technical question on the topic: "{topic}".

Instructions:
- Read the recent conversation below to understand what has already been discussed.
- Do NOT repeat or rephrase any question already asked.
- Build naturally on the candidate's last answer when relevant — maintain conversational flow.
- Difficulty level: {difficulty} (1=basic, 3=intermediate, 5=expert).

Return ONLY a valid JSON object:
{{"question": "your question here"}}
"""

FOLLOW_UP_PROMPT = """
You are an expert technical interviewer. The candidate showed gaps in "{topic}".
Specifically, they missed or weakly covered: "{missing_concept}"

Generate exactly ONE follow-up question targeting ONLY this missing concept.
Do NOT introduce new topics. Stay focused on "{topic}".

Return ONLY a valid JSON object:
{{"question": "your follow-up question here"}}
"""

CONTRADICTION_CLARIFICATION_PROMPT = """
You are an expert technical interviewer. You noticed an inconsistency in the candidate's answers.

Earlier they said: "{earlier}"
But now they said: "{current}"

Generate exactly ONE clarification question that:
- Directly and professionally points out the discrepancy
- Asks them to explain or reconcile the two statements
- Does NOT introduce any new technical topics

Example format: "Earlier you mentioned [X], but just now you said [Y]. Could you clarify this for me?"

Return ONLY a valid JSON object:
{{"question": "your clarification question here"}}
"""

PROJECT_DEEP_DIVE_PROMPT = """
You are an expert technical interviewer. We are doing a deep dive into the candidate's project: "{project_name}".
Current deep dive stage: {stage_name}

Instructions:
- Generate ONE question focusing specifically on the {stage_name} of the project.
- Keep it conversational.

Return ONLY a valid JSON object:
{{"question": "your question here"}}
"""

PROJECT_STAGES = [
    "Architecture & Design",
    "Tech Stack & Tools",
    "Challenges & Trade-offs",
    "Impact & Learnings"
]

def _recent_history(history: list[dict], n: int = 4) -> str:
    recent = history[-n:] if len(history) >= n else history
    lines = []
    for msg in recent:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def generate_question(state: InterviewState) -> Dict[str, Any]:
    phase = state.get("phase", "technical")
    history = state.get("history", [])
    answers = state.get("answers", [])
    num_answers = len(answers)
    next_action = state.get("next_action", "idle")
    
    question_text = ""
    llm = get_fast_llm(temperature=0.6)
    
    # 1. Intro phase
    if phase == "intro":
        if num_answers == 0:
            question_text = "Hi there! Welcome to your interview. Let's start — could you tell me a bit about yourself and what you're looking for in your next role?"
        elif num_answers == 1:
            question_text = "Thank you! Could you walk me through your resume, highlighting your key technical achievements?"
        elif num_answers == 2:
            candidate = state.get("candidate")
            projects = candidate.get("projects", []) if candidate and isinstance(candidate, dict) else []
            project_name = projects[0].get("name", "your project") if projects and isinstance(projects[0], dict) else (projects[0] if projects else "")
            project_hint = f" For instance, your work on {project_name}?" if project_name else ""
            question_text = f"That's great. Let's talk about one of your recent projects.{project_hint} Can you give me an overview?"
        else:
            question_text = "Let's move on to the next part of the interview."
            
        new_history = history + [{"role": "interviewer", "content": question_text}]
        return {
            "current_question": question_text,
            "history": new_history,
            "raw_answer": ""
        }

    # 2. Clarify contradiction
    if next_action == "clarify_contradiction":
        contradictions = state.get("contradictions", [])
        if contradictions:
            latest_contra = contradictions[-1]
            earlier = latest_contra.get("earlier", "") if isinstance(latest_contra, dict) else getattr(latest_contra, "earlier", "")
            current = latest_contra.get("current", "") if isinstance(latest_contra, dict) else getattr(latest_contra, "current", "")
            
            prompt = CONTRADICTION_CLARIFICATION_PROMPT.format(
                earlier=earlier,
                current=current
            )
            response = llm.invoke([SystemMessage(content=prompt)])
            parsed = parse_json(response.content)
            question_text = parsed.get("question", "Could you clarify a contradiction in your previous statements?")
        else:
            question_text = "Could you clarify what you meant earlier?"
            
        new_history = history + [{"role": "interviewer", "content": question_text}]
        return {
            "current_question": question_text,
            "history": new_history,
            "raw_answer": ""
        }

    # 3. Project deep dive
    if phase == "project_deep_dive":
        dive_idx = state.get("project_dive_index", 0)
        project_name = state.get("selected_project", "your project")
        if dive_idx < len(PROJECT_STAGES):
            stage_name = PROJECT_STAGES[dive_idx]
            prompt = PROJECT_DEEP_DIVE_PROMPT.format(
                project_name=project_name,
                stage_name=stage_name
            )
            response = llm.invoke([SystemMessage(content=prompt)])
            parsed = parse_json(response.content)
            question_text = parsed.get("question", f"Could you tell me more about the {stage_name}?")
            new_history = history + [{"role": "interviewer", "content": question_text}]
            return {
                "current_question": question_text,
                "history": new_history,
                "raw_answer": "",
                "project_dive_index": dive_idx + 1
            }
        else:
            question_text = "Let's move on to technical questions."
            new_history = history + [{"role": "interviewer", "content": question_text}]
            return {
                "current_question": question_text,
                "history": new_history,
                "raw_answer": ""
            }

    # 4. Follow-up
    if next_action == "ask_follow_up":
        topic = state.get("current_topic", "general")
        latest_eval = state.get("latest_eval", {})
        missing_topics = latest_eval.get("missing_topics", []) if isinstance(latest_eval, dict) else getattr(latest_eval, "missing_topics", [])
        missing_concept = missing_topics[0] if missing_topics else "the details"
        
        prompt = FOLLOW_UP_PROMPT.format(
            topic=topic,
            missing_concept=missing_concept
        )
        response = llm.invoke([SystemMessage(content=prompt)])
        parsed = parse_json(response.content)
        question_text = parsed.get("question", f"Could you elaborate more on {missing_concept}?")
        
        new_history = history + [{"role": "interviewer", "content": question_text}]
        return {
            "current_question": question_text,
            "history": new_history,
            "raw_answer": ""
        }

    # 5. New technical question (default)
    topic = state.get("current_topic", "general")
    difficulty = state.get("difficulty", 3)
    
    prompt = GENERAL_PROMPT.format(topic=topic, difficulty=difficulty)
    recent_conv = _recent_history(history)
    human_msg = f"Recent conversation:\n{recent_conv}\n\nPlease generate the next question."
    
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=human_msg)
    ])
    parsed = parse_json(response.content)
    question_text = parsed.get("question", "Could you explain a technical concept related to your skills?")
    
    new_history = history + [{"role": "interviewer", "content": question_text}]
    return {
        "current_question": question_text,
        "history": new_history,
        "raw_answer": ""
    }