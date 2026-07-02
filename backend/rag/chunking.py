from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

from backend.rag.parser import parse_code_symbols

# Maps file extension languages to LangChain's Language enum values
LANG_TO_SPLITTER = {
    "Python": Language.PYTHON,
    "JavaScript": Language.JS,
    "JavaScript (React)": Language.JS,
    "TypeScript": Language.TS,
    "TypeScript (React)": Language.TS,
    "Go": Language.GO,
    "Rust": Language.RUST,
    "Java": Language.JAVA,
    "C++": Language.CPP,
    "C": Language.CPP,
    "HTML": Language.HTML,
}


# Hard guardrail to avoid sending huge symbols to the embedding model.
# Can be overridden with env var RAG_MAX_CHUNK_CHARS.
DEFAULT_MAX_CHUNK_CHARS = 4000


def _get_comment_symbol(language: str) -> str:
    return (
        "#"
        if language
        in {
            "Python",
            "Shell",
            "YAML",
            "TOML",
        }
        else "//"
    )


def _make_chunk_header(file_path: str, language: str, chunk_index_1based: int) -> str:
    comment_symbol = _get_comment_symbol(language)
    return (
        f"{comment_symbol} File: {file_path}\n"
        f"{comment_symbol} Language: {language}\n"
        f"{comment_symbol} Chunk: {chunk_index_1based}\n\n"
    )


