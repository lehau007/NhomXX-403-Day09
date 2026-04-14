# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Team 3 (Hậu, Tú, Hào)
**Ngày:** 14/04/2026

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.65 (Est.) | 0.41 | -0.24 | Multi-agent khắt khe hơn về grounding |
| Avg latency (ms) | 3500 (Est.) | 7716 | +4216 | Tăng do overhead điều phối và nhiều LLM calls |
| Abstain rate (%) | 15% (Est.) | 20% | +5% | Tránh hallucination tốt hơn nhờ Policy Worker |
| Multi-hop accuracy | 40% (Est.) | 80% | +40% | Cải thiện mạnh mẽ nhờ chia nhỏ task |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Dễ dàng giải trình quyết định |
| Debug time (estimate) | 20 phút | 5 phút | -15 phút | Trace giúp khoanh vùng lỗi nhanh |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)
- **Day 08:** Phản hồi nhanh, nhưng đôi khi bỏ sót chi tiết nếu prompt quá dài.
- **Day 09:** Độ trễ cao hơn không cần thiết cho các câu hỏi cực đơn giản. Tuy nhiên, tính chính xác cao và có trích dẫn rõ ràng.

### 2.2 Câu hỏi multi-hop (cross-document)
- **Day 08:** Thường bị "confused" giữa các tài liệu khác nhau, dễ dẫn đến câu trả lời trộn lẫn thông tin sai lệch.
- **Day 09:** Xử lý cực tốt. Ví dụ câu hỏi vừa về SLA vừa về Access Control được phân rã và tổng hợp chính xác từ 2 nguồn khác nhau.

### 2.3 Câu hỏi cần abstain
- **Day 08:** Có xu hướng cố gắng trả lời dựa trên kiến thức chung (hallucination).
- **Day 09:** Synthesis Worker từ chối trả lời rất dứt khoát nếu context từ Retrieval/Policy không đủ thông tin.

---

## 3. Debuggability Analysis

- **Day 08:** Khi trả lời sai, phải đoán xem do Retrieval lấy sai document hay do LLM hiểu sai prompt.
- **Day 09:** Chỉ cần mở Trace JSON. Nếu `retrieved_chunks` đúng mà `final_answer` sai -> Lỗi ở Synthesis. Nếu `supervisor_route` sai -> Lỗi ở Supervisor. Việc cô lập lỗi diễn ra trong vài giây.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Rất khó, làm loãng prompt chính. | Dễ, chỉ cần thêm 1 MCP tool. |
| Thêm 1 domain mới | Cần sửa và test lại toàn bộ prompt. | Thêm 1 Worker mới là xong. |

---

## 5. Cost & Latency Trade-off

Hệ thống Multi-agent tốn kém hơn về tài nguyên LLM (trung bình 2-3 calls cho mỗi request so với 1 call của Single Agent). Tuy nhiên, lợi ích về độ chính xác và khả năng bảo trì vượt xa chi phí này trong các hệ thống doanh nghiệp quan trọng.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**
1. Khả năng xử lý các logic nghiệp vụ phức tạp và ngoại lệ (Policy).
2. Khả năng gỡ lỗi (debug) và quan sát (observability) tuyệt vời.
3. Dễ dàng mở rộng năng lực thông qua MCP.

**Multi-agent kém hơn ở điểm nào?**
1. Độ trễ cao hơn (Latency).
2. Chi phí API cao hơn.

**Khi nào KHÔNG nên dùng multi-agent?**
Khi hệ thống chỉ cần tra cứu thông tin đơn giản trên một tập dữ liệu nhỏ và không có các quy tắc nghiệp vụ phức tạp đi kèm.
