"""
graph.py - Supervisor Orchestrator

Sprint 2 integration:
- Supervisor decides routing only
- Retrieval, policy, and synthesis logic live in worker modules
- Routing follows contracts/worker_contracts.yaml as closely as possible
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv

from workers.policy_tool import run as policy_tool_run
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


def _llm_supervisor_route(task: str, llm_profile: dict) -> tuple[RouteName, str, bool, bool] | None:
    """
    Optional LLM routing for higher-quality supervision.
    Falls back to keyword routing whenever the provider or network is unavailable.
    """
    provider = llm_profile.get("provider", "openai").lower()
    model = llm_profile.get("model", "gpt-4o-mini")

    if provider != "openai":
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=3.0)
        prompt = (
            "You are a supervisor router for a multi-agent IT helpdesk system.\n"
            "Choose exactly one route from: retrieval_worker, policy_tool_worker, human_review.\n"
            "Use policy_tool_worker for refund, flash sale, license, access level, permission tasks.\n"
            "Use retrieval_worker for P1, SLA, ticket, escalation, incident questions.\n"
            "Use human_review for ambiguous error-code issues without enough context.\n"
            "Return strict JSON with keys: route, needs_tool, risk_high, route_reason."
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=120,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": task},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        route = data.get("route")
        if route not in {"retrieval_worker", "policy_tool_worker", "human_review"}:
            return None
        return (
            route,
            data.get("route_reason", "llm-based routing"),
            bool(data.get("needs_tool", route == "policy_tool_worker")),
            bool(data.get("risk_high", False)),
        )
    except Exception:
        return None


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
    """
    Routing aligned to contracts/worker_contracts.yaml:
    1. refund/refund-policy/access-level style questions -> policy_tool_worker
    2. P1/SLA/ticket/escalation/incident -> retrieval_worker
    3. ambiguous ERR-* without policy/retrieval context -> human_review
    4. default -> retrieval_worker
    """
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
        "license key",
        "subscription",
        "cap quyen",
        "access level",
        "access",
        "level 3",
        "permission",
        "quyen han",
    ]
    retrieval_keywords = [
        "p1",
        "sla",
        "ticket",
        "escalation",
        "incident",
        "su co",
        "helpdesk",
        "faq",
    ]
    risk_keywords = [
        "emergency",
        "khan cap",
        "urgent",
        "2am",
        "after hours",
        "production down",
        "sev1",
    ]
    ambiguous_error_markers = ["err-", "error code", "ma loi", "unknown error"]

    matched_policy = _contains_any(task_lower, policy_keywords)
    matched_retrieval = _contains_any(task_lower, retrieval_keywords)
    matched_risk = _contains_any(task_lower, risk_keywords)
    matched_ambiguous = _contains_any(task_lower, ambiguous_error_markers)

    llm_routing = _llm_supervisor_route(task, supervisor_profile)
    if llm_routing is not None:
        route, route_reason, needs_tool, risk_high = llm_routing
        state["supervisor_route"] = route
        state["route_reason"] = f"llm_route | {route_reason}"
        state["needs_tool"] = needs_tool
        state["risk_high"] = risk_high
        state["worker_io_logs"].append(
            {
                "worker": "supervisor",
                "input": {"task": task, "llm_profile": supervisor_profile},
                "output": {
                    "supervisor_route": route,
                    "route_reason": state["route_reason"],
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

    route: RouteName
    needs_tool = False
    risk_high = bool(matched_risk)
    reason_parts: list[str] = []

    if matched_policy:
        route = "policy_tool_worker"
        needs_tool = True
        reason_parts.append(f"matched policy/access keywords: {matched_policy}")
    elif matched_retrieval:
        route = "retrieval_worker"
        reason_parts.append(f"matched retrieval keywords: {matched_retrieval}")
    elif matched_ambiguous:
        route = "human_review"
        risk_high = True
        reason_parts.append(
            "matched ambiguous error marker without enough routing context"
        )
    else:
        route = "retrieval_worker"
        reason_parts.append("default route: knowledge lookup via retrieval_worker")

    if matched_risk:
        reason_parts.append(f"risk_high because of: {matched_risk}")

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
                "note": "placeholder HITL approval for local lab flow",
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
    return policy_tool_run(state)


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
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 60)
    print("Day 09 Lab - Sprint 2 Integrated Graph")
    print("=" * 60)

    test_queries = [
        "SLA ticket P1 la bao lau?",
        "Quy trinh escalation cho ticket P1 la gi?",
        "Khach hang Flash Sale yeu cau refund vi san pham loi - duoc khong?",
        "ERR-742 xuat hien nhung mo ta loi khong ro.",
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

    print("\nIntegrated graph smoke test completed.")
