"""
Services module

Provides reusable services for agents:
- EmbeddingService: Generate embeddings for similarity detection
- VectorDatabase: Store and search embeddings
"""

from src.services.embedding_service import (
    EmbeddingService,
    EmbeddingResult,
    VoyageEmbeddingService,
    OpenAIEmbeddingService,
    CachedEmbeddingService
)

from src.services.vector_database import (
    VectorDatabase,
    SearchResult,
    ChromaDBDatabase
)

__all__ = [
    "EmbeddingService",
    "EmbeddingResult",
    "VoyageEmbeddingService",
    "OpenAIEmbeddingService",
    "CachedEmbeddingService",
    "VectorDatabase",
    "SearchResult",
    "ChromaDBDatabase",
]
