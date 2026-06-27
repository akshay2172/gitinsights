from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import Repository
from backend.rag.chat import query_repository_chat
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chat", tags=["Repository Chat"])

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender: 'user' or 'assistant'")
    content: str = Field(..., description="Text content of the message")

class ChatRequest(BaseModel):
    query: str = Field(..., description="User question about the codebase")
    chat_history: list[ChatMessage] = Field(default=[], description="Previous conversation logs")

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]

@router.post("/{repo_id}", response_model=ChatResponse)
def codebase_chat(
    repo_id: int, 
    request: ChatRequest, 
    db: Session = Depends(get_db)
):
    """Ask questions about the repository. Returns answers with source file citations."""
    # Ensure repository exists and is ready
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Repository is not ready. Current status: {repo.status}"
        )
        
    # Standardize chat history formatting
    formatted_history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.chat_history
    ]
    
    # Run retrieval QA
    answer, sources = query_repository_chat(
        repository_id=repo_id,
        query=request.query,
        chat_history=formatted_history
    )
    
    return ChatResponse(answer=answer, sources=sources)
