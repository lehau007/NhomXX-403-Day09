# Implementation Plan: Multi-Agent Orchestration Lab

## Overview

This implementation plan breaks down the multi-agent orchestration system into actionable tasks following the 4-sprint structure from the lab. The system refactors a monolithic RAG pipeline into a Supervisor-Worker pattern with specialized agents (retrieval, policy checking, synthesis) coordinated through a supervisor orchestrator.

**Implementation Language:** Python

**Key Components:**
- Supervisor node with routing logic
- Three specialized workers (retrieval, policy tool, synthesis)
- MCP server with external capabilities
- Trace generation and evaluation system
- Documentation and reporting

## Tasks

### Sprint 1: Supervisor & Graph (60 minutes)

- [ ] 1. Set up project structure and dependencies
  - Create directory structure: `workers/`, `contracts/`, `data/docs/`, `artifacts/traces/`, `docs/`, `reports/individual/`
  - Create `requirements.txt` with dependencies: `chromadb`, `sentence-transformers`, `openai`, `langgraph`, `pyyaml`
  - Create `.env.example` file with API key placeholders
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [ ] 2. Implement AgentState TypedDict
  - [ ] 2.1 Define AgentState in `graph.py` with all required fields
    - Include input fields: `task`
    - Include supervisor decision fields: `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`, `hitl_triggered`
    - Include worker output fields: `retrieved_chunks`, `retrieved_sources`, `policy_result`, `mcp_tools_used`
    - Include final output fields: `final_answer`, `sources`, `confidence`
    - Include trace metadata fields: `history`, `workers_called`, `worker_io_logs`, `latency_ms`, `run_id`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [ ] 3. Implement supervisor routing logic
  - [ ] 3.1 Create `determine_route()` function with keyword-based routing
    - Define policy keywords: "hoàn tiền", "refund", "flash sale", "license", "cấp quyền", "access", "level"
    - Define risk keywords: "emergency", "khẩn cấp", "2am", "err-"
    - Define SLA keywords: "P1", "escalation", "sla", "ticket"
    - Return tuple: (route, route_reason, risk_high, needs_tool)
    - Ensure route_reason is never empty or "unknown"
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ] 3.2 Implement `supervisor_node()` function
    - Call `determine_route()` with task
    - Set `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` in state
    - Append routing decision to `history`
    - Handle routing errors with fallback to retrieval_worker
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [ ] 4. Implement route_decision function
  - [ ] 4.1 Create conditional routing logic
    - Route to "human_review" if risk_high AND unknown error code
    - Route to "policy_tool_worker" if policy keywords present
    - Route to "retrieval_worker" for SLA keywords or default
    - Return worker name string for graph routing
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [ ] 5. Create graph structure with LangGraph
  - [ ] 5.1 Define graph nodes and edges
    - Add supervisor_node as entry point
    - Add route_decision as conditional edge
    - Add placeholder worker nodes (retrieval_worker_node, policy_tool_worker_node, human_review_node)
    - Add synthesis_worker_node as final step
    - Connect nodes: START → supervisor → route_decision → [workers] → synthesis → END
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ] 5.2 Implement `make_initial_state()` helper function
    - Create AgentState with task and run_id
    - Initialize empty arrays and default values
    - Generate unique run_id with timestamp
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ] 5.3 Implement `run_graph()` entry point function
    - Accept task string parameter
    - Create initial state
    - Record start timestamp
    - Invoke graph with state
    - Calculate latency_ms
    - Return final state
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 13.1, 13.2, 13.3, 13.4_

- [ ] 6. Test supervisor routing with 2 queries
  - [ ] 6.1 Create test script in `graph.py` main block
    - Test query 1: "SLA ticket P1 là bao lâu?" (should route to retrieval_worker)
    - Test query 2: "Khách hàng Flash Sale yêu cầu hoàn tiền" (should route to policy_tool_worker)
    - Print supervisor_route and route_reason for each
    - Verify route_reason is descriptive
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [ ] 7. Checkpoint - Ensure supervisor routing works correctly
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 2: Workers (60 minutes)

