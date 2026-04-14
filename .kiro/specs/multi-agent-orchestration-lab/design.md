# Design Document: Multi-Agent Orchestration Lab

## Overview

This design document specifies the architecture and implementation details for a multi-agent orchestration system that refactors a monolithic RAG pipeline into a Supervisor-Worker pattern. The system coordinates specialized worker agents (retrieval, policy checking, synthesis) through a supervisor orchestrator to handle CS and IT Helpdesk queries across five internal documents.

### System Goals

- **Modularity**: Separate concerns into independent, testable workers
- **Traceability**: Provide complete execution traces for debugging and analysis
- **Extensibility**: Enable easy addition of new workers and capabilities
- **Reliability**: Handle errors gracefully without cascading failures

### Key Design Decisions

1. **Supervisor-Worker Pattern**: Chosen over single-agent approach for clear separation of routing logic from domain expertise
2. **Stateless Workers**: Workers operate on shared state without side effects, enabling independent testing
3. **MCP Integration**: External capabilities accessed through Model Context Protocol for loose coupling
4. **Contract-Based Interfaces**: YAML contracts define worker I/O specifications for validation and documentation

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Query                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Supervisor Node                          │
│  • Analyzes task keywords                                   │
│  • Determines routing decision                              │
│  • Sets risk_high and needs_tool flags                      │
│  • Records route_reason                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
                  [Route Decision]
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Retrieval   │  │ Policy Tool  │  │    Human     │
│   Worker     │  │   Worker     │  │   Review     │
│              │  │              │  │              │
│ • ChromaDB   │  │ • Policy     │  │ • HITL       │
│   search     │  │   analysis   │  │   trigger    │
│ • Chunk      │  │ • MCP tool   │  │ • Approval   │
│   retrieval  │  │   calls      │  │   flow       │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │   Synthesis     │
                │     Worker      │
                │                 │
                │ • LLM call      │
                │ • Citation      │
                │ • Confidence    │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  Final Answer   │
                │  + Trace Log    │
                └─────────────────┘
```

### Component Interaction Flow

1. **Query Reception**: User query enters through `run_graph(task)` entry point
2. **State Initialization**: `AgentState` object created with task and empty fields
3. **Supervisor Analysis**: Supervisor analyzes task, sets routing decision and flags
4. **Worker Execution**: Appropriate worker(s) invoked based on routing decision
5. **Synthesis**: Synthesis worker generates final answer from worker outputs
6. **Trace Generation**: Complete execution trace saved to artifacts directory

### Routing Decision Logic

The supervisor uses keyword-based routing with the following priority:

```python
# Priority 1: Human Review (highest risk)
if risk_high AND unknown_error_code:
    route = "human_review"

# Priority 2: Policy/Tool Worker
elif any(policy_keyword in task):
    route = "policy_tool_worker"
    needs_tool = True

# Priority 3: Retrieval Worker (default)
else:
    route = "retrieval_worker"
```

**Policy Keywords**: "hoàn tiền", "refund", "flash sale", "license", "cấp quyền", "access", "level"
**Risk Keywords**: "emergency", "khẩn cấp", "2am", "err-"
**SLA Keywords**: "P1", "escalation", "sla", "ticket"


## Components and Interfaces

### 1. AgentState (Shared State)

The `AgentState` TypedDict serves as the shared memory passed between all components.

```python
class AgentState(TypedDict):
    # Input
    task: str                      # User query
    
    # Supervisor decisions
    supervisor_route: str          # Worker chosen: retrieval_worker | policy_tool_worker | human_review
    route_reason: str              # Specific explanation for routing decision
    risk_high: bool                # True if emergency/high-risk scenario
    needs_tool: bool               # True if MCP tool invocation required
    hitl_triggered: bool           # True if human review was triggered
    
    # Worker outputs
    retrieved_chunks: list         # [{text, source, score, metadata}, ...]
    retrieved_sources: list        # Unique source filenames
    policy_result: dict            # {policy_applies, policy_name, exceptions_found, source}
    mcp_tools_used: list           # [{tool, input, output, error, timestamp}, ...]
    
    # Final output
    final_answer: str              # Synthesized answer with citations
    sources: list                  # Sources cited in final answer
    confidence: float              # 0.0 - 1.0
    
    # Trace metadata
    history: list                  # Execution log entries
    workers_called: list           # Worker names in execution order
    worker_io_logs: list           # Detailed I/O logs per worker
    latency_ms: int                # Total execution time
    run_id: str                    # Unique run identifier
```

**Design Rationale**: TypedDict provides type hints for IDE support while maintaining dictionary flexibility for dynamic field access.

### 2. Supervisor Node (`graph.py`)

**Responsibility**: Analyze incoming tasks and make routing decisions.

**Interface**:
```python
def supervisor_node(state: AgentState) -> AgentState:
    """
    Analyzes task and determines routing.
    
    Input: state with task field populated
    Output: state with supervisor_route, route_reason, risk_high, needs_tool set
    """
```

**Implementation Strategy**:
- Keyword matching for initial routing classification
- Risk assessment based on emergency indicators
- Tool requirement detection for policy queries
- Explicit route_reason generation (never "unknown")

**Error Handling**: Defaults to retrieval_worker if no clear match, logs decision rationale.

### 3. Retrieval Worker (`workers/retrieval.py`)

**Responsibility**: Retrieve relevant evidence chunks from ChromaDB knowledge base.

**Contract** (from `worker_contracts.yaml`):
```yaml
input:
  task: string (required)
  top_k: integer (optional, default: 3)

output:
  retrieved_chunks: array of {text, source, score, metadata}
  retrieved_sources: array of unique source filenames
  worker_io_logs: array
```

**Implementation Details**:

1. **Embedding Generation**:
   - Primary: Sentence Transformers (`all-MiniLM-L6-v2`) for offline operation
   - Fallback: OpenAI embeddings if API key available
   - Test mode: Random embeddings (development only)

2. **ChromaDB Query**:
   ```python
   collection.query(
       query_embeddings=[query_embedding],
       n_results=top_k,
       include=["documents", "distances", "metadatas"]
   )
   ```

3. **Score Calculation**: `score = 1 - cosine_distance` (0.0 to 1.0 range)

4. **Stateless Operation**: No persistent state beyond ChromaDB connection

**Error Handling**: Returns empty `retrieved_chunks` array on failure, logs error to `worker_io_logs`.

### 4. Policy Tool Worker (`workers/policy_tool.py`)

**Responsibility**: Analyze policy rules, detect exceptions, invoke MCP tools when needed.

**Contract**:
```yaml
input:
  task: string (required)
  retrieved_chunks: array (optional)
  needs_tool: boolean (optional, default: false)

output:
  policy_result: object {policy_applies, policy_name, exceptions_found, source}
  mcp_tools_used: array of tool call records
  worker_io_logs: array
```

**Exception Detection Logic**:

1. **Flash Sale Exception**:
   - Trigger: "flash sale" in task or context
   - Rule: Flash Sale orders not eligible for refund (Policy v4, Article 3)

2. **Digital Product Exception**:
   - Trigger: "license key", "subscription", "kỹ thuật số"
   - Rule: Digital products non-refundable after delivery

3. **Activated Product Exception**:
   - Trigger: "đã kích hoạt", "đã đăng ký", "đã sử dụng"
   - Rule: Activated products non-refundable

4. **Temporal Scoping**:
   - Detect orders before 01/02/2026 → flag policy version mismatch
   - Note: Policy v3 not available in current documentation

**MCP Integration**:
```python
def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    from mcp_server import dispatch_tool
    result = dispatch_tool(tool_name, tool_input)
    return {
        "tool": tool_name,
        "input": tool_input,
        "output": result,
        "error": None if "error" not in result else result,
        "timestamp": datetime.now().isoformat()
    }
