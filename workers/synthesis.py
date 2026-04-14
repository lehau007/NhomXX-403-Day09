"""
workers/synthesis.py - Synthesis Worker
Sprint 2: synthesize a grounded answer from retrieval and policy evidence.
"""

import os

from dotenv import load_dotenv


load_dotenv()


WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """You are an internal IT Helpdesk and Policy assistant.

Rules:
1. Answer only from the provided context.
2. If the context is insufficient, explicitly abstain.
3. Cite important claims inline using [source_name].
4. If policy exceptions exist, mention them before the conclusion.
5. Keep the answer concise, structured, and factual.
"""


def _call_openai_compatible(
    messages: list,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> str:
    from openai import OpenAI

    kwargs = {"api_key": api_key, "timeout": 3.0}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


def _call_google(messages: list, model: str, api_key: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    generator = genai.GenerativeModel(model)
    prompt = "\n".join(message["content"] for message in messages)
    response = generator.generate_content(prompt)
    return getattr(response, "text", "") or ""


def _fallback_answer(chunks: list, policy_result: dict) -> str:
    if policy_result.get("exceptions_found"):
        first_exception = policy_result["exceptions_found"][0]
        return (
            "Yeu cau nay bi chan boi policy. "
            f"Ly do: {first_exception.get('rule', '')} "
            f"[{first_exception.get('source', 'unknown')}]"
        )

    if not chunks:
        return "Khong du thong tin trong tai lieu noi bo."

    primary_chunk = chunks[0]
    return f"{primary_chunk.get('text', '')} [{primary_chunk.get('source', 'unknown')}]"


def _call_llm(messages: list, llm_profile: dict, chunks: list, policy_result: dict) -> str:
    if not chunks or policy_result.get("exceptions_found"):
        return _fallback_answer(chunks, policy_result)

    provider = llm_profile.get("provider", os.getenv("SYNTHESIS_PROVIDER", "groq")).lower()
    model = llm_profile.get("model", os.getenv("SYNTHESIS_MODEL", "openai/gpt-oss-120b"))

    try:
        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
                return _call_openai_compatible(messages, model, api_key, base_url=base_url)

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                return _call_openai_compatible(messages, model, api_key)

        if provider == "google":
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                return _call_google(messages, model, api_key)
    except Exception as error:
        print(f"Warning: synthesis LLM call failed: {error}")

    return _fallback_answer(chunks, policy_result)


def _build_context(chunks: list, policy_result: dict) -> str:
    parts = []

    if chunks:
        parts.append("=== EVIDENCE ===")
        for index, chunk in enumerate(chunks, start=1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0.0)
            parts.append(f"[{index}] Source: {source} (relevance={score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("=== POLICY EXCEPTIONS ===")
        for exception in policy_result["exceptions_found"]:
            parts.append(
                f"- {exception.get('rule', '')} [{exception.get('source', 'unknown')}]"
            )

    if policy_result and policy_result.get("policy_version_note"):
        parts.append("=== POLICY VERSION NOTE ===")
        parts.append(policy_result["policy_version_note"])

    if not parts:
        return "(No context)"

    return "\n\n".join(parts)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    if not chunks:
        return 0.1

    if "Khong du thong tin" in answer or "insufficient" in answer.lower():
        return 0.3

    average_score = sum(chunk.get("score", 0) for chunk in chunks) / len(chunks)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))
    return round(max(0.1, min(0.95, average_score - exception_penalty)), 2)


def synthesize(task: str, chunks: list, policy_result: dict, llm_profile: dict) -> dict:
    context = _build_context(chunks, policy_result)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Question: {task}\n\n"
                f"{context}\n\n"
                "Answer only from the evidence above. "
                "Use inline citations in the format [source_name]."
            ),
        },
    ]

    answer = _call_llm(messages, llm_profile, chunks, policy_result)
    sources = list(dict.fromkeys(chunk.get("source", "unknown") for chunk in chunks))

    for source in policy_result.get("source", []):
        if source not in sources:
            sources.append(source)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": _estimate_confidence(chunks, answer, policy_result),
    }


def run(state: dict) -> dict:
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})
    llm_profile = state.get("llm_profiles", {}).get(
        "synthesis",
        {
            "provider": os.getenv("SYNTHESIS_PROVIDER", "groq"),
            "model": os.getenv("SYNTHESIS_MODEL", "openai/gpt-oss-120b"),
        },
    )

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
            "llm_profile": llm_profile,
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result, llm_profile)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, sources={result['sources']}"
        )
    except Exception as error:
        state["final_answer"] = f"SYNTHESIS_ERROR: {error}"
        state["confidence"] = 0.0
        worker_io["error"] = {
            "code": "SYNTHESIS_FAILED",
            "reason": str(error),
        }
        state["history"].append(f"[{WORKER_NAME}] ERROR: {error}")

    state["worker_io_logs"].append(worker_io)
    return state


if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker - Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 la bao lau?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1 requires an initial response within 15 minutes and resolution within 4 hours.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }
    result = run(test_state)
    print(result["final_answer"])
