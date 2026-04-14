"""
workers/retrieval.py - Retrieval Worker
Sprint 2: retrieve evidence from ChromaDB and return chunks + sources.
"""

import os

from dotenv import load_dotenv


load_dotenv()


WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3


def _get_embedding_fn():
    """
    Return an embedding function based on provider config from .env.

    Preferred layout from guidelines.md / techstack.md:
    - Retrieval -> Google Gemini embeddings
    - Fallbacks stay graceful for local testing
    """
    provider = os.getenv("RETRIEVAL_PROVIDER", "google").lower()
    model_name = os.getenv("RETRIEVAL_MODEL", "gemini-embedding-2-preview")

    if provider == "google":
        try:
            import google.generativeai as genai

            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)

                def embed(text: str) -> list:
                    result = genai.embed_content(
                        model=model_name,
                        content=text,
                        task_type="retrieval_query",
                    )
                    return result["embedding"]

                return embed
        except Exception as error:
            print(f"Warning: Google embedding setup failed: {error}")

    if provider == "openai":
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            def embed(text: str) -> list:
                response = client.embeddings.create(input=text, model=model_name)
                return response.data[0].embedding

            return embed
        except Exception as error:
            print(f"Warning: OpenAI embedding setup failed: {error}")

    if provider == "local":
        try:
            from sentence_transformers import SentenceTransformer

            local_model = SentenceTransformer(model_name)

            def embed(text: str) -> list:
                return local_model.encode([text])[0].tolist()

            return embed
        except Exception as error:
            print(f"Warning: local embedding setup failed: {error}")

    import random

    def embed(text: str) -> list:
        return [random.random() for _ in range(384)]

    print("Warning: falling back to random embeddings for local smoke tests.")
    return embed


def _get_collection():
    import chromadb

    db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    collection_name = os.getenv("CHROMA_COLLECTION", "day09_docs")

    client = chromadb.PersistentClient(path=db_path)
    try:
        return client.get_collection(collection_name)
    except Exception:
        print(
            f"Warning: collection '{collection_name}' is missing or empty. "
            "Returning an auto-created empty collection."
        )
        return client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        chunks = []
        for document, distance, metadata in zip(documents, distances, metadatas):
            metadata = metadata or {}
            chunks.append(
                {
                    "text": document,
                    "source": metadata.get("source", "unknown"),
                    "score": round(max(0.0, 1 - distance), 4),
                    "metadata": metadata,
                }
            )
        return chunks
    except Exception as error:
        print(f"Warning: ChromaDB query failed: {error}")
        return []


def run(state: dict) -> dict:
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)
    llm_profile = state.get("llm_profiles", {}).get(
        "retrieval",
        {
            "provider": os.getenv("RETRIEVAL_PROVIDER", "google"),
            "model": os.getenv("RETRIEVAL_MODEL", "gemini-embedding-2-preview"),
        },
    )

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "top_k": top_k,
            "llm_profile": llm_profile,
        },
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)
        sources = list(dict.fromkeys(chunk["source"] for chunk in chunks))

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources
        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )
    except Exception as error:
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        worker_io["error"] = {
            "code": "RETRIEVAL_FAILED",
            "reason": str(error),
        }
        state["history"].append(f"[{WORKER_NAME}] ERROR: {error}")

    state["worker_io_logs"].append(worker_io)
    return state


if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker - Standalone Test")
    print("=" * 50)

    for query in [
        "SLA ticket P1 la bao lau?",
        "Dieu kien duoc hoan tien la gi?",
        "Ai phe duyet cap quyen Level 3?",
    ]:
        result = run({"task": query, "history": []})
        print(f"\nQuery: {query}")
        print(f"Retrieved: {len(result.get('retrieved_chunks', []))} chunks")
        print(f"Sources: {result.get('retrieved_sources', [])}")
