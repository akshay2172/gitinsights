import os
import ast
import re
import json

# Set of standard directories and files to ignore during repository ingestion
IGNORED_DIRS = {
    "node_modules", "venv", ".venv", "env", ".env", ".git", ".github",
    "__pycache__", "build", "dist", ".next", "out", "target", "bin", "obj"
}

IGNORED_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip", ".tar",
    ".gz", ".exe", ".dll", ".so", ".dylib", ".woff", ".woff2", ".eot", ".ttf",
    ".mp3", ".mp4", ".wav", ".avi", ".db", ".sqlite", ".pyc"
}

# Maps file extensions to programming languages
EXTENSION_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cpp": "C++",
    ".h": "C/C++",
    ".c": "C",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sh": "Shell",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    ".html": "HTML",
    ".css": "CSS",
    ".md": "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".sql": "SQL"
}

def get_file_language(file_path: str) -> str:
    _, ext = os.path.splitext(file_path.lower())
    return EXTENSION_MAP.get(ext, "Unknown")

def should_process_file(file_path: str, repo_root: str) -> bool:
    """Determine if a file should be read and processed or ignored."""
    relative_path = os.path.relpath(file_path, repo_root)
    parts = relative_path.split(os.sep)
    
    # Check if file is in any ignored folder
    for part in parts:
        if part in IGNORED_DIRS:
            return False
            
    # Check extension
    _, ext = os.path.splitext(file_path.lower())
    if ext in IGNORED_EXTS:
        return False
        
    # Ignore files that are extremely large (e.g. lock files, data dumps)
    try:
        if os.path.getsize(file_path) > 500 * 1024:  # > 500KB
            return False
    except OSError:
        return False
        
    return True

def parse_dependencies(repo_path: str) -> list[str]:
    """Parse common package manager configuration files to extract dependencies."""
    dependencies = []
    
    # Python requirements.txt
    req_path = os.path.join(repo_path, "requirements.txt")
    if os.path.isfile(req_path):
        try:
            with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name before any version specifier (e.g., fastapi>=0.90 -> fastapi)
                        parts = re.split(r"[=<>~#;]", line)
                        package = parts[0].strip()
                        if package:
                            dependencies.append(package)
        except Exception:
            pass

    # Node package.json
    pkg_path = os.path.join(repo_path, "package.json")
    if os.path.isfile(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                dependencies.extend(deps.keys())
                dependencies.extend(dev_deps.keys())
        except Exception:
            pass

    # Go go.mod
    go_path = os.path.join(repo_path, "go.mod")
    if os.path.isfile(go_path):
        try:
            with open(go_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("require ("):
                        continue
                    # Match direct requirements: package version
                    match = re.match(r"^\t?([^\s]+)\s+v[0-9]+", line)
                    if match:
                        dependencies.append(match.group(1))
        except Exception:
            pass

    # Rust Cargo.toml
    cargo_path = os.path.join(repo_path, "Cargo.toml")
    if os.path.isfile(cargo_path):
        try:
            with open(cargo_path, "r", encoding="utf-8", errors="ignore") as f:
                in_dependencies = False
                for line in f:
                    line = line.strip()
                    if line.startswith("[dependencies]") or line.startswith("[dev-dependencies]"):
                        in_dependencies = True
                        continue
                    elif line.startswith("[") and in_dependencies:
                        in_dependencies = False
                    
                    if in_dependencies and "=" in line:
                        dep_name = line.split("=")[0].strip()
                        if dep_name:
                            dependencies.append(dep_name)
        except Exception:
            pass

    return list(set(dependencies))

def parse_python_ast(code: str) -> tuple[list[dict], list[dict], list[str]]:
    """Parse Python code using AST to extract functions, classes, and imports."""
    functions = []
    classes = []
    imports = []
    
    try:
        root = ast.parse(code)
    except Exception:
        return functions, classes, imports

    for node in ast.walk(root):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
        
        # Functions
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if this function is nested in a class
            is_method = False
            curr = node
            # Determine end line
            end_line = getattr(node, "end_lineno", node.lineno)
            
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
                
            functions.append({
                "name": node.name,
                "start_line": node.lineno,
                "end_line": end_line,
                "args": args,
                "is_async": isinstance(node, ast.AsyncFunctionDef)
            })
            
        # Classes
        elif isinstance(node, ast.ClassDef):
            end_line = getattr(node, "end_lineno", node.lineno)
            classes.append({
                "name": node.name,
                "start_line": node.lineno,
                "end_line": end_line,
                "bases": [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
            })
            
    return functions, classes, list(set(imports))

def parse_regex_code_symbols(code: str, language: str) -> tuple[list[dict], list[dict], list[str]]:
    """Generic regex parser for languages other than Python (JS, TS, C++, Go, Java, Rust)."""
    functions = []
    classes = []
    imports = []
    
    lines = code.split("\n")
    
    # Setup some simple regexes for common constructs
    # Functions: e.g. function name(args) or name = (args) => or func name(args)
    # JS/TS/Java/C# function
    fn_js_regex = re.compile(r"(?:const|let|var)?\s*([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>")
    fn_standard_regex = re.compile(r"(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)")
    
    # Go function: func (receiver) Name(args) or func Name(args)
    fn_go_regex = re.compile(r"func\s+(?:\([^)]*\)\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)")
    
    # Rust function: fn name(args)
    fn_rs_regex = re.compile(r"fn\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)")

    # Classes: class Name
    class_regex = re.compile(r"class\s+([a-zA-Z0-9_$]+)")

    # Imports: import X or require(X)
    import_js_regex = re.compile(r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]")
    require_js_regex = re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
    import_go_regex = re.compile(r"import\s+['\"]([^'\"]+)['\"]")
    
    for i, line in enumerate(lines):
        line_num = i + 1
        
        # JS/TS imports
        if "import" in line or "require" in line:
            js_imp = import_js_regex.search(line)
            if js_imp:
                imports.append(js_imp.group(1))
            else:
                req_imp = require_js_regex.search(line)
                if req_imp:
                    imports.append(req_imp.group(1))
                    
        # Go imports
        if language == "Go":
            go_imp = import_go_regex.search(line)
            if go_imp:
                imports.append(go_imp.group(1))

        # Functions
        fn_match = None
        if language in ["JavaScript", "TypeScript", "JavaScript (React)", "TypeScript (React)"]:
            fn_match = fn_js_regex.search(line) or fn_standard_regex.search(line)
        elif language == "Go":
            fn_match = fn_go_regex.search(line)
        elif language == "Rust":
            fn_match = fn_rs_regex.search(line)
            
        if fn_match:
            name = fn_match.group(1)
            args_str = fn_match.group(2) if len(fn_match.groups()) > 1 else ""
            args = [a.strip() for a in args_str.split(",") if a.strip()]
            # Assume 10-line placeholder scope range since regex can't easily parse block structure boundaries
            functions.append({
                "name": name,
                "start_line": line_num,
                "end_line": line_num + 15,
                "args": args
            })
            
        # Classes
        cl_match = class_regex.search(line)
        if cl_match:
            classes.append({
                "name": cl_match.group(1),
                "start_line": line_num,
                "end_line": line_num + 30
            })
            
    return functions, classes, list(set(imports))

def parse_code_symbols(code: str, language: str) -> tuple[list[dict], list[dict], list[str]]:
    """Route code to language-specific parser."""
    if language == "Python":
        return parse_python_ast(code)
    else:
        return parse_regex_code_symbols(code, language)
