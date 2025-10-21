"""
Vector Database Service - Abstract interface and implementations

Provides vector storage and similarity search for plagiarism detection:
- ChromaDB (primary, local/cloud)
- Pinecone (future, managed cloud)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError

logger = setup_logger(__name__)


class SearchResult(BaseModel):
    """Result of vector similarity search"""

    id: str = Field(..., description="Document ID")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity")

    text: str = Field(..., description="Matched text")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorDatabase(ABC):
    """Abstract base class for vector databases"""

    @abstractmethod
    def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add documents with embeddings to database"""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for similar vectors"""
        pass

    @abstractmethod
    def delete_documents(self, ids: List[str]) -> None:
        """Delete documents by IDs"""
        pass

    @abstractmethod
    def get_document_count(self) -> int:
        """Get total number of documents"""
        pass

    @abstractmethod
    def clear_collection(self) -> None:
        """Clear all documents from collection"""
        pass


class ChromaDBDatabase(VectorDatabase):
    """
    ChromaDB vector database implementation.

    Supports both local (persistent) and in-memory modes.
    """

    def __init__(
        self,
        collection_name: str = "questions",
        persist_directory: Optional[str] = "data/chromadb",
        distance_metric: str = "cosine"
    ):
        """
        Initialize ChromaDB database.

        Args:
            collection_name: Name of the collection
            persist_directory: Directory for persistent storage (None for in-memory)
            distance_metric: Distance metric (cosine, l2, ip)
        """
        try:
            import chromadb
            from chromadb.config import Settings

            # Create client
            if persist_directory:
                persist_path = Path(persist_directory)
                persist_path.mkdir(parents=True, exist_ok=True)

                self.client = chromadb.PersistentClient(
                    path=str(persist_path),
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info(f"Initialized ChromaDB with persistent storage: {persist_path}")
            else:
                self.client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info("Initialized ChromaDB with in-memory storage")

            # Get or create collection
            self.collection_name = collection_name
            self.distance_metric = distance_metric

            # Map our distance metric to ChromaDB's space
            space_map = {
                "cosine": "cosine",
                "l2": "l2",
                "ip": "ip"  # inner product
            }

            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": space_map.get(distance_metric, "cosine")}
            )

            logger.info(
                f"ChromaDB collection '{collection_name}' ready "
                f"(documents: {self.collection.count()}, metric: {distance_metric})"
            )

        except ImportError:
            raise AprepError("chromadb package not installed. Run: pip install chromadb")
        except Exception as e:
            raise AprepError(f"Failed to initialize ChromaDB: {e}")

    def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add documents with embeddings to database"""
        try:
            if not ids or not embeddings or not texts:
                raise ValueError("ids, embeddings, and texts cannot be empty")

            if len(ids) != len(embeddings) != len(texts):
                raise ValueError("ids, embeddings, and texts must have same length")

            # Add timestamp to metadata
            if metadatas is None:
                metadatas = [{}] * len(ids)

            for metadata in metadatas:
                if "added_at" not in metadata:
                    metadata["added_at"] = datetime.now().isoformat()

            # Add to ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

            logger.info(f"Added {len(ids)} documents to ChromaDB collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
            raise AprepError(f"Failed to add documents: {e}")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for similar vectors.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"source_type": "ap_released"})

        Returns:
            List of SearchResult objects
        """
        try:
            # Build where clause for filtering
            where_clause = filter_metadata if filter_metadata else None

            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )

            # Convert to SearchResult objects
            search_results = []

            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    # ChromaDB returns distances, convert to similarity
                    # For cosine: similarity = 1 - distance (distance is in [0, 2])
                    # For L2: we approximate similarity
                    distance = results["distances"][0][i]

                    if self.distance_metric == "cosine":
                        similarity = 1.0 - (distance / 2.0)  # Normalize to [0, 1]
                    elif self.distance_metric == "l2":
                        # Simple exponential decay for L2
                        similarity = 1.0 / (1.0 + distance)
                    else:  # ip (inner product)
                        similarity = max(0.0, min(1.0, distance))  # Clamp to [0, 1]

                    search_results.append(SearchResult(
                        id=results["ids"][0][i],
                        similarity=round(similarity, 4),
                        text=results["documents"][0][i],
                        metadata=results["metadatas"][0][i] or {}
                    ))

            logger.debug(f"Found {len(search_results)} similar documents")
            return search_results

        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            raise AprepError(f"Failed to search vectors: {e}")

    def delete_documents(self, ids: List[str]) -> None:
        """Delete documents by IDs"""
        try:
            if not ids:
                return

            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents from ChromaDB")

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise AprepError(f"Failed to delete documents: {e}")

    def get_document_count(self) -> int:
        """Get total number of documents"""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0

    def clear_collection(self) -> None:
        """Clear all documents from collection"""
        try:
            # Delete collection and recreate
            self.client.delete_collection(name=self.collection_name)

            space_map = {
                "cosine": "cosine",
                "l2": "l2",
                "ip": "ip"
            }

            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": space_map.get(self.distance_metric, "cosine")}
            )

            logger.info(f"Cleared ChromaDB collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise AprepError(f"Failed to clear collection: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            "collection_name": self.collection_name,
            "document_count": self.get_document_count(),
            "distance_metric": self.distance_metric
        }

    def update_document_metadata(
        self,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Update metadata for a document.

        Args:
            document_id: Document ID
            metadata: New metadata
        """
        try:
            self.collection.update(
                ids=[document_id],
                metadatas=[metadata]
            )

            logger.debug(f"Updated metadata for document {document_id}")

        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")
            raise AprepError(f"Failed to update metadata: {e}")

    def get_document(self, document_id: str) -> Optional[SearchResult]:
        """
        Get a document by ID.

        Args:
            document_id: Document ID

        Returns:
            SearchResult if found, None otherwise
        """
        try:
            result = self.collection.get(
                ids=[document_id],
                include=["documents", "metadatas"]
            )

            if result["ids"]:
                return SearchResult(
                    id=result["ids"][0],
                    similarity=1.0,  # Exact match
                    text=result["documents"][0],
                    metadata=result["metadatas"][0] or {}
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None
