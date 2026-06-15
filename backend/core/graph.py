# backend/core/graph.py
from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from backend.core.state import InterviewState


def _route_entry(state: InterviewState) -> str:
    # Handle skip actions and end interview overrides
    skip = state.get("skip_action")
    if skip:
        if skip in ("skip_followup", "skip_topic"):
            return "interview_planning"
        if skip == "force_report":
            return "report_generation"

    # If a raw answer is present, we route to evaluation. Otherwise (upload), to resume analysis.
    if state.get("raw_answer"):
        return "answer_evaluation"
    return "resume_analysis"


def _route_after_followup_decision(state: InterviewState) -> str:
    action = state.get("next_action", "advance_topic")
    routes = {
        "ask_follow_up":     "question_generation",
        "deepen_difficulty": "question_generation",
        "project_deep_dive": "question_generation",
        "advance_topic":     "interview_planning",
        "wrap_up":           "interview_planning",
        "generate_report":   "report_generation",
    }
    return routes.get(action, "interview_planning")


def _route_after_planning(state: InterviewState) -> str:
    phase = state.get("phase", "technical")
    if phase in ("wrap_up", "report"):
        return "report_generation"
    return "question_generation"


def build_graph() -> StateGraph:
    # Import agents here to avoid circular imports at module level
    from backend.agents.resume_analysis   import resume_analysis_agent
    from backend.agents.interview_planning import interview_planning_agent
    from backend.agents.question_generation import question_generation_agent
    from backend.agents.answer_evaluation  import answer_evaluation_agent
    from backend.agents.followup_decision  import followup_decision_agent
    from backend.agents.report_generation  import report_generation_agent

    graph = StateGraph(InterviewState)

    # ── Register nodes ───────────────────────────────────────────────────────
    graph.add_node("resume_analysis",    resume_analysis_agent)
    graph.add_node("interview_planning", interview_planning_agent)
    graph.add_node("question_generation", question_generation_agent)
    graph.add_node("answer_evaluation",  answer_evaluation_agent)
    graph.add_node("followup_decision",  followup_decision_agent)
    graph.add_node("report_generation",  report_generation_agent)

    # ── Entry ────────────────────────────────────────────────────────────────
    graph.add_conditional_edges(
        START,
        _route_entry,
        {
            "resume_analysis": "resume_analysis",
            "answer_evaluation": "answer_evaluation",
        }
    )

    # ── Fixed edges ──────────────────────────────────────────────────────────
    graph.add_edge("resume_analysis",    "interview_planning")
    graph.add_edge("question_generation", END)  # Halt graph and return generated question to client
    graph.add_edge("answer_evaluation",  "followup_decision")
    graph.add_edge("report_generation",  END)

    # ── Conditional edges ────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "interview_planning",
        _route_after_planning,
        {
            "question_generation": "question_generation",
            "report_generation":   "report_generation",
        },
    )

    graph.add_conditional_edges(
        "followup_decision",
        _route_after_followup_decision,
        {
            "question_generation": "question_generation",
            "interview_planning":  "interview_planning",
            "report_generation":   "report_generation",
        },
    )

    return graph.compile(checkpointer=None)


# Compiled once, shared across all sessions
interview_graph = build_graph()
