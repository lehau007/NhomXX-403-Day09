# Danh sách công việc (Tasks) - Lab Day 09

Dưới đây là tổng hợp các task cần thực hiện dựa trên yêu cầu của `README.md`:

## Sprint 1: Refactor Graph (`graph.py`)
- [ ] Implement `AgentState` để làm shared state cho toàn graph.
- [ ] Implement `supervisor_node()` để đọc task và quyết định route.
- [ ] Implement `route_decision()` để xây dựng logic định tuyến dựa vào task type và risk flag.
- [ ] Kết nối graph theo luồng: `supervisor → route → [retrieval | policy_tool | human_review] → synthesis → END`.
- [ ] Chạy `graph.invoke()` với 2 test queries khác nhau để kiểm tra kết quả.
- [ ] Đảm bảo mỗi bước routing được log với `route_reason`.

## Sprint 2: Build Workers (`workers/`)
- [ ] **Retrieval Worker** (`workers/retrieval.py`):
  - [ ] Implement `run(state)` để nhận query từ state, gọi ChromaDB và trả về chunks.
  - [ ] Ghi `retrieved_chunks` và `worker_io_log` vào state.
- [ ] **Policy Tool Worker** (`workers/policy_tool.py`):
  - [ ] Implement `run(state)` để kiểm tra policy dựa trên retrieved chunks.
  - [ ] Phân tích và xử lý exception/edge case (ví dụ: Flash Sale, Digital Product).
  - [ ] Ghi `policy_result` và `worker_io_log` vào state.
- [ ] **Synthesis Worker** (`workers/synthesis.py`):
  - [ ] Implement `run(state)` để tổng hợp answer từ chunks và `policy_result`.
  - [ ] Gọi LLM với grounded prompt (chỉ dùng evidence từ state).
  - [ ] Output trả về bao gồm `answer`, `sources`, và `confidence`.
- [ ] Kiểm tra từng worker hoạt động độc lập (không cần graph) và đảm bảo I/O khớp với `contracts/worker_contracts.yaml`.

## Sprint 3: Thêm MCP (`mcp_server.py`)
- [ ] Implement mock MCP Server với ít nhất 2 tools:
  - [ ] `search_kb(query, top_k)`: Tìm kiếm Knowledge Base sử dụng ChromaDB.
  - [ ] `get_ticket_info(ticket_id)`: Tra cứu thông tin ticket với mock data.
- [ ] Cập nhật `workers/policy_tool.py`: Gọi MCP client để lấy kết quả thay vì truy cập trực tiếp ChromaDB.
- [ ] Ghi lại thông tin `mcp_tool_called` và `mcp_result` vào trace.

## Sprint 4: Trace & Docs & Report
- [ ] Chạy pipeline với 15 test questions và lưu trace vào thư mục `artifacts/traces/`.
- [ ] Implement hàm `analyze_trace()` trong `eval_trace.py` để đọc trace và tính metrics.
- [ ] Implement hàm `compare_single_vs_multi()` trong `eval_trace.py` để so sánh với baseline Day 08.
- [ ] Điền thông tin vào các template tài liệu:
  - [ ] `docs/system_architecture.md`
  - [ ] `docs/routing_decisions.md` (ít nhất 3 quyết định routing thực tế)
  - [ ] `docs/single_vs_multi_comparison.md` (ít nhất 2 metrics)
- [ ] Hoàn thành báo cáo nhóm tại `reports/group_report.md`.
- [ ] Hoàn thành báo cáo cá nhân tại `reports/individual/[tên].md`.