import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from backend.rag.vectorstore import search_repository_code
from backend.rag.prompts import (
    CHAT_SYSTEM_PROMPT,
    FILE_EXPLAIN_SYSTEM_PROMPT,
    FUNCTION_EXPLAIN_SYSTEM_PROMPT
)

def get_llm():
    """Get the appropriate LangChain Chat Model based on environment variables."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if gemini_api_key:
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=gemini_api_key,
            temperature=0.2
        )
    elif openai_api_key:
        return ChatOpenAI(
            model="gpt-4-turbo",
            api_key=openai_api_key,
            temperature=0.2
        )
    else:
        # Fallback dummy class if no keys are found
        class MockLLM:
            def invoke(self, messages):
                class MockResponse:
                    content = "Mock Mode: Please set GEMINI_API_KEY or OPENAI_API_KEY in your environment to receive live AI responses."
                return MockResponse()
        return MockLLM()

def query_repository_chat(repository_id: int, query: str, chat_history: list[dict] = None) -> tuple[str, list[dict]]:
    """Query the codebase using RAG. Returns the AI response and sources used."""
    if chat_history is None:
        chat_history = []

    # 1. Retrieve relevant code snippets from ChromaDB
    retrieved_docs = search_repository_code(repository_id, query, k=5)
    
    # 2. Format the code context
    context_str = ""
    sources = []
    
    for doc in retrieved_docs:
        file_path = doc.metadata.get("file_path", "unknown_file")
        if file_path not in sources:
            sources.append(file_path)
            
        context_str += f"\n--- File: {file_path} ---\n{doc.page_content}\n"

    # 3. Build message list
    messages = [
        SystemMessage(content=CHAT_SYSTEM_PROMPT.format(context=context_str))
    ]
    
    # Add history
    for msg in chat_history[-6:]:  # Keep last 3 exchanges (6 messages) to fit context window
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
            
    # Add current query
    messages.append(HumanMessage(content=query))

    # 4. Invoke LLM
    llm = get_llm()
    try:
        response = llm.invoke(messages)
        ai_response = response.content
    except Exception as e:
        ai_response = f"Error generating response: {str(e)}"

    return ai_response, sources

def generate_file_explanation(file_content: str, file_path: str, language: str) -> str:
    """Generate a structured markdown explanation for a given file."""
    llm = get_llm()
    
    messages = [
        SystemMessage(content=FILE_EXPLAIN_SYSTEM_PROMPT),
        HumanMessage(content=f"Please analyze this file: {file_path}\nLanguage: {language}\n\nCode:\n```\n{file_content}\n```")
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        return f"Error explaining file: {str(e)}"

def generate_function_explanation(function_code: str, function_name: str, file_path: str) -> str:
    """Generate a detailed breakdown explanation for a specific function."""
    llm = get_llm()
    
    messages = [
        SystemMessage(content=FUNCTION_EXPLAIN_SYSTEM_PROMPT),
        HumanMessage(content=f"Function Name: {function_name}\nFile: {file_path}\n\nCode:\n```\n{function_code}\n```")
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        return f"Error explaining function: {str(e)}"
