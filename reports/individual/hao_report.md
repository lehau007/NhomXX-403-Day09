# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hào - 2A202600133
**Vai trò trong nhóm:** MCP & Policy Worker Lead / Infrastructure Specialist  
**Ngày nộp:** 14/04/2026

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi chịu trách nhiệm chính về hạ tầng kết nối công cụ và logic điều phối thông tin của hệ thống. Các phần tôi trực tiếp thực hiện bao gồm:
- **MCP Server (`mcp_server.py`):** Triển khai server theo chuẩn giao thức **Official MCP Protocol** sử dụng thư viện `mcp[server]` và `SseServerTransport`. 
- **Policy Worker (`workers/policy_tool.py`):** Xây dựng Worker phân tích chính sách và trích xuất dữ liệu thông qua việc gọi các MCP Tool (`get_ticket_info`, `check_access_permission`).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Chuyển đổi toàn bộ kiến trúc server từ FastAPI REST đơn thuần sang chuẩn **Official MCP SSE (Server-Sent Events) Transport**.

**Lý do:**
Việc sử dụng các endpoint HTTP POST thông thường tuy đơn giản nhưng không tuân thủ đặc tả (spec) của MCP, dẫn đến việc các Client chuẩn (như Claude Desktop hay các bộ thư viện MCP SDK) không thể "hiểu" và gọi tool tự động được. 

Tôi quyết định sử dụng `mcp.server.Server` kết hợp với `SseServerTransport`. Quyết định này giúp hệ thống của chúng ta có khả năng **Tool Discovery** tự động. Khi Client kết nối vào endpoint `/sse`, server sẽ tự động liệt kê danh sách tool và schema thông qua giao thức handshake chuẩn của MCP, thay vì phải khai báo thủ công ở phía Client. Điều này giúp tách biệt hoàn toàn tầng ứng dụng (Agent) khỏi tầng nghiệp vụ (Tools).

**Bằng chứng từ code (`mcp_server.py`):**
```python
from mcp.server.sse import SseServerTransport
# ...
@app.get("/sse")
async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** "Protocol Incompatibility & Non-standard API Implementation" (Bất tương thích giao thức).

**Symptom:** 
Trong phiên bản đầu tiên, server sử dụng các endpoint tùy biến như `/tools` và `/tools/call`. Các Agent chuẩn MCP (MCP Clients) không thể kết nối hoặc gọi tool vì chúng mong đợi một luồng dữ liệu liên tục qua SSE hoặc Stdio theo đúng đặc tả của thư viện `mcp`.

**Root cause:**
Sử dụng FastAPI theo cách truyền thống (Request-Response JSON) thay vì tuân thủ mô hình **Transport-based Execution** của MCP. Điều này làm mất đi khả năng tương tác liên thông (Interoperability) của hệ thống.

**Cách sửa:**
Tôi đã loại bỏ hoàn toàn các endpoint REST cũ và tích hợp thư viện `mcp.server`. Tôi đã triển khai cơ chế `sse.connect_sse` để tạo ra một kênh truyền dữ liệu song hướng (Bi-directional stream). Việc sửa lỗi này không chỉ giúp hệ thống chạy được mà còn giúp nó đạt chuẩn công nghiệp, cho phép bất kỳ Client MCP nào cũng có thể cắm vào và sử dụng bộ tool của chúng ta ngay lập tức.

**Bằng chứng:**
Server hiện tại khởi động với thông báo: `Starting MCP Server on http://127.0.0.1:8000/sse` và xử lý tin nhắn qua endpoint `/messages` theo đúng đặc tả SSE Transport.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Đóng góp tốt nhất của tôi là việc chủ động nghiên cứu và đưa vào sử dụng SSE Transport cũng như Official MCP SDK. Tôi hy vọng việc tiên phong áp dụng các giải pháp này sẽ tạo nền tảng tốt cho các bước phát triển tiếp theo của nhóm.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Phần xử lý Encoding (UTF-8) trên terminal Windows vẫn còn một số lỗi hiển thị ký tự đặc biệt, tôi cần tìm giải pháp triệt để hơn thay vì chỉ dùng `sys.stdout.reconfigure`.

**Nhóm phụ thuộc vào tôi ở đâu?**
Nếu không có Server SSE chuẩn, Agent sẽ bị cô lập và không thể tương tác với bất kỳ dữ liệu thực tế nào từ hệ thống.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ viết thêm bộ **Adapter** để server có thể hỗ trợ song song cả **Stdio Transport** (cho các công cụ CLI) và **SSE Transport** (cho Web App), giúp bộ công cụ của nhóm trở nên linh hoạt tối đa trên mọi môi trường.

---