def _fallback_split(
    file_path: str,
    content: str,
    language: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    """Original behavior: language-aware RecursiveCharacterTextSplitter."""
    lang_enum = LANG_TO_SPLITTER.get(language)

    if lang_enum:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_enum,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    documents = splitter.create_documents([content])

    chunks: list[dict[str, Any]] = []
    for i, doc in enumerate(documents):
        header = _make_chunk_header(file_path, language, i + 1)
        chunks.append(
            {
                "content": header + doc.page_content,
                "metadata": {
                    "file_path": file_path,
                    "language": language,
                    "chunk_index": i,
                },
            }
        )

    return chunks


@dataclass(frozen=True)
class LineRange:
    # 1-based inclusive
    start_line: int
    end_line: int
    # optional traceability
    symbol_name: str | None = None
    symbol_type: str | None = None


def _merge_ranges(ranges: list[LineRange]) -> list[LineRange]:
    if not ranges:
        return []
    # Sort by start, then end
    ranges_sorted = sorted(ranges, key=lambda r: (r.start_line, r.end_line))
    merged: list[LineRange] = [ranges_sorted[0]]
    for r in ranges_sorted[1:]:
        last = merged[-1]
        if r.start_line <= last.end_line + 1:
            # Overlapping/adjacent merge; keep last traceability if present
            merged[-1] = LineRange(
                start_line=min(last.start_line, r.start_line),
                end_line=max(last.end_line, r.end_line),
                symbol_name=last.symbol_name or r.symbol_name,
                symbol_type=last.symbol_type or r.symbol_type,
            )
        else:
            merged.append(r)
    return merged


def _slice_lines(lines: list[str], start_line: int, end_line: int) -> str:
    """Slice a 1-based inclusive line interval safely."""
    n = len(lines)
    if n == 0:
        return ""
    start_idx = max(0, start_line - 1)
    end_idx_excl = min(n, end_line)  # end_line is inclusive
    if start_idx >= end_idx_excl:
        return ""
    return "".join(lines[start_idx:end_idx_excl])


def _sub_split_if_large(
    file_path: str,
    language: str,
    symbol_header_index_start: int,
    content: str,
    metadata_base: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
    max_chars: int,
) -> list[dict]:
    if len(content) <= max_chars:
        return [
            {
                "content": _make_chunk_header(
                    file_path, language, symbol_header_index_start
                )
                + content,
                "metadata": metadata_base,
            }
        ]

    # Sub-split via existing RecursiveCharacterTextSplitter (robust fallback)
    lang_enum = LANG_TO_SPLITTER.get(language)
    if lang_enum:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_enum,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    documents = splitter.create_documents([content])
    out: list[dict] = []
    for j, doc in enumerate(documents):
        # chunk_index is still 0-based global-ish; we'll let caller overwrite
        md = metadata_base.copy()
        md["chunk_index"] = metadata_base["chunk_index"] + j
        out.append(
            {
                "content": _make_chunk_header(
                    file_path, language, symbol_header_index_start + j
                )
                + doc.page_content,
                "metadata": md,
            }
        )
    return out


def split_file_into_chunks(
    file_path: str,
    content: str,
    language: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[dict]:
    """Splits file contents into semantic chunks.

    Contract:
      - returns list[dict] where each dict is:
        {"content": <header + chunk_text>, "metadata": { ... }}
    """

    # Fallback if we don't have symbol info / don't trust ranges.
    if language != "Python":
        return _fallback_split(file_path, content, language, chunk_size, chunk_overlap)

    # Symbol-based chunking for Python
    lines = content.splitlines(keepends=True)
    if not lines:
        return _fallback_split(file_path, content, language, chunk_size, chunk_overlap)

    functions, classes, _imports = parse_code_symbols(content, language)

    # If no symbols found, keep current behavior
    if not classes and not functions:
        return _fallback_split(file_path, content, language, chunk_size, chunk_overlap)

    # Build ranges
    class_ranges: list[LineRange] = [
        LineRange(
            start_line=c["start_line"],
            end_line=c["end_line"],
            symbol_name=c.get("name"),
            symbol_type="class",
        )
        for c in classes
        if isinstance(c.get("start_line"), int) and isinstance(c.get("end_line"), int)
    ]
    class_ranges = _merge_ranges(class_ranges)

    def _is_inside_any_class(func_start: int) -> bool:
        for cr in class_ranges:
            if cr.start_line <= func_start <= cr.end_line:
                return True
        return False

    function_ranges: list[LineRange] = []
    for fn in functions:
        start_line = fn.get("start_line")
        end_line = fn.get("end_line")
        name = fn.get("name")
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            continue
        if _is_inside_any_class(start_line):
            continue
        # Only keep non-nested top-level functions
        function_ranges.append(
            LineRange(
                start_line=start_line,
                end_line=end_line,
                symbol_name=name,
                symbol_type="function",
            )
        )

    symbol_ranges = _merge_ranges(class_ranges + function_ranges)

    # Covered per-line bool to compute uncovered regions without dropping content.
    n = len(lines)
    covered = [False] * n  # 0-based
    for r in symbol_ranges:
        s = max(0, r.start_line - 1)
        e = min(n, r.end_line)  # inclusive end_line
        for i in range(s, e):
            covered[i] = True

    # Build uncovered ranges (module-level gaps)
    uncovered_ranges: list[LineRange] = []
    i = 0
    while i < n:
        if covered[i]:
            i += 1
            continue
        start = i
        while i < n and not covered[i]:
            i += 1
        end_inclusive = i - 1
        # convert to 1-based inclusive lines
        uncovered_ranges.append(
            LineRange(
                start_line=start + 1,
                end_line=end_inclusive + 1,
                symbol_name=None,
                symbol_type="module",
            )
        )

    ordered_chunks = sorted(
        [*symbol_ranges, *uncovered_ranges],
        key=lambda r: (r.start_line, r.end_line),
    )

    # Emit chunks with sub-splitting guardrail
    max_chars = int(
        __import__("os").getenv("RAG_MAX_CHUNK_CHARS", str(DEFAULT_MAX_CHUNK_CHARS))
    )

    chunks: list[dict] = []
    chunk_index = 0

    for r in ordered_chunks:
        chunk_text = _slice_lines(lines, r.start_line, r.end_line)
        if not chunk_text.strip():
            continue

        metadata_base: dict[str, Any] = {
            "file_path": file_path,
            "language": language,
            "chunk_index": chunk_index,
        }
        if r.symbol_name is not None:
            metadata_base["symbol_name"] = r.symbol_name
        if r.symbol_type is not None:
            metadata_base["symbol_type"] = r.symbol_type

        # header chunk number is 1-based; keep it aligned with chunk_index+1
        sub_chunks = _sub_split_if_large(
            file_path=file_path,
            language=language,
            symbol_header_index_start=chunk_index + 1,
            content=chunk_text,
            metadata_base=metadata_base,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_chars=max_chars,
        )

        chunks.extend(sub_chunks)
        chunk_index += len(sub_chunks)

    # Final safety: if for some reason we didn't return anything, fallback.
    return (
        chunks
        if chunks
        else _fallback_split(file_path, content, language, chunk_size, chunk_overlap)
    )
