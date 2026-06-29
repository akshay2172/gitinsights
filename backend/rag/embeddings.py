import os
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

def get_embeddings_model() -> Embeddings:
    """Initialize and return the appropriate LangChain Embeddings model.

    Priority order:
    1) Local HuggingFace (no API key required)
    2) Gemini
    3) OpenAI
    4) Mock embeddings (last-resort fallback for local dev)
    """

    # IMPORTANT: Use local embeddings first (no API keys required).
    # nomic v2 is a Mixture-of-Experts model that requires trust_remote_code=True.
    return HuggingFaceEmbeddings(
        model_name=os.getenv("HF_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        
    )

    # ---- Fallbacks (kept for optional use / older deployments) ----
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if gemini_api_key:
        # LangChain Google GenAI embeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=gemini_api_key,
        )
    elif openai_api_key:
        # LangChain OpenAI embeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=openai_api_key,
        )
    else:
        # Fallback to dummy mock embeddings for local test if key is absent (to avoid hard crash)
        class MockEmbeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 768 for _ in texts]

            def embed_query(self, text: str) -> list[float]:
                return [0.1] * 768

        return MockEmbeddings()

