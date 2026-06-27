from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

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
    "HTML": Language.HTML
}

def split_file_into_chunks(file_path: str, content: str, language: str, chunk_size: int = 1500, chunk_overlap: int = 200) -> list[dict]:
    """Splits file contents into semantic chunks with language-specific splitting rules."""
    lang_enum = LANG_TO_SPLITTER.get(language)
    
    if lang_enum:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_enum,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
    documents = splitter.create_documents([content])
    
    chunks = []
    for i, doc in enumerate(documents):
        # Prepend a context header to the chunk to give the LLM clear context during QA
        comment_symbol = "#" if language == "Python" or language == "Shell" or language == "YAML" or language == "TOML" else "//"
        header = f"{comment_symbol} File: {file_path}\n{comment_symbol} Language: {language}\n{comment_symbol} Chunk: {i+1}\n\n"
        context_content = header + doc.page_content
        
        chunks.append({
            "content": context_content,
            "metadata": {
                "file_path": file_path,
                "language": language,
                "chunk_index": i
            }
        })
        
    return chunks