- [ ] 8. Implement Retrieval Worker
  - [ ] 8.1 Create `workers/retrieval.py` with ChromaDB integration
    - Implement `_get_collection()` to connect to ChromaDB
    - Implement `_get_embedding_fn()` with fallback chain (SentenceTransformers → OpenAI → random for testing)
    - Implement `retrieve_dense()` function to query ChromaDB
    - Format results as chunks with text, source, score, metadata
    - Calculate score as `1 - cosine_distance`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ] 8.2 Implement `run()` function for retrieval worker
    - Extract task from state
    - Call `retrieve_dense()` with task and top_k=3
    - Set `retrieved_chunks` in state
    - Extract unique sources into `retrieved_sources`
    - Append worker name to `workers_called`
    - Create worker_io_log entry with input/output
    - Append worker_io_log to state
    - Handle errors gracefully (return empty chunks on failure)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 14.1, 14.2_

  - [ ] 8.3 Create `retrieval_worker_node()` wrapper for graph
    - Call `run()` function
    - Append execution log to history
    - Return updated state
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [ ] 9. Implement Policy Tool Worker
  - [ ] 9.1 Create `workers/policy_tool.py` with policy analysis logic
    - Implement `analyze_policy()` function to detect policy rules
    - Detect Flash Sale exception: check for "flash sale" in task or chunks
    - Detect Digital Product exception: check for "license key", "subscription", "kỹ thuật số"
    - Detect Activated Product exception: check for "đã kích hoạt", "đã đăng ký"
    - Return policy_result dict with policy_applies, policy_name, exceptions_found, source
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 9.2 Implement MCP tool invocation in policy worker
    - Create `_call_mcp_tool()` helper function
    - Import `dispatch_tool` from mcp_server
    - Wrap tool call with timestamp and error handling
    - Return tool call record with tool, input, output, error, timestamp
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 9.3 Implement `determine_mcp_tools()` function
    - Check if needs_tool flag is true
    - If no chunks and needs_tool, call search_kb
    - If ticket-related query, call get_ticket_info
    - If access control query, call check_access_permission
    - Return list of (tool_name, tool_input) tuples
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 9.4 Implement `run()` function for policy tool worker
    - Extract task, retrieved_chunks, needs_tool from state
    - Determine which MCP tools to call
    - Invoke MCP tools and collect results in mcp_tools_used
    - Analyze policy with chunks and MCP results
    - Set policy_result in state
    - Append worker name to workers_called
    - Create worker_io_log entry
    - Handle errors gracefully
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 14.1, 14.3_

  - [ ] 9.5 Create `policy_tool_worker_node()` wrapper for graph
    - Call `run()` function
    - Append execution log to history
    - Return updated state
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 10. Implement Synthesis Worker
  - [ ] 10.1 Create `workers/synthesis.py` with LLM integration
    - Implement `_call_llm()` function with OpenAI API
    - Use model "gpt-4o-mini" with temperature 0.1
    - Implement retry logic with exponential backoff (3 retries)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ] 10.2 Implement prompt construction for synthesis
    - Create SYSTEM_PROMPT with strict grounding rules
    - Include Vietnamese instructions: "CHỈ trả lời dựa vào context được cung cấp"
    - Require inline citations with [source_name] format
    - Instruct to state "Không đủ thông tin" if context insufficient
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ] 10.3 Implement context building from chunks and policy
    - Format retrieved_chunks with source and score
    - Append policy exceptions if present
    - Build structured context string for LLM
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ] 10.4 Implement confidence estimation
    - Return 0.0 if no chunks available
    - Return 0.3 if answer contains "Không đủ thông tin"
    - Calculate average chunk score
    - Apply penalty for policy exceptions (0.05 per exception)
    - Clamp confidence between 0.1 and 0.95
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ] 10.5 Implement abstention behavior
    - Check if retrieved_chunks is empty
    - Generate abstention message: "Không đủ thông tin trong tài liệu nội bộ. Vui lòng liên hệ support team."
    - Set confidence to 0.0
    - Set sources to empty array
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ] 10.6 Implement `run()` function for synthesis worker
    - Extract task, retrieved_chunks, policy_result from state
    - Check for abstention condition
    - Build context and call LLM if chunks available
    - Extract cited sources from final_answer
    - Calculate confidence score
    - Set final_answer, sources, confidence in state
    - Append worker name to workers_called
    - Create worker_io_log entry
    - Handle LLM errors gracefully
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 14.1, 14.4_

  - [ ] 10.7 Create `synthesis_worker_node()` wrapper for graph
    - Call `run()` function
    - Append execution log to history
    - Return updated state
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 11. Create worker contracts YAML
  - [ ] 11.1 Define contracts in `contracts/worker_contracts.yaml`
    - Define retrieval_worker contract with input (task, top_k) and output (retrieved_chunks, retrieved_sources)
    - Define policy_tool_worker contract with input (task, retrieved_chunks, needs_tool) and output (policy_result, mcp_tools_used)
    - Define synthesis_worker contract with input (task, retrieved_chunks, policy_result) and output (final_answer, sources, confidence)
    - Include error_format and constraints for each worker
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 12. Test each worker independently
  - [ ] 12.1 Create test script for retrieval worker
    - Test with query "SLA ticket P1 là bao lâu?"
    - Verify retrieved_chunks is non-empty list
    - Verify each chunk has text, source, score fields
    - Verify scores are between 0.0 and 1.0
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ] 12.2 Create test script for policy tool worker
    - Test with Flash Sale query
    - Verify policy_result contains exceptions_found
    - Verify exception type is "flash_sale_exception"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 12.3 Create test script for synthesis worker
    - Test with chunks and policy_result
    - Verify final_answer contains citations
    - Verify sources array is populated
    - Verify confidence is between 0.0 and 1.0
    - Test abstention case with empty chunks
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 13. Checkpoint - Ensure all workers function correctly
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 3: MCP Integration (60 minutes)

