# Requirements Document

## Introduction

This document specifies requirements for a multi-agent orchestration system implementing the Supervisor-Worker pattern to refactor a RAG (Retrieval-Augmented Generation) pipeline for CS and IT Helpdesk internal support. The system routes user queries through specialized workers (retrieval, policy checking, synthesis) coordinated by a supervisor agent, with external capabilities accessed via Model Context Protocol (MCP).

The system must handle single-hop and multi-hop queries across five internal documents (refund policy, SLA, access control, IT helpdesk FAQ, HR leave policy), provide traceable routing decisions, and support abstention when information is unavailable.

## Glossary

- **System**: The multi-agent orchestration system
- **Supervisor**: The orchestrator agent that analyzes tasks and routes to appropriate workers
- **Retrieval_Worker**: Worker agent responsible for retrieving evidence chunks from the knowledge base
- **Policy_Tool_Worker**: Worker agent responsible for policy checking and external tool invocation
- **Synthesis_Worker**: Worker agent responsible for generating final answers with citations
- **AgentState**: Shared state object passed between all agents containing task, routing decisions, worker outputs, and trace information
- **MCP_Server**: Model Context Protocol server providing external capabilities via tools
- **Trace**: Complete execution log including routing decisions, worker calls, and outputs
- **HITL**: Human-in-the-loop review triggered for high-risk scenarios
- **Worker_Contract**: Input/output specification defining the interface for each worker
- **Knowledge_Base**: Collection of five internal documents stored in ChromaDB
- **Chunk**: Text segment retrieved from Knowledge_Base with source and similarity score
- **Route_Reason**: Explanation for why Supervisor chose a specific worker
- **Abstain**: System behavior when no relevant information exists in Knowledge_Base

## Requirements

### Requirement 1: Supervisor Routing

**User Story:** As a system operator, I want the Supervisor to analyze incoming tasks and route them to appropriate workers, so that queries are handled by the most suitable specialized agent.

#### Acceptance Criteria

1. WHEN a task is received, THE Supervisor SHALL analyze the task content and determine the appropriate worker route
2. WHEN a task contains policy keywords ("hoàn tiền", "refund", "flash sale", "license", "cấp quyền", "access level"), THE Supervisor SHALL route to Policy_Tool_Worker
3. WHEN a task contains SLA keywords ("P1", "SLA", "ticket", "escalation", "sự cố"), THE Supervisor SHALL route to Retrieval_Worker
4. WHEN a task contains unknown error codes AND insufficient context, THE Supervisor SHALL route to human_review
5. THE Supervisor SHALL record route_reason in AgentState with specific explanation for the routing decision
6. THE Supervisor SHALL set risk_high flag to true WHEN task contains emergency keywords ("emergency", "khẩn cấp", "2am")
7. THE Supervisor SHALL set needs_tool flag to true WHEN routing to Policy_Tool_Worker
8. THE Supervisor SHALL NOT generate domain knowledge answers directly

### Requirement 2: Retrieval Worker Operation

**User Story:** As a developer, I want the Retrieval Worker to find relevant evidence chunks from the knowledge base, so that answers are grounded in actual documentation.

#### Acceptance Criteria

1. WHEN invoked with a task, THE Retrieval_Worker SHALL embed the query and search the Knowledge_Base
2. THE Retrieval_Worker SHALL return top_k chunks with text, source filename, similarity score, and metadata
3. THE Retrieval_Worker SHALL return similarity scores as float values between 0.0 and 1.0
4. WHEN no relevant chunks are found, THE Retrieval_Worker SHALL return an empty retrieved_chunks array
5. THE Retrieval_Worker SHALL extract unique source filenames into retrieved_sources array
6. THE Retrieval_Worker SHALL append worker_io_log entry to AgentState with input and output details
7. THE Retrieval_Worker SHALL operate statelessly without reading or writing state beyond specified contract fields

### Requirement 3: Policy Tool Worker Operation

