from backend.core.llm import get_fast_llm
from backend.core.utils import parse_json
from backend.core.config import settings

PLANNING_PROMPT = """You are a technical interview planner.
Based on the candidate's role and skills, suggest a list of 4-5 technical topics to assess.
Return JSON ONLY with this exact structure:
{
  "topics": ["topic1", "topic2", "topic3", "topic4"]
}"""

def plan_interview(state: dict) -> dict:
    phase = state.get("phase", "intro")
    topics = state.get("topics", [])
    topic_questions = state.get("topic_questions", {})
    answers = state.get("answers", [])
    latest_eval = state.get("latest_eval")
    difficulty = state.get("difficulty", 2)
    current_topic = state.get("current_topic")
    selected_project = state.get("selected_project")
    project_dive_index = state.get("project_dive_index", 0)

    updates = {}

    # 2. If no topics, generate them (fallback)
    if not topics:
        candidate = state.get("candidate", {})
        skills = ", ".join(candidate.get("skills", []))
        role = candidate.get("target_role", "Software Engineer")
        
        llm = get_fast_llm()
        response = llm.invoke([
            {"role": "system", "content": PLANNING_PROMPT},
            {"role": "user", "content": f"Role: {role}\nSkills: {skills}"}
        ])
        parsed = parse_json(response.content)
        topics = parsed.get("topics", ["Data Structures", "System Design", "Problem Solving"])
        updates["topics"] = topics

    # 1. Initialize topic_questions if empty
    if not topic_questions and topics:
        topic_questions = {t: 0 for t in topics}
        updates["topic_questions"] = topic_questions
        updates["current_topic"] = "Intro"
        updates["phase"] = "intro"
        return updates

    # 3. Intro phase, < 3 answers
    if phase == "intro" and len(answers) < 3:
        updates["current_topic"] = "Intro"
        return updates
        
    # 4. Transition from intro
    if phase == "intro" and len(answers) >= 3:
        if selected_project:
            phase = "project_deep_dive"
            updates["phase"] = phase
        else:
            phase = "technical"
            updates["phase"] = phase
            
    # 5. Project Deep Dive
    if phase == "project_deep_dive":
        if project_dive_index >= 3:
            phase = "technical"
            updates["phase"] = phase
        else:
            updates["current_topic"] = f"Project: {selected_project}"
            updates["difficulty"] = 3
            return updates

    # 6. Technical Phase
    if phase == "technical":
        # Adapt difficulty based on latest_eval
        if latest_eval:
            score = latest_eval.get("score", 5.0)
            if score >= 7.8 and difficulty < 5:
                difficulty += 1
                updates["difficulty"] = difficulty
            elif score <= 4.2 and difficulty > 1:
                difficulty -= 1
                updates["difficulty"] = difficulty

        # Update current topic questions count
        if current_topic in topic_questions and latest_eval:
            topic_questions[current_topic] = topic_questions.get(current_topic, 0) + 1
            updates["topic_questions"] = topic_questions
            
        # Check completion and find next incomplete topic
        next_topic = None
        for t in topics:
            if topic_questions.get(t, 0) < settings.MAX_QUESTIONS_PER_TOPIC:
                next_topic = t
                break

        if next_topic is None:
            updates["phase"] = "report"
        else:
            if next_topic != current_topic:
                updates["current_topic"] = next_topic
                updates["follow_ups"] = 0
            else:
                updates["current_topic"] = next_topic

    return updates