```

**Tool Invocation Strategy**:
- If `needs_tool=True` and no chunks available → call `search_kb`
- If ticket-related query → call `get_ticket_info`
- If access control query → call `check_access_permission`

### 5. Synthesis Worker (`workers/synthesis.py`)

**Responsibility**: Generate final answer with citations from retrieved evidence and policy results.

**Contract**:
```yaml
input:
  task: string (required)
  retrieved_chunks: array (optional)
  policy_result: object (optional)

output:
  final_answer: string with inline citations
  sources: array of cited source filenames
  confidence: float (0.0 - 1.0)
  worker_io_logs: array
```

**LLM Prompt Strategy**:

```python
SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""
```

**Context Building**:
1. Format retrieved chunks with source and relevance score
2. Append policy exceptions if present
3. Provide structured context to LLM

**Confidence Estimation**:
```python
def _estimate_confidence(chunks, answer, policy_result):
    if not chunks:
        return 0.1  # No evidence
    
    if "Không đủ thông tin" in answer:
        return 0.3  # Abstention
    
    avg_score = sum(c["score"] for c in chunks) / len(chunks)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))
    
    return min(0.95, max(0.1, avg_score - exception_penalty))
```

**Abstention Behavior**:
- Triggered when `retrieved_chunks` is empty
- Answer: "Không đủ thông tin trong tài liệu nội bộ. Vui lòng liên hệ support team."
- Confidence: 0.0
- Sources: []

### 6. MCP Server (`mcp_server.py`)

**Responsibility**: Provide external capabilities through Model Context Protocol interface.

**Tool Registry**:

1. **search_kb**:
   ```python
   Input: {query: str, top_k: int}
   Output: {chunks: list, sources: list, total_found: int}
   ```
   Delegates to retrieval worker's `retrieve_dense()` function.

2. **get_ticket_info**:
   ```python
   Input: {ticket_id: str}
   Output: {ticket_id, priority, status, assignee, created_at, sla_deadline, notifications_sent}
   ```
   Returns mock ticket data from `MOCK_TICKETS` dictionary.

3. **check_access_permission**:
   ```python
   Input: {access_level: int, requester_role: str, is_emergency: bool}
   Output: {can_grant: bool, required_approvers: list, emergency_override: bool, notes: list}
   ```
   Applies access control rules from `ACCESS_RULES` configuration.

4. **create_ticket**:
   ```python
   Input: {priority: str, title: str, description: str}
   Output: {ticket_id: str, url: str, created_at: str}
   ```
   Mock implementation (logs only, no actual ticket creation).

**Dispatch Interface**:
```python
def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """
    MCP execution interface.
    
    Returns: Tool output dict or error dict if tool not found/failed
    """
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' không tồn tại"}
    
    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**tool_input)
    except Exception as e:
        return {"error": f"Tool execution failed: {e}"}
```

**Discovery Interface**:
```python
def list_tools() -> list:
    """Returns list of available tool schemas in MCP format."""
    return list(TOOL_SCHEMAS.values())
```

### 7. Human Review Node (`graph.py`)

**Responsibility**: Handle high-risk scenarios requiring human oversight.

**Trigger Conditions**:
- `risk_high=True` AND unknown error code detected
- Confidence score < 0.4 (set by synthesis worker)

**Implementation**:
```python
def human_review_node(state: AgentState) -> AgentState:
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    
    # Log HITL event
    print(f"⚠️  HITL TRIGGERED: {state['task']}")
    print(f"   Reason: {state['route_reason']}")
    
    # Auto-approve in lab mode, route to retrieval
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"
    
    return state
```

**Production Considerations**: Replace auto-approval with actual interrupt mechanism (LangGraph `interrupt_before` or external approval queue).

### 8. Trace Generation (`eval_trace.py`)

**Responsibility**: Generate execution traces for debugging and evaluation.

**Trace Format**:
```json
{
  "run_id": "run_20260413_143211",
  "task": "User query text",
  "supervisor_route": "retrieval_worker",
  "route_reason": "task contains SLA keyword",
  "workers_called": ["retrieval_worker", "synthesis_worker"],
  "mcp_tools_used": [],
  "retrieved_sources": ["sla_p1_2026.txt"],
  "final_answer": "Answer with citations [1]",
  "sources": ["sla_p1_2026.txt"],
  "confidence": 0.88,
  "hitl_triggered": false,
  "latency_ms": 1230,
  "timestamp": "2026-04-13T14:32:11"
}
```

**Grading Trace Format** (JSONL):
```json
{"id": "gq01", "question": "...", "answer": "...", "sources": [...], "supervisor_route": "...", "route_reason": "...", "workers_called": [...], "mcp_tools_used": [...], "confidence": 0.91, "hitl_triggered": false, "timestamp": "..."}
```

**Trace Generation Flow**:
1. Initialize trace record with `run_id` and `task`
2. Append worker names to `workers_called` as they execute
3. Collect `worker_io_logs` from each worker
4. Record MCP tool calls in `mcp_tools_used`
5. Calculate `latency_ms` from start to end timestamp
6. Save to `artifacts/traces/{run_id}.json`


## Data Models

### AgentState Schema

```python
from typing import TypedDict, Optional, List, Dict, Any

class ChunkModel(TypedDict):
    text: str
    source: str
    score: float
    metadata: Dict[str, Any]

class PolicyException(TypedDict):
    type: str  # "flash_sale_exception" | "digital_product_exception" | "activated_exception"
    rule: str
    source: str

class PolicyResult(TypedDict):
    policy_applies: bool
    policy_name: str
    exceptions_found: List[PolicyException]
    source: List[str]
    policy_version_note: Optional[str]
    explanation: str

class MCPToolCall(TypedDict):
    tool: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    error: Optional[Dict[str, str]]
    timestamp: str

class WorkerIOLog(TypedDict):
    worker: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    error: Optional[Dict[str, str]]

class AgentState(TypedDict):
    # Input
    task: str
    
    # Supervisor decisions
    supervisor_route: str
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool
    
    # Worker outputs
    retrieved_chunks: List[ChunkModel]
    retrieved_sources: List[str]
    policy_result: PolicyResult
    mcp_tools_used: List[MCPToolCall]
    
    # Final output
    final_answer: str
    sources: List[str]
    confidence: float
    
    # Trace metadata
    history: List[str]
    workers_called: List[str]
    worker_io_logs: List[WorkerIOLog]
    latency_ms: Optional[int]
    run_id: str
```

### Worker Contract Schema

Worker contracts are defined in `contracts/worker_contracts.yaml` following this structure:

```yaml
worker_name:
  name: string
  file: string
  description: string
  input:
    field_name:
      type: string | integer | boolean | array | object
      required: boolean
      default: any (optional)
      description: string
  output:
    field_name:
      type: string | integer | boolean | array | object
      required: boolean
      description: string
  error_format:
    code: string
    reason: string
  constraints:
    - constraint description strings
  actual_implementation:
    status: string
    notes: string
```

### MCP Tool Schema

```python
class MCPToolSchema(TypedDict):
    name: str
    description: str
    inputSchema: Dict[str, Any]  # JSON Schema format
    outputSchema: Dict[str, Any]  # JSON Schema format

# Example: search_kb tool
{
    "name": "search_kb",
    "description": "Tìm kiếm Knowledge Base nội bộ bằng semantic search",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Câu hỏi hoặc keyword"},
            "top_k": {"type": "integer", "description": "Số chunks", "default": 3}
        },
        "required": ["query"]
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "chunks": {"type": "array"},
            "sources": {"type": "array"},
            "total_found": {"type": "integer"}
        }
    }
}
```

### Trace Record Schema

```python
class TraceRecord(TypedDict):
    run_id: str
    task: str
    supervisor_route: str
    route_reason: str
    workers_called: List[str]
    mcp_tools_used: List[MCPToolCall]
    retrieved_sources: List[str]
    final_answer: str
    sources: List[str]
    confidence: float
    hitl_triggered: bool
    latency_ms: int
    timestamp: str  # ISO 8601 format
