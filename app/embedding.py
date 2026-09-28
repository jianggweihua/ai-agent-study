from functools import lru_cache

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Use the local model cache first; only download on the first run."""
    try:
        return SentenceTransformer(MODEL_NAME, local_files_only=True)
    except OSError:
        return SentenceTransformer(MODEL_NAME)


def get_embedding(text: str) -> list[float]:
    """Encode text with all-MiniLM-L6-v2 and return a plain Python list."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must not be empty")

    vector = _load_model().encode(text, normalize_embeddings=True, show_progress_bar=False)
    return [float(value) for value in vector]
