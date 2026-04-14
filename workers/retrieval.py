"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────


WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3


def _get_embedding_fn():
    """
    Trả về embedding function.
    Sprint 1: Dùng Google Generative AI (Gemini).
    """
    model_provider = os.getenv("RETRIEVAL_PROVIDER", "google")
    if model_provider == "google":
        try:
            import google.generativeai as genai

            # Option: Google Gemini (Cần GOOGLE_API_KEY)
            api_key = os.getenv("GOOGLE_API_KEY")
            embedding_model = os.getenv("RETRIEVAL_MODEL", "gemini-embedding-2-preview")
            if api_key:
                try:
                    genai.configure(api_key=api_key)

                    def embed(text: str) -> list:
                        result = genai.embed_content(model=embedding_model, content=text, task_type="retrieval_query")
                        return result["embedding"]

                    return embed
                except Exception as e:
                    print(f"⚠️  Google Embedding error: {e}")
        except ImportError:
            print("Error: google.generativeai is not installed")

    elif model_provider == "openai":
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            embedding_model = os.getenv("RETRIEVAL_MODEL", "text-embedding-3-small")

            def embed(text: str) -> list:
                resp = client.embeddings.create(input=text, model=embedding_model)
                return resp.data[0].embedding

            return embed
        except ImportError:
            pass
    elif model_provider == "local":
        try:
            from sentence_transformers import SentenceTransformer

            embedding_model = os.getenv("RETRIEVAL_MODEL", "all-MiniLM-L6-v2")
            model = SentenceTransformer(embedding_model)

            def embed(text: str) -> list:
                return model.encode([text])[0].tolist()

            return embed
        except ImportError:
            pass
    else:
        # Fallback: random embeddings cho test (KHÔNG dùng production)
        import random

        def embed(text: str) -> list:
            # text-embedding-004 có 768 dimensions mặc định
            return [random.random() for _ in range(768)]

        print("⚠️  WARNING: Using random embeddings (test only). Check GOOGLE_API_KEY.")
        return embed


def _get_collection():
    """
    Kết nối ChromaDB collection.
    TODO Sprint 2: Đảm bảo collection đã được build từ Step 3 trong README.
    """
    import chromadb

    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        collection = client.get_collection("day09_docs")
    except Exception:
        # Auto-create nếu chưa có
        collection = client.get_or_create_collection("day09_docs", metadata={"hnsw:space": "cosine"})
        print("⚠️  Collection 'day09_docs' chưa có data. Chạy index script trong README trước.")
    return collection


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top_k chunks.

    TODO Sprint 2: Implement phần này.
    - Dùng _get_embedding_fn() để embed query
    - Query collection với n_results=top_k
    - Format result thành list of dict

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    # TODO: Implement dense retrieval
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_embedding], n_results=top_k, include=["documents", "distances", "metadatas"]
        )

        chunks = []
        for i, (doc, dist, meta) in enumerate(
            zip(results["documents"][0], results["distances"][0], results["metadatas"][0])
        ):
            chunks.append(
                {
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "score": round(1 - dist, 4),  # cosine similarity
                    "metadata": meta,
                }
            )
        return chunks

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        # Fallback: return empty (abstain)
        return []


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)

        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}")

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state.setdefault("worker_io_logs", []).append(worker_io)

    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