```

### Grading Trace Record Schema

Extends `TraceRecord` with additional fields for evaluation:

```python
class GradingTraceRecord(TraceRecord):
    id: str  # Question ID (e.g., "gq01")
    question: str  # Original question text
    answer: str  # Alias for final_answer
```

## API Contracts Between Components

### 1. Graph → Supervisor

**Input**: `AgentState` with `task` field populated

**Output**: `AgentState` with routing decisions:
- `supervisor_route`: Worker name to invoke
- `route_reason`: Specific explanation (never "unknown")
- `risk_high`: Boolean flag for high-risk scenarios
- `needs_tool`: Boolean flag for MCP tool requirement

**Contract Guarantee**: `route_reason` must be non-empty and descriptive.

### 2. Graph → Workers

**Input**: `AgentState` with fields specified in worker contract

**Output**: `AgentState` with worker-specific output fields populated

**Contract Guarantees**:
- Workers append their name to `workers_called`
- Workers append I/O log to `worker_io_logs`
- Workers do not modify fields outside their contract
- Workers handle errors gracefully, returning error dict instead of raising exceptions

### 3. Workers → MCP Server

**Input**: Tool name (string) and tool input (dict)

**Output**: Tool result (dict) or error dict

**Contract**:
```python
# Success case
{
    "chunks": [...],
    "sources": [...],
    "total_found": 3
}

# Error case
{
    "error": "Tool 'xyz' không tồn tại",
    "available_tools": ["search_kb", "get_ticket_info", ...]
}
```

**Contract Guarantee**: MCP server never raises exceptions outside `dispatch_tool()`.

### 4. Graph → Trace Generator

**Input**: Completed `AgentState` after all workers finish

**Output**: Trace file saved to `artifacts/traces/{run_id}.json`

**Contract**: Trace file contains all required fields from `TraceRecord` schema.

### 5. Supervisor → Human Review

**Input**: `AgentState` with `risk_high=True` and unknown error code

**Output**: `AgentState` with:
- `hitl_triggered=True`
- `workers_called` includes "human_review"
- `supervisor_route` updated to next worker after approval

**Contract**: Human review node logs HITL event to console and trace.

## Routing Logic and Decision Flow

### Routing Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│                    Analyze Task Keywords                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Contains risk_keyword? │
              │ (emergency, 2am, err-) │
              └──────┬────────┬────────┘
                     │        │
                 Yes │        │ No
                     │        │
                     ▼        ▼
            ┌────────────┐   ┌────────────────────────┐
            │ risk_high  │   │ Contains policy_keyword?│
            │ = True     │   │ (refund, access, etc.)  │
            └────────────┘   └──────┬────────┬─────────┘
                     │               │        │
                     │           Yes │        │ No
                     │               │        │
                     ▼               ▼        ▼
            ┌────────────────┐  ┌─────────┐  ┌─────────┐
            │ Unknown error  │  │ Policy  │  │Retrieval│
            │ code present?  │  │ Tool    │  │ Worker  │
            └───┬────────┬───┘  │ Worker  │  │         │
                │        │      └─────────┘  └─────────┘
            Yes │        │ No
                │        │
                ▼        ▼
         ┌──────────┐  ┌─────────┐
         │  Human   │  │Retrieval│
         │  Review  │  │ Worker  │
         └──────────┘  └─────────┘
```

### Routing Rules Implementation

```python
def determine_route(task: str) -> tuple[str, str, bool, bool]:
    """
    Returns: (route, route_reason, risk_high, needs_tool)
    """
    task_lower = task.lower()
    
    # Keyword sets
    policy_keywords = ["hoàn tiền", "refund", "flash sale", "license", 
                       "cấp quyền", "access", "level 3", "level 2"]
    risk_keywords = ["emergency", "khẩn cấp", "2am", "err-"]
    sla_keywords = ["p1", "escalation", "sla", "ticket"]
    
    # Initialize flags
    risk_high = any(kw in task_lower for kw in risk_keywords)
    needs_tool = False
    route = "retrieval_worker"
    route_reason = "default route"
    
    # Rule 1: Policy/Access queries
    if any(kw in task_lower for kw in policy_keywords):
        route = "policy_tool_worker"
        route_reason = f"task contains policy keyword: {[kw for kw in policy_keywords if kw in task_lower]}"
        needs_tool = True
    
    # Rule 2: SLA queries (override if more specific)
    elif any(kw in task_lower for kw in sla_keywords):
        route = "retrieval_worker"
        route_reason = f"task contains SLA keyword: {[kw for kw in sla_keywords if kw in task_lower]}"
    
    # Rule 3: High-risk with unknown error code → human review
    if risk_high and "err-" in task_lower:
        route = "human_review"
        route_reason = "unknown error code + risk_high → human review required"
    
    # Append risk flag to reason
    if risk_high:
        route_reason += " | risk_high flagged"
    
    return route, route_reason, risk_high, needs_tool
```

### Multi-Hop Query Handling

For queries requiring information from multiple documents:

1. **Supervisor routes to primary worker** (e.g., policy_tool_worker)
2. **Primary worker checks for context**: If `retrieved_chunks` is empty and `needs_tool=True`, invoke MCP `search_kb`
3. **Primary worker completes**: Returns policy analysis
4. **Synthesis worker combines**: Merges `retrieved_chunks` and `policy_result` into final answer
5. **Trace records all workers**: `workers_called` array shows execution sequence

**Example Multi-Hop Flow**:
```
Query: "P1 lúc 2am + cần cấp quyền Level 2 tạm thời cho contractor"

1. Supervisor → policy_tool_worker (access control query)
2. Policy Tool Worker → MCP search_kb (retrieve access control SOP)
3. Policy Tool Worker → MCP search_kb (retrieve SLA P1 procedure)
4. Policy Tool Worker → analyze both contexts
5. Synthesis Worker → combine into comprehensive answer
6. Trace: workers_called = ["policy_tool_worker", "synthesis_worker"]
           mcp_tools_used = [search_kb call 1, search_kb call 2]
```

## MCP Integration Design

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Policy Tool Worker                       │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Worker Logic                                        │  │
│  │  • Analyze task                                      │  │
│  │  • Determine if MCP call needed                      │  │
│  │  • Build tool input                                  │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  _call_mcp_tool(tool_name, tool_input)              │  │
│  │  • Import mcp_server.dispatch_tool                   │  │
│  │  • Invoke tool                                       │  │
│  │  • Wrap result with timestamp                        │  │
│  │  • Handle errors gracefully                          │  │
│  └────────────────────┬─────────────────────────────────┘  │
└────────────────────────┼──────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server                             │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  dispatch_tool(tool_name, tool_input)                │  │
│  │  • Lookup tool in TOOL_REGISTRY                      │  │
│  │  • Validate input against schema                     │  │
│  │  • Execute tool function                             │  │
│  │  • Return result or error dict                       │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tool Functions                                      │  │
│  │  • tool_search_kb()                                  │  │
│  │  • tool_get_ticket_info()                            │  │
│  │  • tool_check_access_permission()                    │  │
│  │  • tool_create_ticket()                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### MCP Call Flow

