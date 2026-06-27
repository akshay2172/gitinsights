import json
import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import Repository
from backend.rag.ingestion import parse_github_url, ingest_repository, REPOS_DIR
from backend.rag.vectorstore import delete_repository_vectors
from pydantic import BaseModel, Field

router = APIRouter(prefix="/repos", tags=["Repositories"])

class RepoImportRequest(BaseModel):
    github_url: str = Field(..., description="Public GitHub repository URL")

class RepoResponse(BaseModel):
    id: int
    name: str
    owner: str
    github_url: str
    description: str | None = None
    primary_language: str | None = None
    status: str
    error_message: str | None = None
    created_at: str
    
    class Config:
        from_attributes = True

@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_repository(
    request: RepoImportRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """Import a public GitHub repository. Ingestion runs asynchronously in the background."""
    parsed = parse_github_url(request.github_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub repository URL. Must be in the format 'https://github.com/owner/repo'"
        )
    
    owner, name = parsed
    
    # Check if this repository is already imported
    existing = db.query(Repository).filter(Repository.github_url == request.github_url).first()
    if existing:
        # If it failed earlier, we reset it and re-import
        if existing.status == "failed":
            existing.status = "importing"
            existing.error_message = None
            db.commit()
            background_tasks.add_task(ingest_repository, db, existing.id)
            return existing
        return existing

    # Create new repository record
    new_repo = Repository(
        name=name,
        owner=owner,
        github_url=request.github_url,
        status="importing"
    )
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)

    # Queue background task for cloning, parsing, indexing and overview generation
    background_tasks.add_task(ingest_repository, db, new_repo.id)

    return new_repo

@router.get("/")
def list_repositories(db: Session = Depends(get_db)):
    """Retrieve all imported repositories."""
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    return repos

@router.get("/{repo_id}")
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    """Get full details of a specific repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Unpack JSON fields
    langs = json.loads(repo.languages_json) if repo.languages_json else {}
    deps = json.loads(repo.dependencies_json) if repo.dependencies_json else []
    
    return {
        "id": repo.id,
        "name": repo.name,
        "owner": repo.owner,
        "github_url": repo.github_url,
        "description": repo.description,
        "primary_language": repo.primary_language,
        "status": repo.status,
        "error_message": repo.error_message,
        "summary": repo.summary,
        "tech_stack": repo.tech_stack,
        "folder_overview": repo.folder_overview,
        "important_modules": repo.important_modules,
        "starting_point": repo.starting_point,
        "languages": langs,
        "dependencies": deps,
        "created_at": repo.created_at
    }

@router.delete("/{repo_id}")
def delete_repository(repo_id: int, db: Session = Depends(get_db)):
    """Delete an imported repository, its local folder, and its vector embeddings."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    # Delete vector embeddings
    delete_repository_vectors(repo_id)
    
    # Delete cloned folder
    clone_path = os.path.join(REPOS_DIR, f"{repo.owner}_{repo.name}")
    if os.path.exists(clone_path):
        shutil.rmtree(clone_path, ignore_errors=True)
        
    # Delete database record
    db.delete(repo)
    db.commit()
    
    return {"detail": "Repository deleted successfully"}
