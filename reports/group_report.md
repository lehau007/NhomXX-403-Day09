# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Team 24 (VinUni Lab)  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Hậu | Supervisor & Evaluator |  |
| Tú | Worker Specialist |  |
| Hào | Integration & MCP |  |

**Ngày nộp:** 14/04/2026  
**Repo:** https://github.com/team24/lab-day-09  

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

Hệ thống của chúng tôi được xây dựng theo mô hình **Supervisor-Worker** linh hoạt. Trái tim của hệ thống là `graph.py`, nơi Supervisor (sử dụng GPT-4o-mini qua Groq) đóng vai trò điều phối chính. 

**Routing logic cốt lõi:**
Chúng tôi sử dụng cơ chế định tuyến lai (Hybrid Routing):
- **Ưu tiên LLM Routing:** Supervisor sử dụng LLM để phân loại ý định người dùng vào 3 nhóm: `retrieval_worker`, `policy_tool_worker`, và `human_review`. Điều này giúp xử lý các câu hỏi phức tạp không chứa từ khóa trực tiếp.
- **Keyword Fallback:** Trong trường hợp lỗi API hoặc timeout, hệ thống tự động chuyển sang keyword matching để đảm bảo tính ổn định (high availability).

**MCP tools đã tích hợp:**
Chúng tôi đã xây dựng một MCP Server hoàn chỉnh với 4 công cụ thực tế:
- `search_kb`: Truy vấn Knowledge Base với cơ chế scoring đơn giản.
- `get_ticket_info`: Tra cứu thông tin ticket từ dữ liệu mock (Jira-style).
- `check_access_permission`: Kiểm tra quyền truy cập dựa trên Approval Matrix trong SOP.
- `create_ticket`: Cho phép tạo ticket IT hỗ trợ ngay khi agent không thể tự giải quyết.

---

## 2. Quyết định kỹ thuật tiêu biểu

### Quyết định: Sử dụng Hybrid Routing (LLM + Keyword Fallback)
- **Vấn đề:** Nếu chỉ dùng Keyword, hệ thống sẽ bỏ lỡ các câu hỏi diễn đạt gián tiếp (ví dụ: "Tôi không vào được hệ thống P1" thay vì hỏi "SLA P1 là gì"). Nếu chỉ dùng LLM, hệ thống sẽ crash nếu API chậm.
- **Giải pháp:** Implement hàm `_llm_supervisor_route` với cơ chế try/except bao quanh. Nếu LLM fail, logic `supervisor_node` sẽ chạy tiếp xuống phần keyword matching.
- **Kết quả:** Trace `q03` cho thấy LLM nhận diện đúng yêu cầu "Ai phê duyệt Level 3" thuộc về policy mặc dù không có từ khóa "refund".

---

## 3. Kết quả đánh giá (Trace Analysis)

Dựa trên kết quả chạy 15 câu hỏi test và 10 câu hỏi grading:
- **Độ chính xác (Accuracy):** Cải thiện rõ rệt ở các câu hỏi Multi-hop (như gq09) nhờ khả năng gọi tuần tự Retrieval -> Policy -> Synthesis.
- **Độ tin cậy (Confidence):** Trung bình đạt 0.68. Các câu hỏi có nguồn trích dẫn rõ ràng (SLA, Refund) đạt trên 0.8.
- **Thời gian phản hồi (Latency):** Trung bình 12-15s do phải qua nhiều bước trung gian. Đây là điểm đánh đổi để có được câu trả lời grounded.
- **Abstain rate:** Hệ thống từ chối trả lời (abstain) đúng 100% các câu hỏi không có trong tài liệu (ví dụ: gq07 về mức phạt tài chính).

---

## 4. Bài học kinh nghiệm

1. **State Management là chìa khóa:** Việc thống nhất cấu trúc `AgentState` ngay từ đầu giúp 3 thành viên ghép code cực nhanh mà không gặp lỗi xung đột dữ liệu.
2. **Sức mạnh của MCP:** Việc tách biệt logic nghiệp vụ (tra cứu ticket, check quyền) ra MCP Server giúp code worker sạch sẽ hơn và dễ dàng tái sử dụng cho các dự án khác.
3. **Trace-driven Development:** Việc debug dựa trên file JSON trace giúp nhóm phát hiện ra Supervisor đôi khi phân loại sai "Refund" vào "Retrieval", từ đó tinh chỉnh Prompt kịp thời.
