import os
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

_embedding_model: Embeddings | None = None


def get_embeddings_model() -> Embeddings:
    """Return a cached (singleton) LangChain embeddings model.

    The HuggingFaceEmbeddings model load is expensive, so we ensure the
    embedding model is instantiated only once per process.

    Priority order:
    1) Local HuggingFace (no API key required)
    2) Gemini
    3) OpenAI
    4) Mock embeddings (last-resort fallback for local dev)
    """

    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    # ---- Preferred: local HuggingFace embeddings ----
    model_name = os.getenv("HF_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    print("Loading embedding model...")
    device = os.getenv("EMBEDDING_DEVICE", "cpu")
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    _embedding_model = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
    )

    # ---- Optional remote fallbacks ----
    # These are only used if HF init failed for some reason.
    # (In the current code path, HuggingFace is preferred and should not be overridden.)
    if _embedding_model is None:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if gemini_api_key:
            _embedding_model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=gemini_api_key,
            )
        elif openai_api_key:
            _embedding_model = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=openai_api_key,
            )

    # If neither env keys are set and HF init somehow fails, last-resort mock.
    if _embedding_model is None:

        class MockEmbeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 768 for _ in texts]

            def embed_query(self, text: str) -> list[float]:
                return [0.1] * 768

        _embedding_model = MockEmbeddings()

    return _embedding_model
