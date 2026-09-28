"""Backward-compatible import for the old misspelled module name."""

from app.embedding import get_embedding

__all__ = ["get_embedding"]
