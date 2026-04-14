# Định hướng & Hướng dẫn Thực thi Code - Lab Day 09

Tài liệu này đóng vai trò như cẩm nang cho 3 thành viên team trong toàn bộ quá trình thực hiện Lab 09 (Multi-Agent Orchestration). Hãy tuân thủ để tránh những lỗi phổ biến khi làm việc với Multi-Agent.

## 1. Định hướng Thiết Kế (Design Principles)

### 1.1 "Supervisor Quyết định, Worker Thực thi"
- **Không nhồi nhét logic vào một file:** Tránh việc Supervisor vừa định tuyến vừa xử lý dữ liệu.
- **Supervisor (Graph):** Chỉ nhận `task`, đọc dữ liệu `history`, đánh giá rủi ro và **chuyển hướng (route)** tới Worker phù hợp (kèm theo log `route_reason`).
- **Worker (Agent):** Chỉ làm một nhiệm vụ chuyên biệt (Retrieval, Policy Check, Synthesis) và báo cáo lại kết quả thông qua biến chia sẻ `AgentState`.

### 1.2 "Hợp đồng I/O là Sinh Mệnh"
- Trong mô hình Multi-Agent, lỗi lớn nhất thường là Worker A truyền kết quả cho Worker B nhưng Worker B không hiểu format.
- Mọi người phải bám sát định dạng của biến `AgentState` được quy định từ Sprint 1. Bất kỳ thay đổi nào cũng phải thông báo cho cả team để đồng bộ `worker_contracts.yaml`.

### 1.3 Lựa chọn LLM Provider Theo Vai Trò (Agent-Specific LLMs)
Trong hệ thống Multi-Agent, không nên chỉ dùng một model cố định cho toàn bộ luồng. Việc chia nhỏ Worker cho phép team chọn Provider tối ưu về giá và tốc độ (cấu hình trong `.env`):
- **Supervisor (Não bộ định tuyến):** Cần model suy luận mạnh, ít ảo giác để phân loại Task. Khuyên dùng **OpenAI** (như `gpt-4o-mini` hoặc `gpt-4o`).
- **Synthesis Worker (Tổng hợp nội dung):** Đòi hỏi tốc độ trả lời cực nhanh để không làm tăng độ trễ tổng thể (latency) của pipeline. Rất phù hợp sử dụng **Groq** (Sử dụng OpenAI Client với `base_url` của Groq và model như `openai/gpt-oss-120b`).
- **Policy/Retrieval Worker:** Dùng **Google (Gemini)** cho vector embedding (`gemini-embedding-2-preview`) hoặc các model chuyên dụng giá rẻ.
- **Quy tắc Bắt Buộc:** **KHÔNG ĐƯỢC HARDCODE** model name hay API key vào trong code của Worker. Tất cả cấu hình này phải lấy từ biến môi trường (`os.getenv("SUPERVISOR_MODEL")`, `os.getenv("GROQ_API_KEY")`, v.v.).

---

## 2. Quy ước Coding (Coding Standards)

- **Modular:** Viết các Worker dưới dạng hàm `run(state)` dễ dàng gọi độc lập.
- **Logging là Bắt Buộc:** Mỗi hành động, định tuyến, hay API call đều cần được log lại (đặc biệt vào `worker_io_log` của State) để phục vụ cho `eval_trace.py` ở Sprint 4.
- **No Hardcode:**
  - Không nhúng thẳng API Key trong code (sử dụng `.env`).
  - Lấy tài liệu và cấu hình từ các file bên ngoài (JSON, YAML, TXT), không hardcode list dữ liệu lớn.
- **Xử lý Ngoại lệ (Graceful Failure):**
  - Worker Retrieval không tìm thấy tài liệu: Trả về mảng rỗng `[]` thay vì văng Exception.
  - Worker Synthesis bị lỗi API (rate limit): Có try-catch và fallback message thay vì sập toàn bộ luồng.

---

## 5. Hướng dẫn Triển khai MCP Localhost Server (SSE/HTTP)

Để chạy MCP Server như một service độc lập trên Localhost, team thực hiện theo mô hình **SSE (Server-Sent Events)**:

### 5.1 Cấu trúc file `mcp_server.py`
Sử dụng thư viện `mcp[server]` và một web framework nhẹ (như `FastAPI` hoặc `starlette`) để host:
1. **Khởi tạo Server:** `server = Server("my-mcp-server")`
2. **Định nghĩa Tool:** Sử dụng decorator `@server.list_tools()` và `@server.call_tool()`.
3. **Expose qua HTTP:** Sử dụng `SSEDataPlain` để chuyển đổi protocol MCP sang HTTP stream.

### 5.2 Cách kết nối từ `policy_tool.py` (Client)
1. **Khởi tạo Client:** Sử dụng `SseClientTransport` trỏ đến `http://localhost:8000/sse`.
2. **Session:** Duy trì một `ClientSession` để gọi các tool đã được server expose.

### 5.3 Lợi ích khi dùng Localhost Server
- **Độc lập:** Có thể restart server mà không cần chạy lại toàn bộ Graph.
- **Traceable:** Có thể xem log trực tiếp từ terminal chạy server để debug lỗi logic bên trong tool.
- **Mở rộng:** Dễ dàng cho phép các Agent khác (không thuộc Graph này) cùng sử dụng bộ tool này.

---

## 6. Quy trình Kiểm thử (Testing Strategy)

- **Step 1: Test Unit độc lập (Bottom-Up):**
  - Trước khi ghép file `retrieval.py` vào `graph.py`, hãy gọi `run({"task": "test", "history": []})` và in kết quả ra màn hình (Mock test).
- **Step 2: Test Luồng Chính (Integration):**
  - Bắt đầu với các câu lệnh định tuyến trực tiếp (Ví dụ: Câu hỏi thuần tra cứu -> Supervisor -> Retrieval -> Synthesis -> End). Đảm bảo state được cập nhật đủ.
- **Step 3: Test Exception Routing:**
  - Nhập một câu hỏi "khó" (VD: "P1 escalation") và kiểm tra xem luồng có chạy đúng sang Policy Worker / Human Review không.

---

## 4. Quản lý Phiên bản (Git Workflow)

*Do nhóm có 3 người và thực hiện trong thời gian ngắn (4 tiếng), khuyến nghị tuân thủ Git ngắn gọn:*
- **Tạo nhánh cho từng phần:**
  - `git checkout -b feature/graph` (Thành viên A)
  - `git checkout -b feature/workers` (Thành viên B)
  - `git checkout -b feature/mcp` (Thành viên C)
- **Cập nhật thường xuyên (Merge):**
  - Khi hoàn thiện 1 Worker và test độc lập xong, Pull/Merge vào nhánh `main` và thông báo nhóm cập nhật.
- **Bảo vệ File Graph:** Nhánh `main` chứa `graph.py` sẽ là điểm ghép nối, nên cẩn thận khi resolve conflict ở file này.
- **Lưu ý:** Không Commit file `.env` và thư mục `chroma_db/`. Cập nhật `.gitignore` nếu cần.