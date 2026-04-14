# Kế hoạch Thực hiện Lab Day 09 - Team 3 người

Bản kế hoạch chi tiết cho đội hình 3 thành viên thực hiện dự án Multi-Agent Orchestration trong 4 giờ (4 Sprints x 60 phút).

---

## 1. Phân chia vai trò (Roles & Responsibilities)

| Thành viên | Vai trò chính | Trách nhiệm chính |
| :--- | :--- | :--- |
| **Thành viên A** | **Supervisor & Evaluator** | Quản lý luồng chạy chính (`graph.py`), điều phối logic định tuyến, viết code đánh giá (`eval_trace.py`) và báo cáo tổng hợp. |
| **Thành viên B** | **Worker Specialist** | Xây dựng các Worker cốt lõi (`retrieval.py`, `synthesis.py`), định nghĩa hợp đồng dữ liệu (`worker_contracts.yaml`) và so sánh metrics. |
| **Thành viên C** | **Integration & MCP** | Xử lý logic nghiệp vụ phức tạp (`policy_tool.py`), xây dựng hệ thống công cụ ngoài (`mcp_server.py`) và viết kiến trúc hệ thống. |

---

## 2. Lộ trình thực hiện chi tiết (Timeline)

### ⏰ Sprint 1: Khởi tạo & Định hình Cấu trúc (0 - 60 phút)
*   **Thành viên A (`graph.py`):**
    *   Định nghĩa `AgentState` (task, history, worker_log, risk_high...).
    *   Xây dựng khung `supervisor_node()` và hàm `route_decision()`.
    *   Kết nối graph với các node giả (dummy) để test luồng chuyển đổi trạng thái.
*   **Thành viên B (`retrieval.py` & `synthesis.py`):**
    *   Implement `Retrieval Worker`: Kết nối ChromaDB, lấy chunks dựa trên query.
    *   Implement `Synthesis Worker`: Viết Prompt grounded (chỉ dùng context), trả về answer + sources + confidence.
    *   Test độc lập từng worker bằng mock state.
*   **Thành viên C (`mcp_server.py`):**
    *   Thiết lập Mock MCP Server.
    *   Viết 2 công cụ: `search_kb` (truy vấn ChromaDB) và `get_ticket_info` (dữ liệu mock).
    *   Test I/O của server độc lập.

### ⏰ Sprint 2: Lắp ráp Workers & Xử lý Policy (60 - 120 phút)
*   **Thành viên A (Integration):**
    *   Hỗ trợ Thành viên B tích hợp `retrieval.py` và `synthesis.py` vào `graph.py`.
    *   Chạy thử graph với các câu hỏi truy vấn thông tin đơn giản.
*   **Thành viên C (`policy_tool.py`):**
    *   Viết logic kiểm tra chính sách (Refund, SLA, Access).
    *   Thay đổi cơ chế: Gọi qua MCP Client (vừa tạo ở Sprint 1) thay vì gọi trực tiếp DB.
    *   Xử lý logic ngoại lệ (Flash Sale, Digital Products).
*   **Thành viên B (Contracts & Refinement):**
    *   Hoàn thiện `contracts/worker_contracts.yaml`.
    *   Tinh chỉnh Prompt cho Synthesis để đảm bảo định dạng Citation `[1]`, `[2]`.

### ⏰ Sprint 3: Tích hợp Toàn diện & Fix Bug (120 - 180 phút)
*   **Cả Team (Làm việc chung):**
    *   Gắn node `policy_tool` vào đồ thị chính.
    *   Kiểm tra tính nhất quán của dữ liệu truyền qua `AgentState`.
    *   Chạy test các kịch bản khó (Multi-hop: vừa hỏi SLA vừa hỏi Ticket cụ thể).
    *   Đảm bảo mọi bước đi đều được ghi log vào `route_reason` và `worker_io_log`.

### ⏰ Sprint 4: Trace, Đánh giá & Báo cáo (180 - 240 phút)
*   **Thành viên A (`eval_trace.py` & Report):**
    *   Chạy 15 câu test questions để sinh file `.jsonl` trong `artifacts/traces/`.
    *   Viết hàm `analyze_trace()` tính toán các chỉ số (latency, confidence avg).
    *   Viết khung báo cáo nhóm `reports/group_report.md`.
*   **Thành viên B (Comparison & Individual Report):**
    *   So sánh hiệu quả giữa Single-Agent (Day 08) và Multi-Agent (Day 09) tại `docs/single_vs_multi_comparison.md`.
    *   Hoàn thành báo cáo cá nhân.
*   **Thành viên C (System Docs & Individual Report):**
    *   Viết `docs/system_architecture.md` (mô tả sơ đồ graph và MCP).
    *   Ghi chú 3 quyết định định tuyến thực tế vào `docs/routing_decisions.md`.
    *   Hoàn thành báo cáo cá nhân.

---

## 3. Quy tắc Phối hợp (Collaboration Tips)

1.  **Giao tiếp qua State:** Các thành viên thống nhất tên các trường dữ liệu trong `AgentState` ngay từ đầu để không bị lỗi khi ghép code.
2.  **Test-Driven:** Luôn viết một đoạn `if __name__ == "__main__":` ở cuối mỗi file worker để tự test trước khi gửi cho Thành viên A ghép vào Graph.
3.  **Ưu tiên Trace:** File Trace là bằng chứng chấm điểm quan trọng nhất. Nếu hết thời gian, ưu tiên chạy ra được file Trace đúng định dạng trước khi chau chuốt nội dung báo cáo.
