from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import Repository
from backend.rag.vectorstore import search_repository_code

router = APIRouter(prefix="/search", tags=["Code Search"])

@router.get("/{repo_id}")
def semantic_code_search(
    repo_id: int, 
    q: str = Query(..., description="Natural language search query"), 
    k: int = Query(5, description="Number of results to return"), 
    db: Session = Depends(get_db)
):
    """Perform a semantic similarity code search across the repository chunks."""
    # Ensure repository exists
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    if not q.strip():
        return []
        
    # Search ChromaDB
    docs = search_repository_code(repo_id, q, k=k)
    
    results = []
    for doc in docs:
        file_path = doc.metadata.get("file_path")
        language = doc.metadata.get("language")
        chunk_idx = doc.metadata.get("chunk_index")
        
        # Simple extraction of function if we find comments in the header
        lines = doc.page_content.split("\n")
        code_lines = [l for l in lines if not (l.startswith("//") or l.startswith("#"))]
        snippet = "\n".join(code_lines).strip()
        
        results.append({
            "file_path": file_path,
            "language": language,
            "chunk_index": chunk_idx,
            "matched_context": doc.page_content,
            "snippet": snippet
        })
        
    return results