1. **Worker determines tool need**: Based on `needs_tool` flag and task analysis
2. **Worker builds tool input**: Constructs input dict matching tool schema
3. **Worker calls `_call_mcp_tool()`**: Wrapper function handles invocation
4. **MCP server dispatches**: `dispatch_tool()` routes to appropriate tool function
5. **Tool executes**: Performs operation (search, lookup, check, etc.)
6. **Result returned**: Tool output or error dict
7. **Worker logs call**: Appends to `mcp_tools_used` array with timestamp
8. **Worker uses result**: Incorporates tool output into analysis

### Tool Selection Logic

```python
def determine_mcp_tools(task: str, needs_tool: bool, chunks: list) -> list:
    """
    Determines which MCP tools to invoke based on task analysis.
    
    Returns: List of (tool_name, tool_input) tuples
    """
    tools_to_call = []
    task_lower = task.lower()
    
    # Tool 1: search_kb (if no chunks and needs_tool)
    if not chunks and needs_tool:
        tools_to_call.append(("search_kb", {"query": task, "top_k": 3}))
    
    # Tool 2: get_ticket_info (if ticket-related)
    if any(kw in task_lower for kw in ["ticket", "p1", "jira", "sự cố"]):
        tools_to_call.append(("get_ticket_info", {"ticket_id": "P1-LATEST"}))
    
    # Tool 3: check_access_permission (if access control query)
    if any(kw in task_lower for kw in ["cấp quyền", "access", "level"]):
        # Extract level from task (simplified)
        level = 3 if "level 3" in task_lower else 2 if "level 2" in task_lower else 1
        is_emergency = "emergency" in task_lower or "khẩn cấp" in task_lower
        tools_to_call.append(("check_access_permission", {
            "access_level": level,
            "requester_role": "contractor",  # Could be extracted from task
            "is_emergency": is_emergency
        }))
    
    return tools_to_call
```

### Error Handling in MCP Integration

```python
def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Safe MCP tool invocation with error handling.
    """
    from datetime import datetime
    
    try:
        from mcp_server import dispatch_tool
        result = dispatch_tool(tool_name, tool_input)
        
        # Check if result contains error
        if "error" in result:
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": None,
                "error": result,
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }
    
    except ImportError as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_IMPORT_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat()
        }
```


## Error Handling

### Error Handling Philosophy

The system follows a **graceful degradation** approach:
1. **Isolate failures**: Worker errors don't crash the entire pipeline
2. **Log comprehensively**: All errors recorded in `worker_io_logs` and trace
3. **Provide fallbacks**: Empty results instead of exceptions
4. **Enable debugging**: Error codes and reasons for root cause analysis

### Error Categories and Handling

#### 1. Retrieval Worker Errors

**Error Scenarios**:
- ChromaDB connection failure
- Embedding generation failure
- Query execution timeout

**Handling Strategy**:
```python
try:
    chunks = retrieve_dense(task, top_k=top_k)
    state["retrieved_chunks"] = chunks
    state["retrieved_sources"] = list({c["source"] for c in chunks})
except Exception as e:
    worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
    state["retrieved_chunks"] = []
    state["retrieved_sources"] = []
    state["history"].append(f"[retrieval_worker] ERROR: {e}")
```

**Impact**: Synthesis worker will abstain due to empty chunks, confidence=0.0

#### 2. Policy Tool Worker Errors

**Error Scenarios**:
- MCP tool invocation failure
- Policy analysis exception
- Context parsing error

**Handling Strategy**:
```python
try:
    policy_result = analyze_policy(task, chunks)
    state["policy_result"] = policy_result
except Exception as e:
    worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
    state["policy_result"] = {"error": str(e)}
    state["history"].append(f"[policy_tool_worker] ERROR: {e}")
```

**Impact**: Synthesis worker proceeds with retrieval context only, may have lower confidence

#### 3. Synthesis Worker Errors

**Error Scenarios**:
- LLM API failure (rate limit, timeout, auth error)
- Context too large for LLM
- Response parsing failure

**Handling Strategy**:
```python
try:
    result = synthesize(task, chunks, policy_result)
    state["final_answer"] = result["answer"]
    state["confidence"] = result["confidence"]
except Exception as e:
    worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
    state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
    state["confidence"] = 0.0
    state["history"].append(f"[synthesis_worker] ERROR: {e}")
```

**Impact**: User receives error message, trace shows failure point

#### 4. MCP Tool Errors

**Error Scenarios**:
- Tool not found
- Invalid input parameters
- Tool execution failure

**Handling Strategy**:
```python
def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' không tồn tại",
            "available_tools": list(TOOL_REGISTRY.keys())
        }
    
    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**tool_input)
    except TypeError as e:
        return {
            "error": f"Invalid input for tool '{tool_name}': {e}",
            "schema": TOOL_SCHEMAS[tool_name]["inputSchema"]
        }
    except Exception as e:
        return {"error": f"Tool '{tool_name}' execution failed: {e}"}
```

**Impact**: Worker logs error in `mcp_tools_used`, continues with available data

#### 5. Supervisor Routing Errors

**Error Scenarios**:
- Invalid route decision
- Missing route_reason

**Handling Strategy**:
```python
def supervisor_node(state: AgentState) -> AgentState:
    try:
        route, route_reason, risk_high, needs_tool = determine_route(state["task"])
        
        # Validate route_reason is not empty
        if not route_reason or route_reason == "unknown":
            route_reason = "default route: no specific keywords matched"
        
        state["supervisor_route"] = route
        state["route_reason"] = route_reason
        state["risk_high"] = risk_high
        state["needs_tool"] = needs_tool
    except Exception as e:
        # Fallback to safe default
        state["supervisor_route"] = "retrieval_worker"
        state["route_reason"] = f"routing error: {e} → fallback to retrieval"
        state["risk_high"] = False
        state["needs_tool"] = False
        state["history"].append(f"[supervisor] ERROR: {e}")
    
    return state
```

**Impact**: System defaults to retrieval worker, logs error for investigation

### Error Recovery Strategies

#### Strategy 1: Retry with Backoff (LLM Calls)

```python
def _call_llm_with_retry(messages: list, max_retries: int = 3) -> str:
    """
    Retry LLM calls with exponential backoff for transient failures.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            return _call_llm(messages)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            print(f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}")
            print(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
```

#### Strategy 2: Fallback Embeddings

```python
def _get_embedding_fn():
    """
    Try multiple embedding sources with fallback chain.
    """
    # Try 1: Sentence Transformers (offline)
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return lambda text: model.encode([text])[0].tolist()
    except ImportError:
        pass
    
    # Try 2: OpenAI (requires API key)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        def embed(text: str) -> list:
            resp = client.embeddings.create(input=text, model="text-embedding-3-small")
            return resp.data[0].embedding
        return embed
    except Exception:
        pass
    
    # Fallback: Random (test only)
    import random
    print("⚠️  WARNING: Using random embeddings (test only)")
    return lambda text: [random.random() for _ in range(384)]
```

#### Strategy 3: Partial Results

Workers return partial results when possible:

```python
# Example: Policy worker with partial MCP failure
if mcp_result.get("error"):
    # Log error but continue with available chunks
    state["mcp_tools_used"].append(mcp_result)
    state["history"].append(f"[policy_tool_worker] MCP call failed, using available chunks")
    # Continue with policy analysis using existing chunks
```

### Error Logging and Debugging

#### Worker I/O Logs

Every worker appends detailed I/O log:

```python
worker_io = {
    "worker": WORKER_NAME,
    "input": {
        "task": task,
        "chunks_count": len(chunks),
        "needs_tool": needs_tool
    },
    "output": {
        "policy_applies": True,
        "exceptions_count": 1
    } if success else None,
    "error": {
        "code": "POLICY_CHECK_FAILED",
        "reason": "LLM timeout after 3 retries"
    } if error else None
}
state["worker_io_logs"].append(worker_io)
```

#### History Timeline

Chronological execution log:

