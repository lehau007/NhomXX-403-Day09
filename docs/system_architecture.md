# System Architecture — Lab Day 09

**Nhóm:** NhomXX-403-Day09
**Ngày:** 14/04/2026
**Version:** 1.2 (Official MCP Library & LLM Supervisor)

---

## 1. Tổng quan kiến trúc

Hệ thống được thiết kế theo mô hình **Multi-Agent Orchestration** sử dụng pattern **Supervisor-Worker**. Kiến trúc này tập trung vào việc tách biệt trách nhiệm (Separation of Concerns) và tối ưu hóa việc chọn Model cho từng tác vụ.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này:**
- **Hybrid Routing:** Supervisor sử dụng LLM (OpenAI) để định tuyến thông minh và có cơ chế fallback về Keyword-based khi API gặp sự cố.
- **Official MCP Protocol:** Tích hợp chuẩn MCP (Model Context Protocol) qua SSE, giúp quản lý các công cụ ngoại vi (Tools) một cách hệ thống.
- **Decoupled Data:** Dữ liệu mock (Tickets, Access Rules) được quản lý qua file JSON, tách biệt hoàn toàn khỏi logic code.

---

## 2. Sơ đồ Pipeline

```text
       [ User Request ]
              │
              ▼
      ┌──────────────┐
      │  Supervisor  │ (LLM-based Routing + Keyword Fallback)
      └──────┬───────┘
             │
      ┌──────┴─────────────────────────────────┐
      │             [ Route Decision ]         │
      ▼                      ▼                 ▼
[ Retrieval Worker ]  [ Policy Worker ]  [ Human Review ]
 (Dense Search RAG)   (Rule-based Check)  (HITL - Placeholder)
      │             (Gọi Tool qua MCP)         │
      └──────────────┬─────────────────────────┘
                     │
                     ▼
           [ Synthesis Worker ] (Grounded Answer + Citations)
                     │
                     ▼
              [ Final Output ]
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích intent và định tuyến đến Worker phù hợp. |
| **Model** | `gpt-4o-mini` (OpenAI). |
| **Cơ chế** | Sử dụng hàm `_llm_supervisor_route` để xuất JSON định tuyến; Fallback về keyword matching nếu LLM lỗi. |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích chính sách hoàn tiền và cấp quyền. |
| **Logic** | Sử dụng **Regex** để trích xuất Ticket ID/Access Level và **Keyword matching** để xác định các ngoại lệ (Flash Sale, Activated, Digital). |
| **Công cụ** | Gọi các MCP Tool: `search_kb`, `get_ticket_info`, `check_access_permission`. |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Tổng hợp câu trả lời cuối cùng từ các bằng chứng (Evidence). |
| **Model** | `openai/gpt-oss-120b` (via Groq). |
| **Grounding** | Trích dẫn inline theo format `[source_name]` dựa trên `retrieved_chunks`. |

### MCP Server (`mcp_server.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Giao thức** | Chuẩn **Official MCP** với `SseServerTransport`. |
| **Dữ liệu** | Tải động từ `data/mcp/mock_tickets.json` và `access_rules.json`. |

---

## 4. LLM Diversity (Tech Stack thực tế)

Hệ thống tận dụng thế mạnh của từng Provider (theo cấu hình `get_llm_profiles`):

| Role | Provider | Model | Tại sao chọn? |
|------|----------|-------|---------------|
| **Supervisor** | **OpenAI** | `gpt-4o-mini` | Reasoning tốt nhất cho việc định tuyến và xuất JSON. |
| **Retrieval** | **Google** | `gemini-embedding-2-preview` | Hiệu suất vector hóa tiếng Việt vượt trội. |
| **Synthesis** | **Groq** | `openai/gpt-oss-120b` | Tốc độ xử lý (Token/s) cực nhanh cho câu trả lời dài. |

---

## 5. Shared State Schema (AgentState)

| Field | Type | Mô tả |
|-------|------|-------|
| `supervisor_route` | str | Kết quả định tuyến cuối cùng. |
| `policy_result` | dict | Kết quả phân tích (True/False, reason, source). |
| `worker_io_logs` | list | Toàn bộ Input/Output của các Node để phục vụ Trace. |

---

## 6. Điểm cải tiến và Giới hạn
- **Cải tiến:** Sử dụng chuẩn MCP chính thức giúp Agent dễ dàng mở rộng thêm các Tool (Jira, Google Calendar) mà không cần sửa code Worker.
- **Giới hạn:** Policy Worker hiện tại vẫn phụ thuộc vào Rule-based; có thể nâng cấp lên LLM-based để xử lý các câu hỏi lắt léo hơn về chính sách.
