import sys
import os

# Adjust path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.rag.ingestion import parse_github_url
from backend.rag.parser import get_file_language, parse_python_ast

def test_parse_github_url():
    """Verify GitHub URL parser correctly extracts owners and repositories."""
    url1 = "https://github.com/fastapi/fastapi"
    url2 = "https://github.com/tiangolo/sqlmodel.git"
    url3 = "github.com/google/gemini"
    
    assert parse_github_url(url1) == ("fastapi", "fastapi")
    assert parse_github_url(url2) == ("tiangolo", "sqlmodel")
    assert parse_github_url(url3) == ("google", "gemini")
    
    # Test invalid URLs
    assert parse_github_url("https://github.com/onlyowner") is None
    assert parse_github_url("https://google.com/fastapi/fastapi") is None

def test_get_file_language():
    """Verify extension-to-language mapping detects common formats."""
    assert get_file_language("main.py") == "Python"
    assert get_file_language("src/App.tsx") == "TypeScript (React)"
    assert get_file_language("index.js") == "JavaScript"
    assert get_file_language("queries.sql") == "SQL"
    assert get_file_language("unknown.xyz") == "Unknown"

def test_parse_python_ast():
    """Verify that Python AST extracts classes, functions, and imports."""
    python_code = """
import os
from datetime import datetime

class User:
    def __init__(self, name: str):
        self.name = name
        
    async def save(self):
        pass

def main():
    pass
"""
    functions, classes, imports = parse_python_ast(python_code)
    
    # Verify imports
    assert "os" in imports
    assert "datetime.datetime" in imports or "datetime" in imports or len(imports) >= 2
    
    # Verify classes
    assert len(classes) == 1
    assert classes[0]["name"] == "User"
    
    # Verify functions
    func_names = [f["name"] for f in functions]
    assert "save" in func_names
    assert "main" in func_names
    
    # Check async flag
    save_fn = next(f for f in functions if f["name"] == "save")
    assert save_fn["is_async"] is True
    
    main_fn = next(f for f in functions if f["name"] == "main")
    assert main_fn["is_async"] is False

if __name__ == "__main__":
    test_parse_github_url()
    test_get_file_language()
    test_parse_python_ast()
    print("All backend unit tests passed successfully!")
