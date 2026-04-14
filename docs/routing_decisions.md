# Routing Decisions Log — Lab Day 09

**Nhóm:** Team 3 (Hậu, Tú, Hào)
**Ngày:** 14/04/2026

---

## Routing Decision #1

**Task đầu vào:**
> "SLA xử lý ticket P1 là bao lâu?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `matched retrieval keywords: ['p1', 'sla', 'ticket']`  
**MCP tools được gọi:** None (trực tiếp qua retrieval node)  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): "Ticket P1 có SLA phản hồi ban đầu 15 phút và thời gian xử lý là 4 giờ."
- confidence: 0.72
- Correct routing? Yes

**Nhận xét:** Routing chính xác dựa trên từ khóa nghiệp vụ (SLA, P1). Hệ thống nhận diện được đây là yêu cầu tra cứu thông tin tĩnh trong tài liệu.

---

## Routing Decision #2

**Task đầu vào:**
> "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi - được không?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `matched policy/access keywords: ['refund', 'flash sale']`  
**MCP tools được gọi:** `search_kb` (để lấy context cho policy analysis)  
**Workers called sequence:** `['policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): "Yêu cầu này bị chặn bởi policy. Lý do: Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4)."
- confidence: 0.1
- Correct routing? Yes

**Nhận xét:** Routing đúng vào Policy Worker giúp hệ thống áp dụng được các logic kiểm tra ngoại lệ (Flash Sale) thay vì chỉ tra cứu thông tin đơn thuần.

---

## Routing Decision #3

**Task đầu vào:**
> "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Worker được chọn:** `human_review`  
**Route reason (từ trace):** `matched ambiguous error marker without enough routing context | human review placeholder approved follow-up retrieval`  
**MCP tools được gọi:** `search_kb` (sau khi qua HITL)  
**Workers called sequence:** `['human_review', 'retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): "Không tìm thấy thông tin về mã lỗi ERR-403-AUTH trong tài liệu nội bộ."
- confidence: 0.3
- Correct routing? Yes

**Nhận xét:** Đây là cơ chế an toàn (fallback). Khi gặp mã lỗi lạ mà Supervisor không chắc chắn thuộc domain nào, nó chuyển sang Human Review để đảm bảo tính an toàn trước khi thực hiện tra cứu mặc định.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA. Nêu đủ cả hai quy trình."

**Worker được chọn:** `policy_tool_worker`  
**Route reason:** `matched policy/access keywords: ['access', 'level']`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**
Vì đây là câu hỏi **multi-hop** chứa tín hiệu của cả 2 Worker (SLA -> Retrieval, Access Level -> Policy). Tuy nhiên, Supervisor đã ưu tiên Policy Worker vì nó có khả năng gọi MCP tools mạnh hơn để kiểm tra quyền truy cập và cũng có thể gọi `search_kb` để lấy thêm thông tin SLA. Kết quả là Synthesis Worker đã tổng hợp được cả hai quy trình từ các nguồn khác nhau.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 45 | 51% |
| policy_tool_worker | 31 | 35% |
| human_review | 12 | 14% |

### Routing Accuracy

- Câu route đúng: 15 / 15 (trong bộ test_questions)
- Câu route sai: 0
- Câu trigger HITL: 12

### Lesson Learned về Routing

1. **Kết hợp Keyword và LLM:** Sử dụng keyword matching làm lớp lọc đầu tiên giúp hệ thống nhanh và rẻ.
2. **Ưu tiên Policy Worker cho các yêu cầu có Tool:** Policy Worker đa năng hơn trong việc tích hợp tool và context.

### Route Reason Quality

Các `route_reason` hiện tại đủ thông tin để debug nhanh chóng vì chỉ rõ nguồn gốc quyết định (keyword match).
