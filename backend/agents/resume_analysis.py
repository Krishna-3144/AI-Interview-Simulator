import fitz
from backend.core.llm import get_fast_llm
from backend.core.utils import parse_json

def _extract_pdf_text(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

SYSTEM_PROMPT = """You are an expert technical recruiter analyzing a candidate's resume.
Extract the candidate's profile and plan the technical interview topics.
Return JSON ONLY with this exact structure:
{
  "candidate": {
    "name": "string",
    "email": "string",
    "skills": ["merged list of skills and technologies"],
    "projects": [{"name": "string", "description": "string", "tech_stack": ["string"]}],
    "experience": [{"company": "string", "role": "string", "duration": "string", "description": "string"}],
    "education": [{"degree": "string", "institution": "string", "year": "string"}],
    "target_role": "string"
  },
  "topics": ["topic1", "topic2", "topic3", "topic4"],
  "planning_rationale": "string explaining why these topics were chosen"
}"""

def analyze_resume(state: dict) -> dict:
    resume_path = state.get("resume_path")
    if not resume_path:
        return {}

    resume_text = _extract_pdf_text(resume_path)
    
    llm = get_fast_llm()
    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Resume Text:\n{resume_text}"}
    ])
    
    parsed_data = parse_json(response.content)
    
    candidate = parsed_data.get("candidate", {})
    topics = parsed_data.get("topics", [])
    
    projects = candidate.get("projects", [])
    selected_project = projects[0]["name"] if projects else None

    return {
        "candidate": candidate,
        "topics": topics,
        "topic_questions": {},
        "answers": [],
        "history": [],
        "confidence_timeline": [],
        "follow_ups": 0,
        "difficulty": 2,
        "next_action": "idle",
        "phase": "intro",
        "contradiction_found": False,
        "contradictions": [],
        "project_dive_index": 0,
        "resume_path": None,
        "selected_project": selected_project
    }