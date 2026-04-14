import chromadb
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def init_db():
    db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    collection_name = os.getenv("CHROMA_COLLECTION", "day09_docs")
    google_api_key = os.getenv("GOOGLE_API_KEY")
    
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found in .env")
        return

    genai.configure(api_key=google_api_key)
    
    client = chromadb.PersistentClient(path=db_path)
    # Delete collection if it exists to start fresh
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    col = client.create_collection(collection_name, metadata={"hnsw:space": "cosine"})
    
    docs_dir = './data/docs'
    if not os.path.exists(docs_dir):
        print(f"Error: {docs_dir} not found")
        return

    model_name = os.getenv("RETRIEVAL_MODEL", "models/embedding-001")
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    for fname in os.listdir(docs_dir):
        if fname.endswith(".txt"):
            with open(os.path.join(docs_dir, fname), encoding="utf-8") as f:
                content = f.read()
            
            print(f'Indexing: {fname} using {model_name}...')
            # Simple chunking by paragraph for now, or just the whole file if small
            # Given the lab scope, whole file or large chunks are fine
            
            result = genai.embed_content(
                model=model_name,
                content=content,
                task_type="retrieval_document",
            )
            embedding = result["embedding"]
            
            col.add(
                embeddings=[embedding],
                documents=[content],
                ids=[fname],
                metadatas=[{"source": fname}]
            )
    
    print('Index ready.')

if __name__ == "__main__":
    init_db()
