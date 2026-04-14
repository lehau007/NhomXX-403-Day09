"""
graph.py - Supervisor Orchestrator

Sprint 2 for Supervisor/Integration:
- keep Supervisor in charge of routing only
- integrate retrieval.py and synthesis.py into the main graph
- keep policy_tool as a placeholder until the dedicated Sprint 2/3 work lands
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv

from workers.retrieval import run as retrieval_run
from workers.synthesis import run as synthesis_run


load_dotenv()


RouteName = Literal["retrieval_worker", "policy_tool_worker", "human_review"]


class AgentState(TypedDict):
    task: str
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool
    retrieved_chunks: list
    retrieved_sources: list
    policy_result: dict
    mcp_tools_used: list
    final_answer: str
    sources: list
    confidence: float
    history: list
    workers_called: list
    worker_io_logs: list
    supervisor_route: str
    latency_ms: Optional[int]
    run_id: str
    timestamp: str
    retrieval_top_k: int
    llm_profiles: dict


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record_history(state: AgentState, message: str) -> None:
    state["history"].append(message)


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _get_role_llm_profile(role: str, default_provider: str, default_model: str) -> dict:
    role_key = role.upper()
    return {
        "provider": os.getenv(f"{role_key}_PROVIDER", default_provider),
        "model": os.getenv(f"{role_key}_MODEL", default_model),
    }


def get_llm_profiles() -> dict:
    return {
        "supervisor": _get_role_llm_profile("supervisor", "openai", "gpt-4o-mini"),
        "synthesis": _get_role_llm_profile("synthesis", "groq", "openai/gpt-oss-120b"),
        "retrieval": _get_role_llm_profile(
            "retrieval", "google", "gemini-embedding-2-preview"
        ),
        "policy": _get_role_llm_profile("policy", "google", "gemini-1.5-flash"),
    }


def make_initial_state(task: str) -> AgentState:
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "worker_io_logs": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}",
        "timestamp": _utc_now_iso(),
        "retrieval_top_k": int(os.getenv("RETRIEVAL_TOP_K", "3")),
        "llm_profiles": get_llm_profiles(),
    }


def supervisor_node(state: AgentState) -> AgentState:
    task = state["task"].strip()
    task_lower = task.lower()
    supervisor_profile = state["llm_profiles"]["supervisor"]
    _record_history(state, f"[supervisor] received task: {task[:120]}")

    policy_keywords = [
        "refund",
        "hoan tien",
        "hoan tra",
        "flash sale",
        "license",
        "subscription",
        "policy",
        "cap quyen",
        "access",
        "access level",
        "level 3",
        "admin",
        "contractor",
    ]
    retrieval_keywords = [
        "sla",
        "ticket",
        "p1",
        "p2",
        "escalation",
        "incident",
        "helpdesk",
        "faq",
        "quy trinh",
        "process",
        "response time",
    ]
    risk_keywords = [
        "emergency",
        "khan cap",
        "urgent",
        "2am",
        "after hours",
        "contractor",
        "level 3",
        "admin",
        "production down",
        "sev1",
    ]
    ambiguous_error_markers = ["err-", "error code", "ma loi", "unknown error"]

    matched_policy = _contains_any(task_lower, policy_keywords)
    matched_retrieval = _contains_any(task_lower, retrieval_keywords)
    matched_risk = _contains_any(task_lower, risk_keywords)
    matched_ambiguous = _contains_any(task_lower, ambiguous_error_markers)

    route: RouteName = "retrieval_worker"
    needs_tool = False
    risk_high = bool(matched_risk)
    reason_parts: list[str] = []

    if matched_ambiguous and not matched_retrieval and not matched_policy:
        route = "human_review"
        risk_high = True
        reason_parts.append(
            "ambiguous error marker without enough retrieval/policy context"
        )
    elif matched_policy:
        route = "policy_tool_worker"
        needs_tool = True
        reason_parts.append(f"matched policy/access keywords: {matched_policy}")
    elif matched_retrieval:
        route = "retrieval_worker"
        reason_parts.append(f"matched retrieval keywords: {matched_retrieval}")
    else:
        route = "retrieval_worker"
        reason_parts.append("defaulted to retrieval for knowledge lookup")

    if matched_risk:
        reason_parts.append(f"risk_high because of: {matched_risk}")
    if route == "policy_tool_worker" and matched_retrieval:
        reason_parts.append(
            "policy route kept priority because question mixes policy with retrieval"
        )

    route_reason = " | ".join(reason_parts)
    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["worker_io_logs"].append(
        {
            "worker": "supervisor",
            "input": {"task": task, "llm_profile": supervisor_profile},
            "output": {
                "supervisor_route": route,
                "route_reason": route_reason,
                "needs_tool": needs_tool,
                "risk_high": risk_high,
            },
            "error": None,
        }
    )
    _record_history(
        state,
        "[supervisor] "
        f"provider={supervisor_profile['provider']} "
        f"model={supervisor_profile['model']} "
        f"route={route} needs_tool={needs_tool} risk_high={risk_high}",
    )
    return state


def route_decision(state: AgentState) -> RouteName:
    route = state.get("supervisor_route", "retrieval_worker")
    if route in {"retrieval_worker", "policy_tool_worker", "human_review"}:
        return route  # type: ignore[return-value]
    return "retrieval_worker"


def human_review_node(state: AgentState) -> AgentState:
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    state["worker_io_logs"].append(
        {
            "worker": "human_review",
            "input": {"task": state["task"], "route_reason": state["route_reason"]},
            "output": {
                "approved": True,
                "next_route": "retrieval_worker",
                "note": "Sprint 2 placeholder review auto-approves follow-up retrieval",
            },
            "error": None,
        }
    )
    _record_history(state, "[human_review] placeholder HITL triggered")
    state["route_reason"] += " | human review placeholder approved follow-up retrieval"
    return state


def retrieval_worker_node(state: AgentState) -> AgentState:
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """
    Sprint 2 integration scope for Hau:
    policy_tool is not the focus here, so keep a lightweight placeholder
    while still allowing synthesis.py to consume policy_result consistently.
    """
    state["workers_called"].append("policy_tool_worker")
    if not state["retrieved_chunks"]:
        state = retrieval_run(state)

    task_lower = state["task"].lower()
    exceptions_found = []
    policy_applies = True
    policy_name = "refund_policy_v4"
    policy_sources = ["policy_refund_v4.txt"]
    explanation = "Sprint 2 placeholder policy integration until the policy worker is finalized."

    if "flash sale" in task_lower:
        policy_applies = False
        exceptions_found.append(
            {
                "type": "flash_sale_exception",
                "rule": "Flash Sale orders are not eligible for refund.",
                "source": "policy_refund_v4.txt",
            }
        )
    if "license" in task_lower or "subscription" in task_lower:
        policy_applies = False
        exceptions_found.append(
            {
                "type": "digital_product_exception",
                "rule": "Digital products and subscriptions are not eligible for refund after activation.",
                "source": "policy_refund_v4.txt",
            }
        )
    if "access" in task_lower or "admin" in task_lower or "level 3" in task_lower:
        policy_name = "access_control_sop"
        policy_sources = ["access_control_sop.txt"]
        explanation = "Sprint 2 access-control placeholder policy integration."

    state["policy_result"] = {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": policy_sources,
        "policy_version_note": "",
        "explanation": explanation,
    }
    state["worker_io_logs"].append(
        {
            "worker": "policy_tool_worker",
            "input": {
                "task": state["task"],
                "needs_tool": state["needs_tool"],
                "chunks_count": len(state["retrieved_chunks"]),
                "llm_profile": state["llm_profiles"]["policy"],
            },
            "output": {
                "policy_applies": policy_applies,
                "exceptions_count": len(exceptions_found),
                "policy_name": policy_name,
            },
            "error": None,
        }
    )
    _record_history(
        state,
        f"[policy_tool_worker] placeholder policy result prepared with policy_applies={policy_applies}",
    )
    return state


def synthesis_worker_node(state: AgentState) -> AgentState:
    return synthesis_run(state)


class SimpleGraph:
    def invoke(self, state: AgentState) -> AgentState:
        start = time.time()

        state = supervisor_node(state)
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            state = retrieval_worker_node(state)
        elif route == "policy_tool_worker":
            state = policy_tool_worker_node(state)
        else:
            state = retrieval_worker_node(state)

        state = synthesis_worker_node(state)
        state["latency_ms"] = int((time.time() - start) * 1000)
        _record_history(state, f"[graph] completed in {state['latency_ms']}ms")
        return state


def build_graph() -> SimpleGraph:
    return SimpleGraph()


_graph = build_graph()


def run_graph(task: str) -> AgentState:
    return _graph.invoke(make_initial_state(task))


def save_trace(state: AgentState, output_dir: Optional[str] = None) -> str:
    output_dir = output_dir or os.getenv("TRACE_OUTPUT_DIR", "./artifacts/traces")
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{state['run_id']}.json")
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    return filename


if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab - Sprint 2 Supervisor Integration")
    print("=" * 60)

    test_queries = [
        "SLA ticket P1 la bao lau?",
        "Quy trinh escalation cho ticket P1 la gi?",
        "Khach hang Flash Sale yeu cau refund vi san pham loi - duoc khong?",
    ]

    for query in test_queries:
        result = run_graph(query)
        trace_file = save_trace(result)
        print(f"\nQuery      : {query}")
        print(f"Route      : {result['supervisor_route']}")
        print(f"Reason     : {result['route_reason']}")
        print(f"Workers    : {result['workers_called']}")
        print(f"Sources    : {result['sources']}")
        print(f"Confidence : {result['confidence']}")
        print(f"Answer     : {result['final_answer']}")
        print(f"Trace      : {trace_file}")

    print("\nSprint 2 integration smoke test completed.")
