"""
workers/policy_tool.py - Policy and Tool Worker
Sprint 2/3: apply policy logic and call MCP tools when needed.
"""

import re
from datetime import datetime


WORKER_NAME = "policy_tool_worker"


def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Sprint 3: SSE/HTTP MCP client implementation with retry and timeout.
    """
    import asyncio
    import json

    async def _run():
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession

        async with sse_client("http://127.0.0.1:8082/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=tool_input)
                if result.isError:
                    return {"error": result.content[0].text}
                return json.loads(result.content[0].text)

    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            # Create a fresh event loop to avoid conflicts
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(asyncio.wait_for(_run(), timeout=15.0))
            finally:
                loop.close()

            error = None
            if isinstance(result, dict) and result.get("error"):
                error = {"code": "MCP_CALL_FAILED", "reason": str(result["error"])}
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": result,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                import time
                time.sleep(0.5)
                continue

    return {
        "tool": tool_name,
        "input": tool_input,
        "output": None,
        "error": {"code": "MCP_CALL_FAILED", "reason": str(last_error)},
        "timestamp": datetime.now().isoformat(),
    }


def _extract_access_level(task: str) -> int:
    task_lower = task.lower()
    match = re.search(r"level\s*([123])", task_lower)
    if match:
        return int(match.group(1))
    if "admin" in task_lower:
        return 3
    return 1


def _extract_ticket_id(task: str) -> str:
    match = re.search(r"\b(?:it-\d+|p\d(?:-[a-z0-9]+)?)\b", task.lower())
    if match:
        return match.group(0).upper()
    if "p1" in task.lower():
        return "P1-LATEST"
    return "IT-0000"


def analyze_policy(task: str, chunks: list) -> dict:
    task_lower = task.lower()
    context_text = " ".join(chunk.get("text", "") for chunk in chunks).lower()

    exceptions_found = []

    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append(
            {
                "type": "flash_sale_exception",
                "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
                "source": "policy_refund_v4.txt",
            }
        )

    if any(
        keyword in task_lower or keyword in context_text
        for keyword in ["license key", "license", "subscription", "phan mem", "digital"]
    ):
        exceptions_found.append(
            {
                "type": "digital_product_exception",
                "rule": "Sản phẩm kỹ thuật số hoặc subscription không được hoàn tiền (Điều 3).",
                "source": "policy_refund_v4.txt",
            }
        )

    if any(
        keyword in task_lower or keyword in context_text
        for keyword in ["da kich hoat", "da dang ky", "da su dung", "activated"]
    ):
        exceptions_found.append(
            {
                "type": "activated_exception",
                "rule": "Sản phẩm đã kích hoạt hoặc đã sử dụng không được hoàn tiền (Điều 3).",
                "source": "policy_refund_v4.txt",
            }
        )

    policy_name = "refund_policy_v4"
    policy_version_note = ""
    if any(keyword in task_lower for keyword in ["31/01", "30/01", "truoc 01/02", "january 2026"]):
        policy_name = "refund_policy_v3"
        policy_version_note = (
            "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3, nhưng tài liệu v3 chưa có trong repo hiện tại."
        )

    sources = list(dict.fromkeys(chunk.get("source", "unknown") for chunk in chunks if chunk))
    for exception in exceptions_found:
        if exception["source"] not in sources:
            sources.append(exception["source"])

    applied_rule = (
        exceptions_found[0]["rule"]
        if exceptions_found
        else "Áp dụng chính sách hoàn trả tiêu chuẩn nếu đủ điều kiện theo tài liệu hiện có."
    )

    return {
        "policy_applies": len(exceptions_found) == 0,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "rule": applied_rule,
        "explanation": "Policy analysis based on explicit refund/access rules and exception detection.",
    }


def run(state: dict) -> dict:
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)
    llm_profile = state.get("llm_profiles", {}).get("policy", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])
    state.setdefault("worker_io_logs", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
            "llm_profile": llm_profile,
        },
        "output": None,
        "error": None,
    }

    try:
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")
            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks
                state["retrieved_sources"] = list(
                    dict.fromkeys(chunk.get("source", "unknown") for chunk in chunks)
                )

        task_lower = task.lower()

        if needs_tool and any(keyword in task_lower for keyword in ["access", "quyen", "permission", "level", "admin"]):
            level = _extract_access_level(task)
            is_emergency = any(keyword in task_lower for keyword in ["khan cap", "emergency", "urgent"])
            mcp_result = _call_mcp_tool(
                "check_access_permission",
                {
                    "access_level": level,
                    "requester_role": "user",
                    "is_emergency": is_emergency,
                },
            )
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(
                f"[{WORKER_NAME}] called MCP check_access_permission (Level {level})"
            )

        if needs_tool and any(keyword in task_lower for keyword in ["ticket", "p1", "jira", "it-"]):
            ticket_id = _extract_ticket_id(task)
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": ticket_id})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(
                f"[{WORKER_NAME}] called MCP get_ticket_info ({ticket_id})"
            )

        policy_result = analyze_policy(task, chunks)
        
        # Sprint 3: Add MCP tool results to policy context for synthesis
        if state.get("mcp_tools_used"):
            mcp_context = []
            for mcp in state["mcp_tools_used"]:
                if mcp.get("output") and not mcp.get("error"):
                    tool_name = mcp.get("tool")
                    tool_out = mcp.get("output")
                    mcp_context.append(f"Tool {tool_name} returned: {tool_out}")
            
            if mcp_context:
                policy_result["mcp_context"] = "\n".join(mcp_context)

        state["policy_result"] = policy_result

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "policy_name": policy_result["policy_name"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state["mcp_tools_used"]),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}"
        )
    except Exception as error:
        state["policy_result"] = {"error": str(error)}
        worker_io["error"] = {
            "code": "POLICY_CHECK_FAILED",
            "reason": str(error),
        }
        state["history"].append(f"[{WORKER_NAME}] ERROR: {error}")

    state["worker_io_logs"].append(worker_io)
    return state


if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker - Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khach hang Flash Sale yeu cau hoan tien vi san pham loi.",
            "retrieved_chunks": [
                {
                    "text": "Ngoai le: Don hang Flash Sale khong duoc hoan tien.",
                    "source": "policy_refund_v4.txt",
                    "score": 0.9,
                }
            ],
        },
        {
            "task": "Contractor can level 3 access de xu ly P1 khan cap.",
            "retrieved_chunks": [],
            "needs_tool": True,
        },
    ]

    for case in test_cases:
        result = run(case.copy())
        print(result.get("policy_result", {}))