**User Story:** As a compliance officer, I want the Policy Tool Worker to check policies and detect exceptions, so that policy-related queries receive accurate rule-based answers.

#### Acceptance Criteria

1. WHEN invoked with a task, THE Policy_Tool_Worker SHALL analyze retrieved_chunks for applicable policies
2. THE Policy_Tool_Worker SHALL detect exception cases including "flash_sale", "digital_product", and "activated_product"
3. WHEN needs_tool flag is true, THE Policy_Tool_Worker SHALL invoke MCP_Server tools
4. THE Policy_Tool_Worker SHALL record each MCP tool call in mcp_tools_used array with tool name, input, output, and timestamp
5. THE Policy_Tool_Worker SHALL return policy_result object containing policy_applies boolean, policy_name, exceptions_found array, and source array
6. WHEN a Flash Sale exception is detected, THE Policy_Tool_Worker SHALL include exception type, rule text, and source in exceptions_found
7. THE Policy_Tool_Worker SHALL NOT generate policy rules not present in retrieved documentation

### Requirement 4: Synthesis Worker Operation

**User Story:** As an end user, I want the Synthesis Worker to generate clear answers with citations, so that I can verify the information source.

#### Acceptance Criteria

1. WHEN invoked with retrieved_chunks and policy_result, THE Synthesis_Worker SHALL generate a final_answer with inline citations
2. THE Synthesis_Worker SHALL include citation markers (e.g., "[1]" or "[source_name]") in final_answer WHEN chunks are available
3. WHEN retrieved_chunks is empty, THE Synthesis_Worker SHALL abstain and state that information is not available in documentation
4. THE Synthesis_Worker SHALL calculate confidence score as float between 0.0 and 1.0
5. WHEN confidence score is below 0.4, THE Synthesis_Worker SHALL recommend setting hitl_triggered to true
6. THE Synthesis_Worker SHALL populate sources array with all source filenames cited in final_answer
7. THE Synthesis_Worker SHALL NOT use knowledge outside the provided context from retrieved_chunks and policy_result

### Requirement 5: MCP Server Tools

**User Story:** As a Policy Tool Worker, I want to access external capabilities through MCP tools, so that I can retrieve additional information beyond static retrieval.

#### Acceptance Criteria

1. THE MCP_Server SHALL implement search_kb tool accepting query string and top_k integer parameters
2. THE MCP_Server SHALL implement get_ticket_info tool accepting ticket_id string parameter
3. WHEN search_kb is invoked, THE MCP_Server SHALL return chunks array, sources array, and total_found integer
4. WHEN get_ticket_info is invoked, THE MCP_Server SHALL return ticket object with ticket_id, priority, status, assignee, created_at, sla_deadline, and notifications_sent fields
5. WHEN an unknown tool is requested, THE MCP_Server SHALL return error object with code and reason
6. THE MCP_Server SHALL NOT raise exceptions outside the dispatch_tool function
7. THE MCP_Server SHALL provide list_tools function returning tool schemas in MCP format

### Requirement 6: Trace Generation

**User Story:** As a system debugger, I want complete execution traces for each query, so that I can analyze routing decisions and worker behavior.

#### Acceptance Criteria

1. THE System SHALL generate a trace record for each query execution
2. THE System SHALL include run_id, task, supervisor_route, route_reason, workers_called, mcp_tools_used, retrieved_sources, final_answer, confidence, hitl_triggered, latency_ms, and timestamp in each trace record
3. THE System SHALL record latency_ms as integer milliseconds from query start to completion
4. THE System SHALL append each worker name to workers_called array WHEN that worker is invoked
5. THE System SHALL save trace records to artifacts/traces/ directory in JSON format
6. WHEN running grading questions, THE System SHALL save trace records to artifacts/grading_run.jsonl in JSONL format (one JSON object per line)
7. THE System SHALL include route_reason with specific explanation, not "unknown" or empty string