```python
state["history"] = [
    "[supervisor] received task: SLA ticket P1 là bao lâu?",
    "[supervisor] route=retrieval_worker reason=task contains SLA keyword",
    "[retrieval_worker] called",
    "[retrieval_worker] retrieved 3 chunks from ['sla_p1_2026.txt']",
    "[synthesis_worker] called",
    "[synthesis_worker] answer generated, confidence=0.88"
]
```

#### Error Debug Tree

When debugging failures, follow this decision tree:

```
Pipeline returned wrong answer?
│
├─ Check trace: supervisor_route correct?
│  ├─ No → Fix routing logic in supervisor_node
│  └─ Yes → Continue
│
├─ Check worker_io_logs: which worker failed?
│  ├─ retrieval_worker → Check ChromaDB connection, embedding model
│  ├─ policy_tool_worker → Check MCP tools, policy analysis logic
│  └─ synthesis_worker → Check LLM API, prompt, context size
│
├─ Check mcp_tools_used: any MCP errors?
│  ├─ Yes → Check MCP server logs, tool implementation
│  └─ No → Continue
│
└─ Check confidence score: too low?
   ├─ Yes → Check chunk relevance scores, policy exceptions
   └─ No → Check synthesis prompt, LLM temperature
```

### Performance Monitoring

#### Latency Tracking

```python
import time

def run_graph(task: str) -> AgentState:
    start = time.time()
    state = make_initial_state(task)
    
    # Execute pipeline
    result = _graph(state)
    
    # Record latency
    result["latency_ms"] = int((time.time() - start) * 1000)
    
    # Performance warning
    if result["latency_ms"] > 5000:
        print(f"⚠️  Performance warning: {result['latency_ms']}ms (threshold: 5000ms)")
    
    return result
```

#### Worker-Level Timing

```python
def retrieval_worker_node(state: AgentState) -> AgentState:
    import time
    start = time.time()
    
    # Worker logic
    state = retrieval_run(state)
    
    # Record worker latency
    worker_latency = int((time.time() - start) * 1000)
    state["history"].append(f"[retrieval_worker] completed in {worker_latency}ms")
    
    return state
```


## Testing Strategy

### Testing Approach Overview

This system is **NOT suitable for property-based testing** because:
1. Heavy reliance on external services (ChromaDB, LLM APIs, MCP tools)
2. Configuration-based routing logic rather than algorithmic transformations
3. Integration-focused behavior with side effects
4. Non-deterministic LLM outputs

**Testing Strategy**: Combination of unit tests, integration tests, and trace-based validation.

### Unit Testing

#### 1. Supervisor Routing Logic

**Test Coverage**:
- Policy keyword detection
- Risk flag setting
- Route reason generation
- Default routing behavior

**Example Tests**:
```python
def test_supervisor_routes_policy_query():
    state = make_initial_state("Khách hàng Flash Sale yêu cầu hoàn tiền")
    result = supervisor_node(state)
    
    assert result["supervisor_route"] == "policy_tool_worker"
    assert "policy keyword" in result["route_reason"]
    assert result["needs_tool"] == True

def test_supervisor_routes_sla_query():
    state = make_initial_state("SLA ticket P1 là bao lâu?")
    result = supervisor_node(state)
    
    assert result["supervisor_route"] == "retrieval_worker"
    assert "SLA keyword" in result["route_reason"]

def test_supervisor_triggers_hitl_for_high_risk():
    state = make_initial_state("ERR-9847 khẩn cấp lúc 2am")
    result = supervisor_node(state)
    
    assert result["supervisor_route"] == "human_review"
    assert result["risk_high"] == True
    assert "unknown error code" in result["route_reason"]

def test_supervisor_never_returns_empty_route_reason():
    state = make_initial_state("random query without keywords")
    result = supervisor_node(state)
    
    assert result["route_reason"] != ""
    assert result["route_reason"] != "unknown"
```

#### 2. Worker Contract Compliance

**Test Coverage**:
- Input validation
- Output format compliance
- Error handling
- Stateless operation

**Example Tests**:
```python
def test_retrieval_worker_returns_valid_chunks():
    state = {"task": "SLA P1", "history": [], "workers_called": []}
    result = retrieval_run(state)
    
    assert "retrieved_chunks" in result
    assert isinstance(result["retrieved_chunks"], list)
    for chunk in result["retrieved_chunks"]:
        assert "text" in chunk
        assert "source" in chunk
        assert "score" in chunk
        assert 0.0 <= chunk["score"] <= 1.0

def test_retrieval_worker_handles_empty_results():
    state = {"task": "nonexistent query xyz123", "history": [], "workers_called": []}
    result = retrieval_run(state)
    
    assert result["retrieved_chunks"] == []
    assert result["retrieved_sources"] == []
    assert "retrieval_worker" in result["workers_called"]

def test_policy_worker_detects_flash_sale_exception():
    state = {
        "task": "Flash Sale refund request",
        "retrieved_chunks": [
            {"text": "Flash Sale orders not eligible for refund", "source": "policy_refund_v4.txt", "score": 0.9}
        ],
        "history": [],
        "workers_called": []
    }
    result = policy_tool_run(state)
    
    assert result["policy_result"]["policy_applies"] == False
    assert len(result["policy_result"]["exceptions_found"]) > 0
    assert any(ex["type"] == "flash_sale_exception" for ex in result["policy_result"]["exceptions_found"])

def test_synthesis_worker_abstains_without_chunks():
    state = {
        "task": "What is the refund policy?",
        "retrieved_chunks": [],
        "policy_result": {},
        "history": [],
        "workers_called": []
    }
    result = synthesis_run(state)
    
    assert "Không đủ thông tin" in result["final_answer"]
    assert result["confidence"] < 0.5
    assert result["sources"] == []
```

#### 3. MCP Tool Functions

**Test Coverage**:
- Tool discovery
- Input validation
- Output format
- Error handling

**Example Tests**:
```python
def test_mcp_list_tools_returns_schemas():
    tools = list_tools()
    
    assert len(tools) >= 2
    assert any(t["name"] == "search_kb" for t in tools)
    assert any(t["name"] == "get_ticket_info" for t in tools)
    
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "outputSchema" in tool

def test_mcp_search_kb_returns_chunks():
    result = dispatch_tool("search_kb", {"query": "SLA P1", "top_k": 3})
    
    assert "chunks" in result
    assert "sources" in result
    assert "total_found" in result
    assert isinstance(result["chunks"], list)

def test_mcp_invalid_tool_returns_error():
    result = dispatch_tool("nonexistent_tool", {})
    
    assert "error" in result
    assert "không tồn tại" in result["error"]

def test_mcp_get_ticket_info_returns_mock_data():
    result = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
    
    assert "ticket_id" in result
    assert "priority" in result
    assert result["priority"] == "P1"
```

### Integration Testing

#### 1. End-to-End Pipeline Tests

**Test Coverage**:
- Complete query execution
- Worker coordination
- Trace generation
- Multi-hop queries

**Example Tests**:
```python
def test_e2e_simple_retrieval_query():
    result = run_graph("SLA ticket P1 là bao lâu?")
    
    assert result["supervisor_route"] == "retrieval_worker"
    assert len(result["retrieved_chunks"]) > 0
    assert result["final_answer"] != ""
    assert result["confidence"] > 0.5
    assert "retrieval_worker" in result["workers_called"]
    assert "synthesis_worker" in result["workers_called"]

def test_e2e_policy_query_with_exception():
    result = run_graph("Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi")
    
    assert result["supervisor_route"] == "policy_tool_worker"
    assert result["policy_result"]["policy_applies"] == False
    assert len(result["policy_result"]["exceptions_found"]) > 0
    assert "Flash Sale" in result["final_answer"] or "flash sale" in result["final_answer"].lower()

def test_e2e_multi_hop_query():
    result = run_graph("P1 lúc 2am + cần cấp quyền Level 2 tạm thời cho contractor")
    
    assert result["risk_high"] == True
    assert len(result["workers_called"]) >= 2
    assert len(result["mcp_tools_used"]) > 0
    assert len(result["retrieved_sources"]) > 1  # Multiple documents

def test_e2e_abstention_case():
    result = run_graph("What is the financial penalty for SLA P1 violation?")
    
    assert "Không đủ thông tin" in result["final_answer"] or result["confidence"] < 0.4
    # System should abstain since this info is not in documents
```

