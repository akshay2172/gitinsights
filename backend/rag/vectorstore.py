import os
from langchain_community.vectorstores import Chroma
from backend.rag.embeddings import get_embeddings_model

# Path to persist the Chroma database
PERSIST_DIRECTORY = os.getenv("CHROMA_DB_PATH", "./chroma_db")


_vectorstore: Chroma | None = None


def get_vectorstore() -> Chroma:
    """Return a cached (singleton) persistent Chroma vector store."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = get_embeddings_model()
    # Create persist directory if it doesn't exist
    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)

    _vectorstore = Chroma(
        collection_name="gitinsight_repos",
        embedding_function=embeddings,
        persist_directory=PERSIST_DIRECTORY,
    )
    return _vectorstore


def index_repository_chunks(repository_id: int, chunks: list[dict]):
    """Add repository chunks to the vector store with repository_id metadata filtering.

    This function explicitly batch-embeds documents via:
      embedding.embed_documents([chunk.content for chunk in chunks])

    Then it inserts the precomputed embeddings into Chroma.
    """
    if not chunks:
        return

    vectorstore = get_vectorstore()
    embeddings = vectorstore.embeddings

    # Control memory usage; tune for your machine.
    batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    batch_size = max(1, batch_size)

    # Use the underlying Chroma collection API for precomputed embeddings.
    # (Chroma wrapper does not expose a public `add_embeddings` method in this version.)
    collection = vectorstore._collection

    # Batch embeddings using an explicit `batch = [chunk1, chunk2, ...]`
    # to avoid any accidental per-chunk embedding behavior.
    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        batch = chunks[start:end]

        batch_texts = [c["content"] for c in batch]
        batch_metadatas = []
        batch_ids = [f"repo_{repository_id}_chunk_{i}" for i in range(start, end)]

        for c in batch:
            meta = c["metadata"].copy()
            meta["repository_id"] = repository_id
            batch_metadatas.append(meta)

        # ---- Batch embeddings (compute once per batch) ----
        embeddings_batch = embeddings.embed_documents(batch_texts)

        # ---- Insert embeddings ----
        collection.add(
            documents=batch_texts,
            embeddings=embeddings_batch,
            metadatas=batch_metadatas,
            ids=batch_ids,
        )


def delete_repository_vectors(repository_id: int):
    """Delete all indexed code chunks for a given repository ID.

    Chroma client internals vary across versions; using the public
    vectorstore/delete API is more stable than reaching into _collection.
    """
    vectorstore = get_vectorstore()

    # Prefer metadata-based deletion when supported.
    try:
        # Most recent langchain-community Chroma exposes `delete`.
        vectorstore.delete(where={"repository_id": repository_id})
        return
    except Exception:
        pass

    # Fallback: delete by IDs if we can reconstruct them.
    try:
        # We used deterministic IDs: repo_{repository_id}_chunk_{i}
        # We don't know the max i; attempt deletion for a reasonable range.
        # Any non-existent IDs are safely ignored by Chroma.
        ids = [f"repo_{repository_id}_chunk_{i}" for i in range(0, 10000)]
        vectorstore.delete(ids=ids)
    except Exception as e:
        print(f"Error deleting vectors for repository {repository_id}: {e}")


def search_repository_code(repository_id: int, query: str, k: int = 5) -> list:
    """Perform a semantic search over a specific repository's codebase."""
    vectorstore = get_vectorstore()

    # Retrieve documents matching search query, filtered by repository_id
    results = vectorstore.similarity_search(
        query, k=k, filter={"repository_id": repository_id}
    )
    return results
