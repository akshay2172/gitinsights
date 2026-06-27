import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import FileRecord, Repository

router = APIRouter(prefix="/explorer", tags=["File Explorer"])

def build_tree_from_paths(paths_info: list[dict]) -> list[dict]:
    """Helper function to build a nested folder tree from flat file paths."""
    tree = {}
    
    for item in paths_info:
        path_str = item["path"]
        parts = path_str.split("/")
        
        current = tree
        for i, part in enumerate(parts):
            is_file = (i == len(parts) - 1)
            
            if part not in current:
                if is_file:
                    current[part] = {
                        "name": part,
                        "type": "file",
                        "path": path_str,
                        "language": item["language"],
                        "size": item["size"]
                    }
                else:
                    current[part] = {
                        "name": part,
                        "type": "directory",
                        "children": {}
                    }
            
            if not is_file:
                current = current[part]["children"]
                
    # Helper to convert dictionaries of children to sorted lists recursively
    def format_node(node):
        if node["type"] == "file":
            return node
        
        children_list = []
        for child_name, child_node in sorted(node["children"].items(), key=lambda x: (x[1]["type"] != "directory", x[0])):
            children_list.append(format_node(child_node))
            
        return {
            "name": node["name"],
            "type": "directory",
            "children": children_list
        }
        
    result = []
    for node_name, node_data in sorted(tree.items(), key=lambda x: (x[1]["type"] != "directory", x[0])):
        result.append(format_node(node_data))
        
    return result

@router.get("/{repo_id}/tree")
def get_file_tree(repo_id: int, db: Session = Depends(get_db)):
    """Retrieve the hierarchical folder tree for a repository."""
    # Ensure repository exists
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    # Query all file records for this repository
    files = db.query(FileRecord.path, FileRecord.language, FileRecord.size).filter(
        FileRecord.repository_id == repo_id
    ).all()
    
    paths_info = [
        {"path": f.path, "language": f.language, "size": f.size}
        for f in files
    ]
    
    nested_tree = build_tree_from_paths(paths_info)
    return nested_tree

@router.get("/{repo_id}/file")
def get_file_content(
    repo_id: int, 
    path: str = Query(..., description="Relative file path"), 
    db: Session = Depends(get_db)
):
    """Retrieve details and content of a specific code file in a repository."""
    file_record = db.query(FileRecord).filter(
        FileRecord.repository_id == repo_id,
        FileRecord.path == path
    ).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in this repository")
        
    # Decode JSON features
    funcs = json.loads(file_record.functions_json) if file_record.functions_json else []
    classes = json.loads(file_record.classes_json) if file_record.classes_json else []
    imports = json.loads(file_record.imports_json) if file_record.imports_json else []
    
    return {
        "id": file_record.id,
        "path": file_record.path,
        "name": file_record.name,
        "language": file_record.language,
        "size": file_record.size,
        "content": file_record.content,
        "purpose_explanation": file_record.purpose_explanation,
        "functions": funcs,
        "classes": classes,
        "imports": imports
    }