#### 2. MCP Integration Tests

**Test Coverage**:
- Worker-to-MCP communication
- Tool call logging
- Error propagation

**Example Tests**:
```python
def test_policy_worker_calls_mcp_search_kb():
    state = {
        "task": "Refund policy for digital products",
        "retrieved_chunks": [],
        "needs_tool": True,
        "history": [],
        "workers_called": [],
        "mcp_tools_used": []
    }
    result = policy_tool_run(state)
    
    assert len(result["mcp_tools_used"]) > 0
    assert any(call["tool"] == "search_kb" for call in result["mcp_tools_used"])

def test_mcp_error_does_not_crash_worker():
    # Simulate MCP failure by calling with invalid tool
    state = {
        "task": "Test query",
        "needs_tool": True,
        "history": [],
        "workers_called": [],
        "mcp_tools_used": []
    }
    
    # Worker should handle MCP error gracefully
    result = policy_tool_run(state)
    
    assert "policy_tool_worker" in result["workers_called"]
    # Check if error was logged
    if result["mcp_tools_used"]:
        # If MCP was called, check for error handling
        assert all("error" in call or "output" in call for call in result["mcp_tools_used"])
```

### Trace-Based Validation

#### 1. Trace Completeness Tests

**Test Coverage**:
- All required fields present
- Trace file creation
- JSONL format for grading

**Example Tests**:
```python
def test_trace_contains_required_fields():
    result = run_graph("Test query")
    
    required_fields = [
        "run_id", "task", "supervisor_route", "route_reason",
        "workers_called", "mcp_tools_used", "retrieved_sources",
        "final_answer", "sources", "confidence", "hitl_triggered",
        "latency_ms", "timestamp"
    ]
    
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"

def test_trace_file_saved():
    result = run_graph("Test query")
    trace_file = save_trace(result)
    
    assert os.path.exists(trace_file)
    
    with open(trace_file) as f:
        saved_trace = json.load(f)
    
    assert saved_trace["run_id"] == result["run_id"]
    assert saved_trace["task"] == result["task"]

def test_grading_trace_jsonl_format():
    questions = [
        {"id": "test01", "question": "Query 1"},
        {"id": "test02", "question": "Query 2"}
    ]
    
    output_file = "artifacts/test_grading_run.jsonl"
    with open(output_file, "w") as f:
        for q in questions:
            result = run_graph(q["question"])
            record = {
                "id": q["id"],
                "question": q["question"],
                "answer": result["final_answer"],
                "sources": result["sources"],
                "supervisor_route": result["supervisor_route"],
                "route_reason": result["route_reason"],
                "workers_called": result["workers_called"],
                "mcp_tools_used": result["mcp_tools_used"],
                "confidence": result["confidence"],
                "hitl_triggered": result["hitl_triggered"],
                "timestamp": result.get("timestamp", datetime.now().isoformat())
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # Validate JSONL format
    with open(output_file) as f:
        lines = f.readlines()
        assert len(lines) == len(questions)
        for line in lines:
            record = json.loads(line)
            assert "id" in record
            assert "answer" in record
```

#### 2. Routing Decision Validation

**Test Coverage**:
- Route reason quality
- Routing accuracy
- Multi-hop detection

**Example Tests**:
```python
def test_route_reason_is_descriptive():
    test_queries = [
        "SLA P1 là bao lâu?",
        "Flash Sale refund policy",
        "ERR-9847 khẩn cấp"
    ]
    
    for query in test_queries:
        result = run_graph(query)
        
        assert result["route_reason"] != ""
        assert result["route_reason"] != "unknown"
        assert len(result["route_reason"]) > 10  # Reasonably descriptive

def test_routing_distribution():
    test_queries = [
        ("SLA P1", "retrieval_worker"),
        ("Refund policy", "policy_tool_worker"),
        ("ERR-123 emergency", "human_review")
    ]
    
    for query, expected_route in test_queries:
        result = run_graph(query)
        assert result["supervisor_route"] == expected_route, \
            f"Query '{query}' routed to {result['supervisor_route']}, expected {expected_route}"
```

### Performance Testing

#### 1. Latency Benchmarks

**Test Coverage**:
- End-to-end latency
- Worker-level timing
- Performance regression

**Example Tests**:
```python
def test_simple_query_latency_under_threshold():
    result = run_graph("SLA P1 là bao lâu?")
    
    assert result["latency_ms"] < 5000, \
        f"Query took {result['latency_ms']}ms, threshold is 5000ms"

def test_multi_hop_query_latency():
    result = run_graph("P1 lúc 2am + cần cấp quyền Level 2")
    
    # Multi-hop queries allowed higher latency
    assert result["latency_ms"] < 10000, \
        f"Multi-hop query took {result['latency_ms']}ms, threshold is 10000ms"

def test_latency_statistics():
    queries = [
        "SLA P1",
        "Refund policy",
        "Access control Level 3",
        "Ticket escalation",
        "Flash Sale exception"
    ]
    
    latencies = []
    for query in queries:
        result = run_graph(query)
        latencies.append(result["latency_ms"])
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    print(f"Average latency: {avg_latency:.0f}ms")
    print(f"Max latency: {max_latency}ms")
    
    assert avg_latency < 3000, "Average latency too high"
    assert max_latency < 8000, "Max latency too high"
```

### Test Execution Strategy

#### Development Phase
```bash
# Unit tests (fast, no external dependencies)
pytest tests/unit/ -v

# Integration tests (requires ChromaDB, API keys)
pytest tests/integration/ -v --slow

# Trace validation
pytest tests/trace/ -v
```

#### Pre-Grading Validation
```bash
# Run with test questions
python eval_trace.py --input data/test_questions.json --output artifacts/test_run.jsonl

# Validate trace format
python -m tests.validate_trace artifacts/test_run.jsonl

# Check routing accuracy
python -m tests.analyze_routing artifacts/test_run.jsonl
```

#### Grading Execution
```bash
# Process grading questions (17:00-18:00)
python eval_trace.py --input data/grading_questions.json --output artifacts/grading_run.jsonl

# Validate submission
python -m tests.validate_submission artifacts/grading_run.jsonl
```

### Test Data Management

#### Mock Data for Unit Tests
```python
MOCK_CHUNKS = [
    {
        "text": "SLA P1: Phản hồi 15 phút, xử lý 4 giờ",
        "source": "sla_p1_2026.txt",
        "score": 0.92,
        "metadata": {"section": "P1_requirements"}
    },
    {
        "text": "Flash Sale orders not eligible for refund",
        "source": "policy_refund_v4.txt",
        "score": 0.88,
        "metadata": {"section": "exceptions"}
    }
]

MOCK_POLICY_RESULT = {
    "policy_applies": False,
    "policy_name": "refund_policy_v4",
    "exceptions_found": [
        {
            "type": "flash_sale_exception",
            "rule": "Flash Sale không được hoàn tiền",
            "source": "policy_refund_v4.txt"
        }
    ],
    "source": ["policy_refund_v4.txt"]
}
```