### Requirement 7: Worker Contracts Compliance

**User Story:** As a system architect, I want workers to adhere to defined contracts, so that components are interchangeable and testable independently.

#### Acceptance Criteria

1. THE System SHALL define worker contracts in contracts/worker_contracts.yaml file
2. WHEN a worker is invoked, THE System SHALL provide input fields matching the worker contract specification
3. WHEN a worker completes, THE System SHALL validate output fields match the worker contract specification
4. THE Retrieval_Worker SHALL accept task string and optional top_k integer as input
5. THE Policy_Tool_Worker SHALL accept task string, optional retrieved_chunks array, and optional needs_tool boolean as input
6. THE Synthesis_Worker SHALL accept task string, optional retrieved_chunks array, and optional policy_result object as input
7. THE System SHALL enable independent testing of each worker without requiring full graph execution

### Requirement 8: Human-in-the-Loop Handling

**User Story:** As a quality assurance manager, I want high-risk queries to trigger human review, so that critical decisions receive human oversight.

#### Acceptance Criteria

1. WHEN risk_high flag is true AND task contains unknown error codes, THE Supervisor SHALL route to human_review
2. WHEN human_review is triggered, THE System SHALL set hitl_triggered flag to true in AgentState
3. WHEN human_review is triggered, THE System SHALL append "human_review" to workers_called array
4. WHEN human_review is triggered, THE System SHALL log HITL event with task and route_reason to console
5. WHEN confidence score is below 0.4, THE Synthesis_Worker SHALL set hitl_triggered to true
6. THE System SHALL record hitl_triggered boolean in trace output
7. WHERE human approval is granted, THE System SHALL continue execution with Retrieval_Worker

### Requirement 9: Multi-Hop Query Handling

**User Story:** As an end user, I want the system to answer complex queries requiring information from multiple documents, so that I receive complete answers to multi-faceted questions.

#### Acceptance Criteria

1. WHEN a task requires information from multiple documents, THE System SHALL invoke multiple workers as needed
2. WHEN Policy_Tool_Worker requires retrieval context, THE System SHALL invoke Retrieval_Worker before Policy_Tool_Worker
3. WHEN a multi-hop query is processed, THE System SHALL record all invoked workers in workers_called array
4. THE Synthesis_Worker SHALL combine information from retrieved_chunks and policy_result for multi-hop queries
5. WHEN cross-document reasoning is required, THE System SHALL retrieve chunks from all relevant source documents
6. THE System SHALL include all relevant source filenames in retrieved_sources array for multi-hop queries
7. THE Synthesis_Worker SHALL provide citations from all sources used in multi-hop answer generation

### Requirement 10: Abstention Behavior

**User Story:** As a system user, I want the system to clearly state when information is unavailable, so that I do not receive fabricated answers.

#### Acceptance Criteria

1. WHEN retrieved_chunks is empty, THE Synthesis_Worker SHALL generate final_answer stating information is not available in documentation
2. WHEN no relevant information exists, THE Synthesis_Worker SHALL NOT generate answers based on external knowledge
3. WHEN abstaining, THE Synthesis_Worker SHALL set confidence score to 0.0
4. WHEN abstaining, THE Synthesis_Worker SHALL set sources array to empty
5. THE System SHALL record abstention cases in trace with empty retrieved_sources array
6. WHEN a query contains unknown error codes not in Knowledge_Base, THE System SHALL abstain or route to human_review
7. THE Synthesis_Worker SHALL include recommendation to contact support team in abstention messages

### Requirement 11: Grading Questions Execution

**User Story:** As a lab instructor, I want the system to process grading questions and generate compliant trace logs, so that student submissions can be evaluated consistently.

#### Acceptance Criteria

