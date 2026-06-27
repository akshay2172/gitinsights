from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import FileRecord
from backend.rag.chat import generate_file_explanation, generate_function_explanation
from pydantic import BaseModel

router = APIRouter(prefix="/explain", tags=["AI Explanations"])

class FileExplainRequest(BaseModel):
    file_path: str

class FunctionExplainRequest(BaseModel):
    file_path: str
    function_name: str
    function_code: str

@router.post("/{repo_id}/file")
def explain_code_file(
    repo_id: int, 
    request: FileExplainRequest, 
    db: Session = Depends(get_db)
):
    """Retrieve or generate a high-level technical summary of a file's role and constructs."""
    file_record = db.query(FileRecord).filter(
        FileRecord.repository_id == repo_id,
        FileRecord.path == request.file_path
    ).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in this repository")
        
    # Return cached explanation if present
    if file_record.purpose_explanation:
        return {"explanation": file_record.purpose_explanation}
        
    # Generate new overview and cache it
    explanation = generate_file_explanation(
        file_content=file_record.content,
        file_path=file_record.path,
        language=file_record.language or "Unknown"
    )
    
    file_record.purpose_explanation = explanation
    db.commit()
    
    return {"explanation": explanation}

@router.post("/{repo_id}/function")
def explain_code_function(
    repo_id: int, 
    request: FunctionExplainRequest
):
    """Generate detailed line-by-step breakdown of a specific code function."""
    explanation = generate_function_explanation(
        function_code=request.function_code,
        function_name=request.function_name,
        file_path=request.file_path
    )
    return {"explanation": explanation}
