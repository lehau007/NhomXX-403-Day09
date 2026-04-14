import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
import uvicorn
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "data" / "docs"
DATA_DIR = BASE_DIR / "data" / "mcp"
MOCK_TICKETS_FILE = DATA_DIR / "mock_tickets.json"
ACCESS_RULES_FILE = DATA_DIR / "access_rules.json"

def load_json(file_path: Path) -> dict:
    if not file_path.exists():
        print(f"Warning: {file_path} not found. Using empty mock data.")
        return {}
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)

MOCK_TICKETS = load_json(MOCK_TICKETS_FILE)
ACCESS_RULES = load_json(ACCESS_RULES_FILE)

server = Server("my-mcp-server")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_kb",
            description="Tim kiem Knowledge Base noi bo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_ticket_info",
            description="Tra cuu thong tin ticket.",
            inputSchema={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
        ),
        Tool(
            name="check_access_permission",
            description="Kiem tra quyen truy cap.",
            inputSchema={
                "type": "object",
                "properties": {
                    "access_level": {"type": "integer"},
                    "requester_role": {"type": "string"},
                    "is_emergency": {"type": "boolean", "default": False},
                },
                "required": ["access_level", "requester_role"],
            },
        ),
        Tool(
            name="create_ticket",
            description="Tao ticket moi.",
            inputSchema={
                "type": "object",
                "properties": {
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["priority", "title"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if not arguments:
        arguments = {}
        
    try:
        if name == "search_kb":
            query = arguments.get("query", "")
            top_k = arguments.get("top_k", 3)
            query_terms = [term for term in query.lower().split() if len(term) > 2]
            scored_chunks = []

            if DOCS_DIR.exists():
                for file_path in DOCS_DIR.glob("*.txt"):
                    text = file_path.read_text(encoding="utf-8")
                    lowered = text.lower()
                    hits = sum(lowered.count(term) for term in query_terms)
                    if hits <= 0:
                        continue
                    snippet = text[:700].strip()
                    score = min(0.99, 0.3 + hits * 0.1)
                    scored_chunks.append(
                        {
                            "text": snippet,
                            "source": file_path.name,
                            "score": round(score, 4),
                            "metadata": {"match_count": hits},
                        }
                    )

            scored_chunks.sort(key=lambda chunk: chunk["score"], reverse=True)
            chunks = scored_chunks[:top_k]
            sources = list(dict.fromkeys(chunk["source"] for chunk in chunks))
            
            result = {
                "chunks": chunks,
                "sources": sources,
                "total_found": len(chunks),
            }
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "get_ticket_info":
            ticket_id = arguments.get("ticket_id", "")
            ticket = MOCK_TICKETS.get(ticket_id.upper())
            if ticket:
                result = ticket
            else:
                result = {
                    "error": f"Ticket '{ticket_id}' khong tim thay.",
                    "available_ids": list(MOCK_TICKETS.keys()),
                }
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "check_access_permission":
            access_level = arguments.get("access_level")
            requester_role = arguments.get("requester_role")
            is_emergency = arguments.get("is_emergency", False)
            
            rule = ACCESS_RULES.get(str(access_level))
            if not rule:
                result = {"error": f"Access level {access_level} khong hop le."}
            else:
                can_grant = True
                notes = []

                if is_emergency and rule.get("emergency_can_bypass"):
                    notes.append(rule.get("emergency_bypass_note", ""))
                elif is_emergency and not rule.get("emergency_can_bypass"):
                    notes.append(f"Level {access_level} khong co emergency bypass.")
                    if access_level == 3:
                        can_grant = False

                result = {
                    "access_level": access_level,
                    "requester_role": requester_role,
                    "can_grant": can_grant,
                    "required_approvers": rule.get("required_approvers", []),
                    "emergency_override": is_emergency and rule.get("emergency_can_bypass", False),
                    "notes": notes,
                    "source": "access_control_sop.txt",
                }
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "create_ticket":
            priority = arguments.get("priority", "P3")
            title = arguments.get("title", "")
            description = arguments.get("description", "")
            
            ticket_id = f"IT-{9900 + abs(hash(title)) % 99}"
            ticket = {
                "ticket_id": ticket_id,
                "priority": priority,
                "title": title,
                "description": description,
                "status": "open",
                "created_at": datetime.now().isoformat(),
                "url": f"https://jira.company.internal/browse/{ticket_id}",
            }
            MOCK_TICKETS[ticket_id] = ticket
            result = ticket
            return [TextContent(type="text", text=json.dumps(result))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Tool '{name}' not found."}))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


sse = SseServerTransport("/messages")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    yield
    # Cleanup

app = FastAPI(title="MCP Server", lifespan=lifespan)

@app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    print("Starting MCP Server on http://127.0.0.1:8082/sse")
    uvicorn.run("mcp_server:app", host="127.0.0.1", port=8082)
