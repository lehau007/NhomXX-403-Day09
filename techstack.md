# Tech Stack & Dependencies - Lab Day 09

Tài liệu này quy định toàn bộ các công nghệ, thư viện và tiêu chuẩn kỹ thuật được sử dụng trong hệ thống Multi-Agent Orchestration.

## 1. Ngôn ngữ & Framework Chính
- **Ngôn ngữ:** Python 3.10+
- **Agent Framework:** LangGraph (sử dụng StateGraph để xây dựng luồng Supervisor-Worker).
- **LLM Providers & Integration:** Hệ thống sử dụng đa dạng LLM tùy theo yêu cầu của từng Agent:
  - **Google (Gemini):** Tối ưu cho Embedding (`gemini-embedding-2-preview`) và các task cần xử lý ngữ cảnh dài.
  - **OpenAI (GPT):** Khả năng suy luận (reasoning) mạnh mẽ, phù hợp làm "Não bộ" cho Supervisor định tuyến.
  - **Groq:** Sử dụng thông qua OpenAI Client (bằng cách đổi `base_url`). Cung cấp tốc độ sinh text siêu nhanh (Ultra-low latency), rất phù hợp cho Synthesis Worker.
  - **Quản lý Cấu hình:** Toàn bộ API key (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`) và thiết lập Provider/Model cho từng Agent phải được đọc từ file `.env`.

## 2. Vector Database & Embedding
- **Cơ sở dữ liệu Vector:** ChromaDB (`chromadb.PersistentClient`) lưu trữ ở dạng local path (`./chroma_db`).
- **Mô hình Embedding:** Google Generative AI (Model: `models/gemini-embedding-2-preview`).
- **Yêu cầu:** Cài đặt `google-generativeai` và cấu hình `GOOGLE_API_KEY` trong file `.env`.

## 3. Giao thức Tích hợp Công cụ (Tooling)
- **MCP (Model Context Protocol):** 
  - Sử dụng đặc tả MCP để giao tiếp giữa `policy_tool_worker` và `mcp_server`.
  - Có thể tự Mock MCP bằng class/hàm Python hoặc sử dụng thư viện `mcp` chuẩn.
  - Tham khảo: [MCP Docs](https://modelcontextprotocol.io/docs)

## 4. Quản lý Môi trường & Mật khẩu
- **Biến môi trường:** Thư viện `python-dotenv` để load cấu hình từ file `.env` (chứa `OPENAI_API_KEY` hoặc `GOOGLE_API_KEY`). Không bao giờ commit `.env` lên Git.

## 5. File Formats & Observability
- **Trace Logs:** Lưu trữ dưới dạng JSON Lines (`.jsonl`) trong thư mục `artifacts/traces/`.
- **Worker Contracts:** Định nghĩa bằng `.yaml` (`contracts/worker_contracts.yaml`) để đảm bảo các node/worker truyền dữ liệu thống nhất với nhau.
- **Tài liệu:** Markdown (`.md`) cho báo cáo và giải thích kiến trúc.

---

*Lưu ý: Bất kỳ thư viện nào mới được thêm vào quá trình làm việc cần phải được cập nhật vào file `requirements.txt`.*