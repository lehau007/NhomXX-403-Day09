# System Architecture — Lab Day 09

**Nhóm:** Team 3 (Hậu, Tú, Hào)
**Ngày:** 14/04/2026
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

Hệ thống được xây dựng theo mô hình **Supervisor-Worker** sử dụng LangGraph (hoặc mô phỏng Graph logic). Supervisor đóng vai trò là "não bộ" điều phối, phân tích câu hỏi của người dùng để quyết định chuyển tiếp (route) đến các Worker chuyên biệt.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**
- **Tính minh bạch (Observability):** Có thể theo dõi rõ ràng lý do tại sao một quyết định điều phối được đưa ra thông qua `route_reason`.
- **Tính module (Modularity):** Mỗi Worker (Retrieval, Policy, Synthesis) được phát triển và kiểm thử độc lập, dễ dàng bảo trì và nâng cấp.
- **Khả năng mở rộng (Extensibility):** Dễ dàng thêm các năng lực mới (như các MCP tools) mà không làm phức tạp hóa Prompt chính của Agent.
- **Kiểm soát rủi ro:** Có tích hợp Human-in-the-loop (HITL) cho các trường hợp câu hỏi mơ hồ hoặc có độ rủi ro cao.

---

## 2. Sơ đồ Pipeline

Sơ đồ luồng xử lý từ khi nhận yêu cầu đến khi trả về kết quả:

```text
       [ User Request ]
              │
              ▼
      ┌──────────────┐
      │  Supervisor  │ (Phân loại Task, Đánh giá Rủi ro, Quyết định Route)
      └──────┬───────┘
             │
      ┌──────┴─────────────────────────────────┐
      │             [ Route Decision ]         │
      ▼                      ▼                 ▼
[ Retrieval Worker ]  [ Policy Worker ]  [ Human Review ]
 (Tra cứu Knowledge)   (Kiểm tra Policy)  (HITL - Chờ duyệt)
      │             (Gọi MCP Tool Call)        │
      └──────────────┬─────────────────────────┘
                     │
                     ▼
           [ Synthesis Worker ] (Tổng hợp Answer + Trích dẫn Source)
                     │
                     ▼
              [ Final Output ]
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích `task`, xác định loại yêu cầu và đánh giá mức độ rủi ro để điều phối đến Worker phù hợp. |
| **Input** | `AgentState` chứa `task` và `history`. |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`. |
| **Routing logic** | Sử dụng keyword matching (hoặc LLM router) để phân loại vào: `retrieval_worker`, `policy_tool_worker`, hoặc `human_review`. |
| **HITL condition** | Trigger khi phát hiện mã lỗi mơ hồ (ERR-*) hoặc các từ khóa rủi ro cao mà thiếu ngữ cảnh. |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Truy vấn dữ liệu từ vector database (ChromaDB) để tìm các đoạn văn bản (chunks) liên quan nhất. |
| **Embedding model** | `gemini-embedding-2-preview` (Google) |
| **Top-k** | 3 (mặc định, có thể cấu hình qua `.env`) |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Kiểm tra các quy tắc chính sách đặc thù (Refund, Access Control) và gọi các công cụ ngoài qua MCP. |
| **MCP tools gọi** | `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket`. |
| **Exception cases xử lý** | Flash Sale, Digital Products, Subscription, Activated products. |

### MCP Server (`mcp_server.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `llama3-8b-8192` (Groq) hoặc `gemini-1.5-flash`. |
| **Temperature** | 0.1 (để đảm bảo tính ổn định và chính xác). |
| **Grounding strategy** | Sử dụng System Prompt nghiêm ngặt: "Chỉ trả lời dựa trên context được cung cấp", kèm inline citations. |
| **Abstain condition** | Trả về "Không đủ thông tin" nếu context rỗng hoặc không chứa thông tin trả lời. |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query, top_k | chunks, sources, total_found |
| get_ticket_info | ticket_id | Chi tiết ticket (priority, status, created_at, v.v.) |
| check_access_permission | access_level, requester_role | can_grant, required_approvers, notes |
| create_ticket | priority, title, description | Thông tin ticket vừa tạo thành công |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào của người dùng | Supervisor đọc |
| supervisor_route | str | Định danh Worker được chọn để xử lý | Supervisor ghi, Router đọc |
| route_reason | str | Giải thích lý do tại sao chọn route đó | Supervisor ghi |
| retrieved_chunks | list | Các đoạn văn bản tìm được từ KB | Retrieval/Policy ghi, Synthesis đọc |
| policy_result | dict | Kết quả phân tích chính sách và ngoại lệ | Policy ghi, Synthesis đọc |
| mcp_tools_used | list | Lịch sử các tool đã gọi qua MCP | Policy ghi |
| final_answer | str | Câu trả lời cuối cùng sau khi tổng hợp | Synthesis ghi |
| confidence | float | Độ tin cậy của câu trả lời (0.0 - 1.0) | Synthesis ghi |
| workers_called | list | Danh sách các worker đã tham gia xử lý | Tất cả ghi |
| worker_io_logs | list | Chi tiết Input/Output của từng bước | Tất cả ghi |

---

## 5. So sánh Single Agent vs Supervisor-Worker

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — phải đọc log prompt dài, không rõ bước nào fail. | Dễ hơn — trace chỉ rõ supervisor route đúng/sai, worker trả về gì. |
| Thêm capability mới | Phải sửa toàn bộ prompt, dễ gây side effect (hallucination). | Thêm worker hoặc MCP tool riêng biệt, không ảnh hưởng logic cũ. |
| Routing visibility | Không có — Agent tự quyết định ngầm. | Có `route_reason` và `supervisor_route` hiển thị trong trace. |
| Độ trễ (Latency) | Thấp hơn (thường chỉ 1 LLM call). | Cao hơn (nhiều LLM calls và bước trung gian). |

**Nhóm điền thêm quan sát từ thực tế lab:**
- Multi-agent giúp xử lý các câu hỏi phức tạp (multi-hop) tốt hơn bằng cách chia nhỏ vấn đề.
- Việc sử dụng các model khác nhau cho từng task (ví dụ: GPT-4 cho Routing, Groq cho Synthesis) giúp tối ưu hóa cả chi phí và hiệu năng.

---

## 6. Giới hạn và điểm cần cải tiến

1. **Độ trễ:** Việc gọi tuần tự qua nhiều node làm tăng thời gian phản hồi tổng thể. Có thể cải tiến bằng cách chạy song song các Worker nếu logic cho phép.
2. **Sự phụ thuộc vào Supervisor:** Nếu Supervisor phân loại sai ngay từ đầu, toàn bộ pipeline sẽ cho kết quả sai. Cần Prompt engineering mạnh hơn cho Supervisor.
3. **Quản lý State:** Khi số lượng Worker tăng lên, AgentState có thể trở nên quá lớn và khó quản lý. Cần cơ chế dọn dẹp hoặc tóm tắt state.
