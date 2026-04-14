"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os

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


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence dựa vào:
    - Số lượng và quality của chunks
    - Có exceptions không
    - Answer có abstain không

    TODO Sprint 2: Có thể dùng LLM-as-Judge để tính confidence chính xác hơn.
    """
    if not chunks:
        return 0.1  # Không có evidence → low confidence

    if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
        return 0.3  # Abstain → moderate-low

    # Weighted average của chunk scores
    if chunks:
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
    else:
        avg_score = 0

    # Penalty nếu có exceptions (phức tạp hơn)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))

    confidence = min(0.95, avg_score - exception_penalty)
    return round(max(0.1, confidence), 2)


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu trên.""",
        },
    ]

    answer = _call_llm(messages)
    sources = list({c.get("source", "unknown") for c in chunks})
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
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

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