#### Test Questions Coverage
- **Simple retrieval**: 5 questions (SLA, FAQ, HR policy)
- **Policy with exceptions**: 3 questions (Flash Sale, digital product, activated)
- **Multi-hop**: 2 questions (P1 + access control, temporal scoping)
- **Abstention**: 2 questions (info not in docs)
- **Edge cases**: 3 questions (unknown error codes, emergency scenarios)

### Continuous Validation

#### Pre-commit Checks
```bash
# Format validation
black graph.py workers/*.py mcp_server.py eval_trace.py

# Type checking
mypy graph.py workers/*.py --strict

# Contract validation
python -m tests.validate_contracts contracts/worker_contracts.yaml

# Quick smoke test
python graph.py
```

#### CI/CD Pipeline
1. **Lint**: flake8, black, mypy
2. **Unit tests**: Fast tests without external dependencies
3. **Integration tests**: With mock ChromaDB and LLM
4. **Trace validation**: Check trace format compliance
5. **Performance benchmarks**: Track latency trends


## Performance Considerations

### Latency Optimization

#### 1. Embedding Caching

**Problem**: Repeated embedding generation for similar queries is expensive.

**Solution**: Cache embeddings with TTL.

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def get_cached_embedding(text: str) -> tuple:
    """
    Cache embeddings for frequently queried text.
    Returns tuple for hashability.
    """
    embed_fn = _get_embedding_fn()
    embedding = embed_fn(text)
    return tuple(embedding)

def retrieve_dense(query: str, top_k: int = 3) -> list:
    # Use cached embedding
    query_embedding = list(get_cached_embedding(query))
    
    collection = _get_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    # ... rest of implementation
```

**Impact**: 50-80% latency reduction for repeated queries.

#### 2. Parallel Worker Execution

**Problem**: Sequential worker execution increases total latency.

**Solution**: Execute independent workers in parallel when possible.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_graph_parallel(task: str) -> AgentState:
    """
    Parallel execution for independent workers.
    """
    state = make_initial_state(task)
    state = supervisor_node(state)
    
    route = route_decision(state)
    
    if route == "policy_tool_worker":
        # Policy worker may need retrieval context
        # Execute retrieval and policy analysis in parallel if possible
        with ThreadPoolExecutor(max_workers=2) as executor:
            retrieval_future = executor.submit(retrieval_worker_node, state.copy())
            
            # Wait for retrieval to complete
            retrieval_result = retrieval_future.result()
            
            # Now run policy with retrieval context
            state.update(retrieval_result)
            state = policy_tool_worker_node(state)
    else:
        state = retrieval_worker_node(state)
    
    state = synthesis_worker_node(state)
    return state
```

**Caution**: Ensure thread-safety for shared state modifications.

#### 3. ChromaDB Query Optimization

**Problem**: Large collections slow down similarity search.

**Solution**: Use HNSW index parameters and query filters.

```python
def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_db")
    
    collection = client.get_or_create_collection(
        "day09_docs",
        metadata={
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,  # Higher = better recall, slower build
            "hnsw:search_ef": 100,        # Higher = better recall, slower search
            "hnsw:M": 16                  # Higher = better recall, more memory
        }
    )
    return collection

def retrieve_dense_filtered(query: str, source_filter: str = None, top_k: int = 3) -> list:
    """
    Retrieve with optional source filtering for faster search.
    """
    embed = _get_embedding_fn()
    query_embedding = embed(query)
    
    collection = _get_collection()
    
    # Apply metadata filter if specified
    where_filter = {"source": source_filter} if source_filter else None
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter
    )
    # ... format results
```

**Impact**: 30-50% faster queries with appropriate HNSW parameters.

#### 4. LLM Response Streaming

**Problem**: Waiting for complete LLM response increases perceived latency.

**Solution**: Stream LLM responses for faster time-to-first-token.

```python
def _call_llm_streaming(messages: list) -> str:
    """
    Stream LLM response for lower latency.
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1,
        stream=True
    )
    
    chunks = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            # Could yield here for real-time display
    
    return "".join(chunks)
```

**Impact**: Reduces time-to-first-token by 40-60%.

### Memory Optimization

#### 1. Chunk Size Management

**Problem**: Large chunks consume memory and slow down LLM processing.

**Solution**: Limit chunk size and count.

```python
MAX_CHUNK_SIZE = 500  # characters
MAX_CHUNKS_FOR_SYNTHESIS = 5

def retrieve_dense(query: str, top_k: int = 3) -> list:
    # ... retrieve chunks
    
    # Truncate oversized chunks
    for chunk in chunks:
        if len(chunk["text"]) > MAX_CHUNK_SIZE:
            chunk["text"] = chunk["text"][:MAX_CHUNK_SIZE] + "..."
    
    return chunks[:MAX_CHUNKS_FOR_SYNTHESIS]
```

#### 2. State Pruning

**Problem**: AgentState accumulates large history and logs.

**Solution**: Prune verbose fields before trace save.

```python
def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """
    Save trace with pruned verbose fields.
    """
    # Create pruned copy
    trace = {
        "run_id": state["run_id"],
        "task": state["task"],
        "supervisor_route": state["supervisor_route"],
        "route_reason": state["route_reason"],
        "workers_called": state["workers_called"],
        "mcp_tools_used": state["mcp_tools_used"],
        "retrieved_sources": state["retrieved_sources"],
        "final_answer": state["final_answer"],
        "sources": state["sources"],
        "confidence": state["confidence"],
        "hitl_triggered": state["hitl_triggered"],
        "latency_ms": state["latency_ms"],
        "timestamp": state.get("timestamp", datetime.now().isoformat())
    }
    
    # Optionally include history for debugging (truncated)
    if state.get("history"):
        trace["history"] = state["history"][-10:]  # Last 10 entries only
    
    # Save
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    
    return filename
```

### Scalability Considerations

#### 1. Concurrent Query Handling

**Problem**: Single-threaded execution limits throughput.

**Solution**: Process multiple queries concurrently.

```python
from concurrent.futures import ThreadPoolExecutor

def process_grading_questions_parallel(questions: list, max_workers: int = 4) -> list:
    """
    Process grading questions in parallel for faster completion.
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_question = {
            executor.submit(run_graph, q["question"]): q
            for q in questions
        }
        
        for future in as_completed(future_to_question):
            question = future_to_question[future]
            try:
                result = future.result()
                results.append({
                    "id": question["id"],
                    "question": question["question"],
                    "answer": result["final_answer"],
                    "sources": result["sources"],
                    "supervisor_route": result["supervisor_route"],
                    "route_reason": result["route_reason"],
                    "workers_called": result["workers_called"],
                    "mcp_tools_used": result["mcp_tools_used"],
                    "confidence": result["confidence"],
                    "hitl_triggered": result["hitl_triggered"],
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                results.append({
                    "id": question["id"],
                    "question": question["question"],
                    "answer": f"PIPELINE_ERROR: {e}",
                    "error": str(e)
                })
    
    return results
```

**Impact**: 3-4x throughput improvement with 4 workers.

#### 2. ChromaDB Connection Pooling

**Problem**: Creating new ChromaDB connections for each query is expensive.

**Solution**: Reuse persistent client connection.

```python
# Global connection (initialized once)
_chroma_client = None
_chroma_collection = None

def _get_collection():
    """
    Get or create ChromaDB collection with connection reuse.
    """
    global _chroma_client, _chroma_collection
    
    if _chroma_collection is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path="./chroma_db")
        _chroma_collection = _chroma_client.get_or_create_collection(
            "day09_docs",
            metadata={"hnsw:space": "cosine"}
        )
    
    return _chroma_collection
```

#### 3. Rate Limiting for LLM APIs

**Problem**: Exceeding API rate limits causes failures.

**Solution**: Implement rate limiting with token bucket algorithm.

