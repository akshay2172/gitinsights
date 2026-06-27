import os
from langchain_community.vectorstores import Chroma
from backend.rag.embeddings import get_embeddings_model

# Path to persist the Chroma database
PERSIST_DIRECTORY = os.getenv("CHROMA_DB_PATH", "./chroma_db")

def get_vectorstore() -> Chroma:
    """Initialize and return the persistent Chroma vector store."""
    embeddings = get_embeddings_model()
    # Create persist directory if it doesn't exist
    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)
    
    return Chroma(
        collection_name="gitinsight_repos",
        embedding_function=embeddings,
        persist_directory=PERSIST_DIRECTORY
    )

def index_repository_chunks(repository_id: int, chunks: list[dict]):
    """Add repository chunks to the vector store with repository_id metadata filtering."""
    if not chunks:
        return
        
    vectorstore = get_vectorstore()
    
    texts = [chunk["content"] for chunk in chunks]
    metadatas = []
    for chunk in chunks:
        meta = chunk["metadata"].copy()
        meta["repository_id"] = repository_id  # Essential for filtering by repository
        metadatas.append(meta)
        
    # We can also generate unique IDs for each chunk to allow easy update/deletion
    ids = [f"repo_{repository_id}_chunk_{i}" for i in range(len(chunks))]
    
    vectorstore.add_texts(
        texts=texts,
        metadatas=metadatas,
        ids=ids
    )

def delete_repository_vectors(repository_id: int):
    """Delete all indexed code chunks for a given repository ID."""
    vectorstore = get_vectorstore()
    
    # In ChromaDB, we can delete by ID or by metadata filter
    try:
        # Get collection directly to delete by metadata query
        collection = vectorstore._collection
        collection.delete(where={"repository_id": repository_id})
    except Exception as e:
        print(f"Error deleting vectors for repository {repository_id}: {e}")

def search_repository_code(repository_id: int, query: str, k: int = 5) -> list:
    """Perform a semantic search over a specific repository's codebase."""
    vectorstore = get_vectorstore()
    
    # Retrieve documents matching search query, filtered by repository_id
    results = vectorstore.similarity_search(
        query,
        k=k,
        filter={"repository_id": repository_id}
    )
    return results
