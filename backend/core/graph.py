# backend/core/graph.py
"""
LangGraph state machine — 6 agent nodes, simplified routing.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from backend.core.state import InterviewState


def _route_entry(state: InterviewState) -> str:
    """Route based on current state when graph is invoked."""
    if state.get("phase") == "report":
        return "report_generation"
    if state.get("raw_answer"):
        return "answer_evaluation"
    if state.get("candidate"):
        return "interview_planning"
    return "resume_analysis"


def _route_after_followup(state: InterviewState) -> str:
    """Decide where to go after the follow-up decision agent."""
    action = state.get("next_action", "advance_topic")
    if action in ("ask_follow_up", "clarify_contradiction"):
        return "question_generation"
    if action == "generate_report":
        return "report_generation"
    return "interview_planning"


def _route_after_planning(state: InterviewState) -> str:
    """After planning, either generate a question or finish."""
    if state.get("phase") in ("wrap_up", "report"):
        return "report_generation"
    return "question_generation"


def build_graph() -> StateGraph:
    from backend.agents.resume_analysis import analyze_resume
    from backend.agents.interview_planning import plan_interview
    from backend.agents.question_generation import generate_question
    from backend.agents.answer_evaluation import evaluate_answer
    from backend.agents.followup_decision import make_followup_decision
    from backend.agents.report_generation import generate_report

    graph = StateGraph(InterviewState)

    # ── Nodes ──
    graph.add_node("resume_analysis", analyze_resume)
    graph.add_node("interview_planning", plan_interview)
    graph.add_node("question_generation", generate_question)
    graph.add_node("answer_evaluation", evaluate_answer)
    graph.add_node("followup_decision", make_followup_decision)
    graph.add_node("report_generation", generate_report)

    # ── Entry routing ──
    graph.add_conditional_edges(START, _route_entry, {
        "resume_analysis": "resume_analysis",
        "answer_evaluation": "answer_evaluation",
        "interview_planning": "interview_planning",
        "report_generation": "report_generation",
    })

    # ── Fixed edges ──
    graph.add_edge("resume_analysis", "interview_planning")
    graph.add_edge("question_generation", END)
    graph.add_edge("answer_evaluation", "followup_decision")
    graph.add_edge("report_generation", END)

    # ── Conditional edges ──
    graph.add_conditional_edges("interview_planning", _route_after_planning, {
        "question_generation": "question_generation",
        "report_generation": "report_generation",
    })

    graph.add_conditional_edges("followup_decision", _route_after_followup, {
        "question_generation": "question_generation",
        "interview_planning": "interview_planning",
        "report_generation": "report_generation",
    })

    return graph.compile(checkpointer=None)


# Compiled once, shared across all sessions
interview_graph = build_graph()