- [ ] 14. Implement MCP Server
  - [ ] 14.1 Create `mcp_server.py` with tool registry
    - Define TOOL_REGISTRY dictionary mapping tool names to functions
    - Define TOOL_SCHEMAS dictionary with MCP-format schemas
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 14.2 Implement search_kb tool
    - Create `tool_search_kb()` function
    - Accept query (string) and top_k (integer) parameters
    - Delegate to retrieval worker's retrieve_dense() function
    - Return dict with chunks, sources, total_found
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 14.3 Implement get_ticket_info tool
    - Create `tool_get_ticket_info()` function
    - Accept ticket_id (string) parameter
    - Define MOCK_TICKETS dictionary with sample data
    - Return ticket object with ticket_id, priority, status, assignee, created_at, sla_deadline, notifications_sent
    - Return error if ticket_id not found
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 14.4 Implement check_access_permission tool
    - Create `tool_check_access_permission()` function
    - Accept access_level (int), requester_role (string), is_emergency (bool) parameters
    - Define ACCESS_RULES configuration
    - Apply access control logic based on level and role
    - Return dict with can_grant, required_approvers, emergency_override, notes
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 14.5 Implement create_ticket tool (optional)
    - Create `tool_create_ticket()` function
    - Accept priority (string), title (string), description (string) parameters
    - Generate mock ticket_id
    - Return dict with ticket_id, url, created_at
    - Log ticket creation (no actual ticket system)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 14.6 Implement dispatch_tool() function
    - Accept tool_name (string) and tool_input (dict) parameters
    - Check if tool exists in TOOL_REGISTRY
    - Return error dict if tool not found
    - Execute tool function with tool_input
    - Catch exceptions and return error dict
    - Return tool output or error
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 14.7 Implement list_tools() function
    - Return list of tool schemas from TOOL_SCHEMAS
    - Include name, description, inputSchema, outputSchema for each tool
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [ ] 15. Integrate MCP into policy worker
  - [ ] 15.1 Update policy worker to call MCP tools
    - Import dispatch_tool from mcp_server
    - Call _call_mcp_tool() for each determined tool
    - Append tool call records to mcp_tools_used
    - Use tool outputs in policy analysis
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [ ] 16. Add MCP logging to trace
  - [ ] 16.1 Ensure mcp_tools_used is populated in state
    - Verify each tool call record has tool, input, output, error, timestamp
    - Verify mcp_tools_used is included in trace output
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [ ] 17. Test MCP tool calls
  - [ ] 17.1 Test search_kb tool directly
    - Call dispatch_tool("search_kb", {"query": "SLA P1", "top_k": 3})
    - Verify chunks array is returned
    - Verify sources array is populated
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 17.2 Test get_ticket_info tool directly
    - Call dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
    - Verify ticket object is returned
    - Verify priority field is "P1"
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 17.3 Test MCP integration in policy worker
    - Run policy worker with needs_tool=True
    - Verify mcp_tools_used array is populated
    - Verify tool call records have correct format
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [ ] 18. Checkpoint - Ensure MCP integration works correctly
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 4: Trace & Documentation (60 minutes)

