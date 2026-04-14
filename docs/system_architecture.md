# System Architecture — Lab Day 09

**Nhóm:** NhomXX-403-Day09
**Ngày:** 14/04/2026
**Version:** 1.2 (Official MCP Library & LLM Supervisor)

---

## 1. Tổng quan kiến trúc

Hệ thống được thiết kế theo mô hình **Multi-Agent Orchestration** sử dụng pattern **Supervisor-Worker**. Điểm nổi bật của phiên bản này là việc tích hợp **Official MCP Protocol** và cơ chế **Hybrid Routing** (LLM + Keyword).

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này:**
- **Hybrid Routing:** Supervisor có khả năng sử dụng LLM (ví dụ: OpenAI) để định tuyến thông minh hoặc fallback về Keyword-based để đảm bảo tính sẵn sàng.
- **Official MCP Integration:** Sử dụng thư viện `mcp[server]` chính thức, hỗ trợ chuẩn SSE (Server-Sent Events) giúp hệ thống mở rộng tốt hơn.
- **Decoupled Data:** Dữ liệu mock được tách ra các file JSON (`mock_tickets.json`, `access_rules.json`) thay vì hardcode.

---

## 2. Sơ đồ Pipeline

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
---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Định tuyến yêu cầu sử dụng LLM (ví dụ: GPT-4o-mini) hoặc Keyword fallback. |
| **Routing logic** | Ưu tiên LLM JSON output; Fallback về Keyword matching cho 3 luồng chính. |
| **HITL condition** | Các mã lỗi `ERR-` lạ mà không có đủ ngữ cảnh tra cứu. |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích chính sách và trích xuất thông tin sử dụng **Rule-based**. |
| **Logic** | Sử dụng biểu thức chính quy (Regex) để trích xuất Ticket ID/Access Level và sử dụng đối sánh từ khóa (Keyword Matching) để xác định ngoại lệ chính sách (Flash Sale, Digital, v.v.). |

### MCP Server (`mcp_server.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Framework** | `mcp.server` + `FastAPI` + `SseServerTransport`. |
| **Tools** | `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket`. |
| **Dữ liệu** | Tải từ `data/mcp/mock_tickets.json` và `data/mcp/access_rules.json`. |

---

## 4. Shared State Schema (AgentState)

| Field | Type | Mô tả |
|-------|------|-------|
| supervisor_route | str | Luồng được chọn (LLM-based hoặc Keyword-based) |
| needs_tool | bool | Cờ đánh dấu Task cần gọi MCP Tool |
| policy_result | dict | Kết quả phân tích chính sách (Rule-based output) |
| mcp_tools_used | list | Log chi tiết các lần gọi Tool qua chuẩn MCP |
| worker_io_logs | list | Nhật ký I/O phục vụ cho `eval_trace.py` |

---

## 5. So sánh Single Agent vs Supervisor-Worker

| Tiêu chí | Single Agent | Supervisor-Worker (v1.2) |
|----------|--------------|-------------------------|
| Tốc độ | Nhanh (1 call) | Chậm hơn (Multi-call) nhưng chính xác hơn |
| Độ tin cậy | Thấp (Dễ ảo giác tool call) | Cao (Worker chuyên biệt cho từng loại Task) |
| Khả năng bảo trì | Khó (Prompt khổng lồ) | Dễ (Mỗi Worker có logic và tool call riêng) |

---

## 6. Điểm cải tiến mới nhất
- **Official Protocol:** Chuyển từ FastAPI REST sang chuẩn MCP SSE Transport.
- **Robustness:** Thêm cơ chế Fallback Routing trong `graph.py` nếu OpenAI API lỗi.
- **Security-First:** Tách biệt logic kiểm tra Policy và gọi Tool vào một Worker chuyên dụng.
