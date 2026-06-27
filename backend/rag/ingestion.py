import os
import stat
import shutil
import git
import re
import json
from sqlalchemy.orm import Session
from backend.database.models import Repository, FileRecord
from backend.rag.parser import should_process_file, get_file_language, parse_dependencies, parse_code_symbols
from backend.rag.chunking import split_file_into_chunks
from backend.rag.vectorstore import index_repository_chunks, delete_repository_vectors
from backend.rag.chat import get_llm
from backend.rag.prompts import OVERVIEW_SYSTEM_PROMPT, OVERVIEW_USER_TEMPLATE

REPOS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "repositories"))

def parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract owner and repo name from a GitHub URL."""
    # Matches patterns like:
    # https://github.com/owner/repo
    # https://github.com/owner/repo.git
    # github.com/owner/repo
    pattern = r"github\.com/([^/]+)/([^/.]+)(?:\.git)?$"
    match = re.search(pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None

def build_directory_tree_text(repo_path: str, max_depth: int = 4) -> str:
    """Generate a clean text tree of the directory structure."""
    lines = []
    
    def _walk(directory: str, prefix: str = "", depth: int = 1):
        if depth > max_depth:
            return
        try:
            items = sorted(os.listdir(directory))
        except OSError:
            return
            
        # Filter items to ignore non-relevant ones
        items = [
            item for item in items 
            if item not in [".git", "node_modules", "venv", ".venv", "__pycache__", ".next"]
        ]
        
        count = len(items)
        for i, item in enumerate(items):
            path = os.path.join(directory, item)
            is_last = (i == count - 1)
            connector = "└── " if is_last else "├── "
            
            lines.append(f"{prefix}{connector}{item}")
            
            if os.path.isdir(path):
                new_prefix = prefix + ("    " if is_last else "│   ")
                _walk(path, new_prefix, depth + 1)
                
    _walk(repo_path)
    return "\n".join(lines)

def ingest_repository(db: Session, repository_id: int):
    """Orchestrate the ingestion of a GitHub repository from cloning to RAG indexing."""
    repo_record = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo_record:
        return

    # Create repositories base folder
    os.makedirs(REPOS_DIR, exist_ok=True)
    clone_path = os.path.join(REPOS_DIR, f"{repo_record.owner}_{repo_record.name}")

    try:
        # Step 1: Clean existing cloned folder if any
        if os.path.exists(clone_path):
            def _on_rm_error(func, path, exc_info):
                """Handle read-only files (common in .git on Windows)."""
                os.chmod(path, stat.S_IWRITE)
                func(path)

            shutil.rmtree(clone_path, onerror=_on_rm_error)

            # Verify the directory was actually removed
            if os.path.exists(clone_path):
                raise OSError(
                    f"Failed to remove existing clone directory: {clone_path}. "
                    "It may be locked by another process."
                )

        # Step 2: Update status to cloning
        repo_record.status = "cloning"
        db.commit()

        # Step 3: Git Clone
        git.Repo.clone_from(repo_record.github_url, clone_path, depth=1)
        
        repo_record.status = "parsing"
        db.commit()

        # Step 4: Parse files and extract metadata
        file_records_to_create = []
        all_chunks = []
        languages_stats = {}
        total_code_size = 0
        readme_content = "No README file found."

        # Walk through the repository
        for root, _, files in os.walk(clone_path):
            for file in files:
                full_path = os.path.join(root, file)
                if not should_process_file(full_path, clone_path):
                    continue
                    
                rel_path = os.path.relpath(full_path, clone_path).replace(os.sep, "/")
                lang = get_file_language(full_path)
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue

                size = len(content)
                total_code_size += size
                languages_stats[lang] = languages_stats.get(lang, 0) + size
                
                # Check for README
                if file.lower() == "readme.md" and "/" not in rel_path:
                    readme_content = content[:15000] # Limit readme size for LLM

                # AST/Regex parse code structure (functions, classes, imports)
                functions, classes, imports = parse_code_symbols(content, lang)
                
                # Create DB record model
                file_rec = FileRecord(
                    repository_id=repository_id,
                    path=rel_path,
                    name=file,
                    language=lang,
                    size=size,
                    content=content,
                    functions_json=json.dumps(functions),
                    classes_json=json.dumps(classes),
                    imports_json=json.dumps(imports)
                )
                file_records_to_create.append(file_rec)

                # Chunk file for RAG
                file_chunks = split_file_into_chunks(rel_path, content, lang)
                all_chunks.extend(file_chunks)

        # Step 5: Save all file records to DB
        db.bulk_save_objects(file_records_to_create)
        db.commit()

        # Calculate primary language and percentages
        if total_code_size > 0:
            lang_pct = {k: round((v / total_code_size) * 100, 1) for k, v in languages_stats.items()}
            repo_record.languages_json = json.dumps(lang_pct)
            # Find primary language
            primary = max(languages_stats, key=languages_stats.get) if languages_stats else "Unknown"
            repo_record.primary_language = primary
        else:
            repo_record.languages_json = json.dumps({})
            repo_record.primary_language = "Unknown"

        # Parse dependencies
        deps = parse_dependencies(clone_path)
        repo_record.dependencies_json = json.dumps(deps)
        db.commit()

        # Step 6: Vector Indexing (ChromaDB)
        repo_record.status = "indexing"
        db.commit()
        
        # Clear existing vectors just in case
        delete_repository_vectors(repository_id)
        
        # Index in ChromaDB
        index_repository_chunks(repository_id, all_chunks)

        # Step 7: Generate Repository LLM Overview
        dir_tree = build_directory_tree_text(clone_path)
        
        llm = get_llm()
        messages = [
            {"role": "system", "content": OVERVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": OVERVIEW_USER_TEMPLATE.format(
                owner=repo_record.owner,
                name=repo_record.name,
                primary_language=repo_record.primary_language,
                dependencies=", ".join(deps[:30]),
                directory_structure=dir_tree[:5000],
                readme_content=readme_content
            )}
        ]

        try:
            # We convert our system/user dicts to langchain format
            from langchain_core.messages import SystemMessage, HumanMessage
            lc_messages = [
                SystemMessage(content=messages[0]["content"]),
                HumanMessage(content=messages[1]["content"])
            ]
            response = llm.invoke(lc_messages)
            overview_data = json.loads(response.content)
            
            repo_record.summary = overview_data.get("summary")
            repo_record.tech_stack = overview_data.get("tech_stack")
            repo_record.folder_overview = overview_data.get("folder_overview")
            repo_record.important_modules = overview_data.get("important_modules")
            repo_record.starting_point = overview_data.get("starting_point")
        except Exception as e:
            # Fallback mock summary if LLM or JSON parsing fails
            print(f"Error generating LLM overview: {e}")
            repo_record.summary = f"A repository named {repo_record.name} developed by {repo_record.owner} primarily written in {repo_record.primary_language}."
            repo_record.tech_stack = "- Primary Language: " + repo_record.primary_language
            repo_record.folder_overview = "Contains standard codebase directory trees."
            repo_record.important_modules = "Includes core application modules."
            repo_record.starting_point = "Explore top level directories and source entrypoints."

        # Complete!
        repo_record.status = "ready"
        repo_record.error_message = None
        db.commit()

    except Exception as e:
        db.rollback()
        repo_record.status = "failed"
        repo_record.error_message = str(e)
        db.commit()
        print(f"Ingestion failed for repository {repository_id}: {e}")
        import traceback
        traceback.print_exc()
