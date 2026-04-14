"""
mcp_server.py — Standardized MCP Server
Refactored based on review for Sprint 1/3.

Features:
    - Standardized Tool Registry.
    - Mock data loaded from JSON files.
    - Fixed duplicate search logic.
    - Ready for MCP Protocol integration.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────
# Path Configuration
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "mcp"
MOCK_TICKETS_FILE = DATA_DIR / "mock_tickets.json"
ACCESS_RULES_FILE = DATA_DIR / "access_rules.json"

# ─────────────────────────────────────────────
# Data Loading
# ─────────────────────────────────────────────
def load_json(file_path: Path) -> dict:
    if not file_path.exists():
        print(f"⚠️  Warning: {file_path} not found. Using empty mock data.")
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

MOCK_TICKETS = load_json(MOCK_TICKETS_FILE)
ACCESS_RULES = load_json(ACCESS_RULES_FILE)

# ─────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────

def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """
    Tìm kiếm Knowledge Base bằng semantic search thông qua retrieval worker.
    """
    try:
        from workers.retrieval import retrieve_dense
        chunks = retrieve_dense(query, top_k=top_k)
        sources = list({c["source"] for c in chunks})
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as e:
        return {
            "error": f"Search failed: {e}",
            "chunks": [],
            "sources": [],
            "total_found": 0
        }

def tool_get_ticket_info(ticket_id: str) -> dict:
    """
    Tra cứu thông tin ticket từ mock data.
    """
    ticket = MOCK_TICKETS.get(ticket_id.upper())
    if ticket:
        return ticket
    return {
        "error": f"Ticket '{ticket_id}' không tìm thấy.",
        "available_ids": list(MOCK_TICKETS.keys())
    }

def tool_check_access_permission(access_level: int, requester_role: str, is_emergency: bool = False) -> dict:
    """
    Kiểm tra quyền truy cập theo quy định.
    """
    rule = ACCESS_RULES.get(str(access_level))
    if not rule:
        return {"error": f"Access level {access_level} không hợp lệ."}

    can_grant = True
    notes = []

    if is_emergency and rule.get("emergency_can_bypass"):
        notes.append(rule.get("emergency_bypass_note", ""))
    elif is_emergency and not rule.get("emergency_can_bypass"):
        notes.append(f"Level {access_level} KHÔNG có emergency bypass.")
        can_grant = False if access_level == 3 else True # Demo logic

    return {
        "access_level": access_level,
        "can_grant": can_grant,
        "required_approvers": rule["required_approvers"],
        "emergency_override": is_emergency and rule.get("emergency_can_bypass", False),
        "notes": notes,
        "source": "access_control_sop.txt"
    }

def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    """
    Tạo ticket mới (Mock).
    """
    mock_id = f"IT-{9900 + hash(title) % 99}"
    ticket = {
        "ticket_id": mock_id,
        "priority": priority,
        "title": title,
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "url": f"https://jira.company.internal/browse/{mock_id}"
    }
    MOCK_TICKETS[mock_id] = ticket
    return ticket

# ─────────────────────────────────────────────
# Dispatcher Layer
# ─────────────────────────────────────────────

TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}

TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tìm kiếm Knowledge Base nội bộ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 3}
            },
            "required": ["query"]
        }
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cứu thông tin ticket Jira.",
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"]
        }
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Kiểm tra quyền truy cập.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer"},
                "requester_role": {"type": "string"},
                "is_emergency": {"type": "boolean", "default": False}
            },
            "required": ["access_level", "requester_role"]
        }
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tạo ticket Jira mới.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["priority", "title"]
        }
    }
}

def list_tools():
    return list(TOOL_SCHEMAS.values())

def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' not found."}
    
    try:
        return TOOL_REGISTRY[tool_name](**tool_input)
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────
# FastAPI Entry Point (Advanced Mode)
# ─────────────────────────────────────────────

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import uvicorn

    app = FastAPI(title="MCP Server")

    class ToolCallRequest(BaseModel):
        tool_name: str
        tool_input: Dict[str, Any]

    @app.get("/tools")
    def get_tools():
        return {"tools": list_tools()}

    @app.post("/tools/call")
    def call_tool(request: ToolCallRequest):
        result = dispatch_tool(request.tool_name, request.tool_input)
        return {"status": "success" if "error" not in result else "error", "output": result}

except ImportError:
    app = None

if __name__ == "__main__":
    if app:
        print("🚀 Starting MCP Server on http://127.0.0.1:8000")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        print("⚠️ FastAPI or Uvicorn not installed. Running in standalone test mode.")
        # Test search
        print(dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"}))
