# Routing Decisions Log — Lab Day 09

**Nhóm:** Team 3 (Hậu, Tú, Hào)
**Ngày:** 14/04/2026

---

## Routing Decision #1 (Knowledge Retrieval)

**Task đầu vào:**
> "SLA xử lý ticket P1 là bao lâu?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `llm_route | The query asks about SLA for P1 tickets, which falls under the retrieval_worker category (P1, SLA, ticket).`  
**MCP tools được gọi:** None (truy vấn trực tiếp qua retrieval node)  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- **final_answer:** "SLA xử lý ticket P1 được quy định như sau: Phản hồi ban đầu (15 phút), Xử lý và khắc phục (4 giờ)."
- **confidence:** 0.72
- **Nguồn trích dẫn:** `sla_p1_2026.txt`

---

## Routing Decision #2 (Policy Analysis)

**Task đầu vào:**
> "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `llm_route | User asks about refund timeframe, which falls under refund policy handling.`  
**MCP tools được gọi:** None (phân tích logic dựa trên chunks)  
**Workers called sequence:** `['retrieval_worker', 'policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- **final_answer:** "Khách hàng có thể yêu cầu hoàn tiền trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng."
- **policy_result:** Phát hiện 2 ngoại lệ (Flash Sale và Digital Product) không được hoàn tiền.
- **confidence:** 0.51
- **Nguồn trích dẫn:** `policy_refund_v4.txt`

---

## Routing Decision #3 (Complex Access with MCP)

**Task đầu vào:**
> "Ai phải phê duyệt để cấp quyền Level 3?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `llm_route | The query asks who must approve to grant a Level 3 access permission, which falls under access level/permission tasks requiring the policy tool.`  
**MCP tools được gọi:** `check_access_permission(access_level=3)`  
**Workers called sequence:** `['retrieval_worker', 'policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- **final_answer:** "Để cấp quyền Level 3 (Elevated Access), những người sau đây phải phê duyệt: Line Manager, IT Admin và IT Security."
- **mcp_result:** Tool trả về danh sách approvers khớp hoàn toàn với tài liệu SOP.
- **confidence:** 0.65
- **Nguồn trích dẫn:** `access_control_sop.txt`