```python
import time
from threading import Lock

class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self.lock = Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            # Remove calls outside the period
            self.calls = [c for c in self.calls if now - c < self.period]
            
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    self.calls = []
            
            self.calls.append(time.time())

# Global rate limiter: 60 calls per minute
_llm_rate_limiter = RateLimiter(max_calls=60, period=60.0)

def _call_llm(messages: list) -> str:
    """
    Call LLM with rate limiting.
    """
    _llm_rate_limiter.wait_if_needed()
    
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1
    )
    return response.choices[0].message.content
```

### Resource Management

#### 1. Graceful Shutdown

**Problem**: Abrupt termination may leave resources in inconsistent state.

**Solution**: Implement cleanup handlers.

```python
import atexit
import signal

def cleanup():
    """
    Cleanup resources on shutdown.
    """
    global _chroma_client
    if _chroma_client:
        print("Closing ChromaDB connection...")
        # ChromaDB client cleanup if needed
        _chroma_client = None

# Register cleanup handlers
atexit.register(cleanup)
signal.signal(signal.SIGINT, lambda s, f: cleanup())
signal.signal(signal.SIGTERM, lambda s, f: cleanup())
```

#### 2. Disk Space Management

**Problem**: Trace files accumulate and consume disk space.

**Solution**: Implement trace rotation and cleanup.

```python
import os
import time

def cleanup_old_traces(trace_dir: str = "./artifacts/traces", max_age_days: int = 7):
    """
    Remove trace files older than max_age_days.
    """
    now = time.time()
    max_age_seconds = max_age_days * 86400
    
    for filename in os.listdir(trace_dir):
        filepath = os.path.join(trace_dir, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                os.remove(filepath)
                print(f"Removed old trace: {filename}")
```

### Monitoring and Observability

#### 1. Performance Metrics Collection

```python
class PerformanceMetrics:
    def __init__(self):
        self.query_count = 0
        self.total_latency = 0
        self.worker_latencies = {}
        self.error_count = 0
    
    def record_query(self, latency_ms: int, workers_called: list):
        self.query_count += 1
        self.total_latency += latency_ms
        
        for worker in workers_called:
            if worker not in self.worker_latencies:
                self.worker_latencies[worker] = []
            # Would need per-worker timing in production
    
    def record_error(self):
        self.error_count += 1
    
    def get_stats(self) -> dict:
        return {
            "query_count": self.query_count,
            "avg_latency_ms": self.total_latency / self.query_count if self.query_count > 0 else 0,
            "error_rate": self.error_count / self.query_count if self.query_count > 0 else 0,
            "worker_usage": self.worker_latencies
        }

# Global metrics instance
_metrics = PerformanceMetrics()

def run_graph(task: str) -> AgentState:
    import time
    start = time.time()
    
    try:
        state = make_initial_state(task)
        result = _graph(state)
        result["latency_ms"] = int((time.time() - start) * 1000)
        
        # Record metrics
        _metrics.record_query(result["latency_ms"], result["workers_called"])
        
        return result
    except Exception as e:
        _metrics.record_error()
        raise
```

#### 2. Health Check Endpoint

For production deployment:

```python
def health_check() -> dict:
    """
    System health check for monitoring.
    """
    health = {
        "status": "healthy",
        "checks": {}
    }
    
    # Check ChromaDB connection
    try:
        collection = _get_collection()
        health["checks"]["chromadb"] = "ok"
    except Exception as e:
        health["checks"]["chromadb"] = f"error: {e}"
        health["status"] = "degraded"
    
    # Check LLM API
    try:
        _call_llm([{"role": "user", "content": "test"}])
        health["checks"]["llm_api"] = "ok"
    except Exception as e:
        health["checks"]["llm_api"] = f"error: {e}"
        health["status"] = "degraded"
    
    # Check MCP server
    try:
        list_tools()
        health["checks"]["mcp_server"] = "ok"
    except Exception as e:
        health["checks"]["mcp_server"] = f"error: {e}"
        health["status"] = "degraded"
    
    # Add metrics
    health["metrics"] = _metrics.get_stats()
    
    return health
```

### Performance Benchmarks

Expected performance targets:

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Simple query latency | < 2s | < 5s | > 10s |
| Multi-hop query latency | < 5s | < 10s | > 20s |
| Throughput (queries/min) | > 30 | > 15 | < 10 |
| Memory usage | < 500MB | < 1GB | > 2GB |
| Error rate | < 1% | < 5% | > 10% |
| Confidence score (avg) | > 0.7 | > 0.5 | < 0.3 |

### Optimization Checklist

Before grading submission:

- [ ] Enable embedding caching
- [ ] Optimize ChromaDB HNSW parameters
- [ ] Implement parallel grading question processing
- [ ] Add rate limiting for LLM calls
- [ ] Prune verbose trace fields
- [ ] Test with full 10-question grading set
- [ ] Verify average latency < 5s per query
- [ ] Check memory usage stays under 1GB
- [ ] Validate all traces have required fields
- [ ] Run performance benchmark suite

## Implementation Roadmap

### Sprint 1: Supervisor and Graph (60 minutes)

**Deliverables**:
- `graph.py` with `AgentState`, `supervisor_node`, `route_decision`
- Basic routing logic with keyword matching
- Placeholder worker nodes
- Manual test with 2-3 queries

**Success Criteria**:
- `python graph.py` runs without errors
- Supervisor routes correctly for policy vs retrieval queries
- `route_reason` is descriptive (not "unknown")
- Trace includes routing decision

### Sprint 2: Workers (60 minutes)

**Deliverables**:
- `workers/retrieval.py` with ChromaDB integration
- `workers/policy_tool.py` with exception detection
- `workers/synthesis.py` with LLM call
- `contracts/worker_contracts.yaml` completed

**Success Criteria**:
- Each worker tests independently
- Retrieval returns chunks with scores
- Policy detects Flash Sale exception
- Synthesis generates answer with citations
- All workers log I/O to state

### Sprint 3: MCP Integration (60 minutes)

**Deliverables**:
- `mcp_server.py` with 2+ tools implemented
- Policy worker calls MCP tools
- MCP tool calls logged in trace

**Success Criteria**:
- `list_tools()` returns tool schemas
- `dispatch_tool()` executes tools correctly
- Policy worker invokes `search_kb` when needed
- `mcp_tools_used` array populated in trace

### Sprint 4: Trace and Documentation (60 minutes)

**Deliverables**:
- `eval_trace.py` processes test questions
- Trace files saved to `artifacts/traces/`
- `docs/system_architecture.md` completed
- `docs/routing_decisions.md` with 3+ examples
- `docs/single_vs_multi_comparison.md` with metrics
- `reports/group_report.md` and individual reports

**Success Criteria**:
- 15 test questions processed successfully
- All traces have required fields
- Routing decisions documented with actual examples
- Comparison shows multi-agent advantages
- Reports submitted before deadline

## Conclusion

This design provides a comprehensive blueprint for implementing a multi-agent orchestration system using the Supervisor-Worker pattern. Key design principles include:

1. **Modularity**: Clear separation of concerns with independent, testable workers
2. **Traceability**: Complete execution logs for debugging and analysis
3. **Extensibility**: Easy addition of new workers and MCP tools
4. **Reliability**: Graceful error handling without cascading failures
5. **Performance**: Optimizations for latency, memory, and throughput

The system is designed to handle single-hop and multi-hop queries across five internal documents, with proper abstention when information is unavailable. The contract-based worker interfaces ensure consistency and enable independent testing, while the MCP integration provides a clean abstraction for external capabilities.

Implementation follows a four-sprint roadmap, with each sprint building on the previous one and delivering testable increments. The testing strategy emphasizes unit tests for individual components, integration tests for end-to-end flows, and trace-based validation for routing decisions and system behavior.

