"""
workers/synthesis.py - Synthesis Worker
Sprint 2: generate a grounded answer from retrieved chunks and policy results.
"""

import os

from dotenv import load_dotenv


load_dotenv()


from dotenv import load_dotenv

load_dotenv()
WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là Chuyên gia Tổng hợp Thông tin của hệ thống IT Helpdesk & Policy Advisor.
Nhiệm vụ của bạn là đưa ra câu trả lời cuối cùng chính xác, chuyên nghiệp và có căn cứ dựa trên các tài liệu nội bộ.
QUY TẮC CỐT LÕI:
1. TRUNG THỰC TỐI ĐA: Chỉ trả lời dựa trên "TÀI LIỆU THAM KHẢO" và "POLICY EXCEPTIONS" được cung cấp. Tuyệt đối không sử dụng kiến
thức bên ngoài hoặc tự suy diễn.
2. XỬ LÝ NGOẠI LỆ (QUAN TRỌNG): Nếu có thông tin trong phần "POLICY EXCEPTIONS", đây là các quy định bắt buộc hoặc ngoại lệ quan
trọng. Bạn PHẢI đưa các thông tin này vào câu trả lời (thường là ở phần lưu ý hoặc cảnh báo).
3. TRÍCH DẪN (CITATION): Mọi thông tin quan trọng phải được trích dẫn nguồn ngay sau câu đó dưới dạng [tên_file.txt]. Không trích dẫn
chung chung ở cuối bài.
4. TRẠNG THÁI "THIẾU THÔNG TIN": Nếu tài liệu cung cấp không chứa câu trả lời, hãy phản hồi: "Xin lỗi, tôi không tìm thấy thông
tin cụ thể về vấn đề này trong tài liệu nội bộ của công ty."

CẤU TRÚC CÂU TRẢ LỜI:
    - Trực diện: Trả lời thẳng vào vấn đề ngay câu đầu tiên.
    - Chi tiết: Trình bày các bước hoặc điều kiện kèm theo (nếu có).
    - Lưu ý/Ngoại lệ: Nêu rõ các trường hợp đặc biệt dựa trên Policy.
    - Nguồn tham khảo: Liệt kê lại các file đã sử dụng ở dưới cùng.

PHONG CÁCH: Chuyên nghiệp, lịch sự, ngắn gọn nhưng đầy đủ ý.
"""


def _call_llm(messages: list) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.
    TODO Sprint 2: Implement với OpenAI hoặc Gemini.
    """
    model_provider = os.getenv("SYNTHESIS_PROVIDER", "google").lower()
    if model_provider == "openai":
        # Option A: OpenAI
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model_name = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,  # Low temperature để grounded
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[SYNTHESIS ERROR] OpenAI: {str(e)}"
    elif model_provider == "groq":
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
            model_name = os.getenv("SYNTHESIS_MODEL")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,  # Low temperature để grounded
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[SYNTHESIS ERROR] OpenAI: {str(e)}"
    else:
        # Option B: Gemini
        try:
            from google import genai

            api_key = os.getenv("GOOGLE_API_KEY")
            client = genai.Client(api_key=api_key)
            model_name = os.getenv("SYNTHESIS_MODEL", "gemini-3.1-flash-lite-preview")
            user_prompt = messages[-1]["content"]
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "temperature": 0.1,  # Keep it low for factual RAG
                    "max_output_tokens": 800,
                },
            )
            return response.text
        except Exception as e:
            return f"[SYNTHESIS ERROR] Gemini: {str(e)}"
SYSTEM_PROMPT = """You are an internal IT Helpdesk assistant.

Strict rules:
1. Answer only from the provided context.
2. If the context is insufficient, clearly abstain.
3. Cite sources inline using [source_name].
4. Keep the answer concise and structured.
5. If policy exceptions exist, mention them before concluding.
"""


def _call_openai_compatible(messages: list, model: str, api_key: str, base_url: str | None = None) -> str:
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
    combined = "\n".join(message["content"] for message in messages)
    response = generator.generate_content(combined)
    return getattr(response, "text", "") or ""


def _fallback_answer(task: str, chunks: list, policy_result: dict) -> str:
    if policy_result.get("exceptions_found"):
        first_exception = policy_result["exceptions_found"][0]
        return (
            "Khong du dieu kien theo ket qua policy hien tai. "
            f"Ly do: {first_exception.get('rule', '')} "
            f"[{first_exception.get('source', 'unknown')}]"
        )

    if not chunks:
        return "Khong du thong tin trong tai lieu noi bo."

    first_chunk = chunks[0]
    return f"{first_chunk.get('text', '')} [{first_chunk.get('source', 'unknown')}]"


def _call_llm(messages: list, llm_profile: dict, task: str, chunks: list, policy_result: dict) -> str:
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

    return _fallback_answer(task, chunks, policy_result)


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
            parts.append(f"- {exception.get('rule', '')}")

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
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu trên.""",
        },
    ]

    answer = _call_llm(messages, llm_profile, task, chunks, policy_result)
    sources = list(dict.fromkeys(chunk.get("source", "unknown") for chunk in chunks))
    if policy_result.get("source"):
        for source in policy_result["source"]:
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