1. WHEN grading_questions.json is provided, THE System SHALL process all questions in sequence
2. THE System SHALL generate one trace record per grading question
3. THE System SHALL save grading traces to artifacts/grading_run.jsonl in JSONL format
4. THE System SHALL include question id, question text, answer, sources, supervisor_route, route_reason, workers_called, mcp_tools_used, confidence, hitl_triggered, and timestamp in each grading trace record
5. WHEN a query execution fails, THE System SHALL record "PIPELINE_ERROR" with error description in answer field
6. THE System SHALL complete grading run within 60 minutes of grading_questions.json publication
7. THE System SHALL NOT modify code or trace files after 18:00 deadline

### Requirement 12: Parser and Pretty Printer (Round-Trip Property)

**User Story:** As a developer, I want to parse worker contracts from YAML and serialize them back, so that contract definitions are validated and maintainable.

#### Acceptance Criteria

1. THE System SHALL parse contracts/worker_contracts.yaml into structured contract objects
2. WHEN a valid YAML contract file is provided, THE Contract_Parser SHALL parse it into Contract objects
3. WHEN an invalid YAML contract file is provided, THE Contract_Parser SHALL return a descriptive error
4. THE Contract_Pretty_Printer SHALL format Contract objects back into valid YAML files
5. FOR ALL valid Contract objects, parsing then printing then parsing SHALL produce an equivalent object (round-trip property)
6. THE Contract_Parser SHALL validate required fields (name, description, input, output) are present
7. THE Contract_Pretty_Printer SHALL preserve comments and formatting structure from original YAML

### Requirement 13: Performance and Latency Tracking

**User Story:** As a performance engineer, I want latency metrics for each query execution, so that I can identify bottlenecks and optimize the system.

#### Acceptance Criteria

1. THE System SHALL record start timestamp WHEN query execution begins
2. THE System SHALL record end timestamp WHEN query execution completes
3. THE System SHALL calculate latency_ms as integer milliseconds between start and end timestamps
4. THE System SHALL include latency_ms in trace output for each query
5. THE System SHALL record individual worker execution times in worker_io_logs
6. WHEN latency exceeds 5000ms, THE System SHALL log a performance warning
7. THE System SHALL aggregate latency statistics across all grading questions in evaluation report

### Requirement 14: Error Handling and Recovery

**User Story:** As a system operator, I want graceful error handling when workers fail, so that the system provides useful feedback instead of crashing.

#### Acceptance Criteria

1. WHEN a worker raises an exception, THE System SHALL catch the exception and record error details in worker_io_logs
2. WHEN Retrieval_Worker fails, THE System SHALL set retrieved_chunks to empty array and continue execution
3. WHEN Policy_Tool_Worker fails, THE System SHALL set policy_result to empty object and continue execution
4. WHEN Synthesis_Worker fails, THE System SHALL set final_answer to error message and confidence to 0.0
5. WHEN MCP tool invocation fails, THE Policy_Tool_Worker SHALL record error object in mcp_tools_used entry
6. THE System SHALL include error code and reason in worker_io_logs error field
7. THE System SHALL NOT terminate execution due to single worker failure

### Requirement 15: Documentation Generation

**User Story:** As a lab student, I want to generate system architecture and routing decision documentation, so that I can explain design choices and trace analysis.

#### Acceptance Criteria

1. THE System SHALL provide template for docs/system_architecture.md with sections for worker roles, routing flow diagram, and pattern justification
2. THE System SHALL provide template for docs/routing_decisions.md with sections for routing examples from actual traces
3. THE System SHALL provide template for docs/single_vs_multi_comparison.md with sections for metrics comparison
4. WHEN evaluation completes, THE System SHALL populate routing_decisions.md with at least 3 actual routing decisions from traces
5. WHEN evaluation completes, THE System SHALL populate single_vs_multi_comparison.md with at least 2 metrics (accuracy, latency, debuggability, or abstain rate)
6. THE System SHALL include task input, worker chosen, route_reason, and result for each routing decision example
7. THE System SHALL provide conclusion comparing multi-agent advantages and disadvantages versus single-agent baseline