- [ ] 19. Implement trace generation
  - [ ] 19.1 Create `save_trace()` function
    - Accept state and output_dir parameters
    - Create pruned trace dict with required fields
    - Include run_id, task, supervisor_route, route_reason, workers_called, mcp_tools_used, retrieved_sources, final_answer, sources, confidence, hitl_triggered, latency_ms, timestamp
    - Save to artifacts/traces/{run_id}.json
    - Return filename
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ] 19.2 Update run_graph() to save traces
    - Call save_trace() after graph execution
    - Ensure timestamp is ISO 8601 format
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [ ] 20. Implement eval_trace.py
  - [ ] 20.1 Create main evaluation script
    - Accept input file path (test_questions.json or grading_questions.json)
    - Accept output file path (artifacts/test_run.jsonl or artifacts/grading_run.jsonl)
    - Load questions from JSON file
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ] 20.2 Implement question processing loop
    - Iterate through questions
    - Call run_graph() for each question
    - Create grading trace record with id, question, answer, sources, supervisor_route, route_reason, workers_called, mcp_tools_used, confidence, hitl_triggered, timestamp
    - Handle pipeline errors gracefully (record "PIPELINE_ERROR" in answer field)
    - Write each record as JSONL line
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ] 20.3 Add progress logging
    - Print progress for each question processed
    - Print summary statistics at end (total questions, errors, average latency)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [ ] 21. Process 15 test questions
  - [ ] 21.1 Run eval_trace.py with test_questions.json
    - Execute: `python eval_trace.py --input data/test_questions.json --output artifacts/test_run.jsonl`
    - Verify all 15 questions processed successfully
    - Check artifacts/traces/ directory for individual trace files
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [ ] 22. Generate trace files
  - [ ] 22.1 Verify trace file format
    - Check that each trace has all required fields
    - Verify route_reason is descriptive (not "unknown")
    - Verify latency_ms is recorded
    - Verify timestamp is ISO 8601 format
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [ ] 23. Complete documentation files
  - [ ] 23.1 Fill in docs/system_architecture.md
    - Describe worker roles and responsibilities
    - Include routing flow diagram (ASCII art or Mermaid)
    - Explain supervisor-worker pattern choice
    - Document component interaction flow
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [ ] 23.2 Fill in docs/routing_decisions.md
    - Extract at least 3 routing decisions from actual traces
    - For each decision include: task input, worker chosen, route_reason, result
    - Explain why each routing decision was appropriate
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [ ] 23.3 Fill in docs/single_vs_multi_comparison.md
    - Compare at least 2 metrics: accuracy, latency, debuggability, or abstain rate
    - Provide actual numbers from traces
    - Explain multi-agent advantages (modularity, traceability, extensibility)
    - Explain multi-agent disadvantages (complexity, latency overhead)
    - Include conclusion with evidence from traces
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

- [ ] 24. Write group and individual reports
  - [ ] 24.1 Complete reports/group_report.md
    - Summarize system architecture and design decisions
    - Document sprint deliverables and completion status
    - Include challenges faced and solutions
    - Provide team member contributions overview
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [ ] 24.2 Create individual reports in reports/individual/
    - Each team member creates [name].md file
    - Describe specific module/worker/contract personally implemented
    - Explain 1 technical decision made (routing logic, contract design, etc.)
    - Document 1 bug fixed with before/after evidence
    - Self-assessment: strengths, weaknesses, team dependencies
    - Propose 1 concrete improvement with reasoning from traces
    - Target length: 500-800 words
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

- [ ] 25. Implement human review node
  - [ ] 25.1 Create human_review_node() in graph.py
    - Set hitl_triggered to True
    - Append "human_review" to workers_called
    - Log HITL event with task and route_reason
    - Auto-approve in lab mode (route to retrieval_worker)
    - Update route_reason with approval note
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [ ] 26. Implement multi-hop query support
  - [ ] 26.1 Ensure policy worker can invoke retrieval via MCP
    - If needs_tool=True and no chunks, call search_kb
    - Merge MCP search results with existing chunks
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ] 26.2 Ensure synthesis combines multiple sources
    - Merge retrieved_chunks and policy_result contexts
    - Include citations from all sources
    - Populate sources array with all cited filenames
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [ ] 27. Final checkpoint - Ensure complete system works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks reference specific requirements for traceability
- Implementation uses Python with ChromaDB, OpenAI API, and LangGraph
- Testing strategy focuses on unit tests for workers and integration tests for end-to-end flows
- Trace generation is critical for debugging and evaluation
- Documentation must include actual examples from traces, not hypothetical scenarios
- Individual reports must demonstrate personal contribution with evidence
