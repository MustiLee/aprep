"""
Embedding Service - Abstract interface and implementations

Provides embedding generation for plagiarism detection using multiple providers:
- Voyage AI (primary, optimized for education)
- OpenAI (fallback)
- Caching layer for cost optimization
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError

logger = setup_logger(__name__)


class EmbeddingResult(BaseModel):
    """Result of embedding generation"""

    text: str = Field(..., description="Original text")
    embedding: List[float] = Field(..., description="Embedding vector")
    model: str = Field(..., description="Model used for embedding")
    dimensions: int = Field(..., description="Embedding dimensions")
    provider: str = Field(..., description="Provider (voyage, openai, etc)")

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingService(ABC):
    """Abstract base class for embedding services"""

    @abstractmethod
    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text"""
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts (batch)"""
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """Get embedding dimensions"""
        pass


class VoyageEmbeddingService(EmbeddingService):
    """Voyage AI embedding service - optimized for education domain"""

    def __init__(
        self,
        api_key: str,
        model: str = "voyage-large-2",
        input_type: str = "document"
    ):
        """
        Initialize Voyage AI embedding service.

        Args:
            api_key: Voyage AI API key
            model: Model name (voyage-large-2, voyage-code-2, etc)
            input_type: document or query
        """
        try:
            import voyageai
            self.client = voyageai.Client(api_key=api_key)
            self.model = model
            self.input_type = input_type
            self._dimensions = 1536 if "large" in model else 1024

            logger.info(f"Initialized VoyageEmbeddingService with model {model}")
        except ImportError:
            raise AprepError("voyageai package not installed. Run: pip install voyageai")
        except Exception as e:
            raise AprepError(f"Failed to initialize Voyage AI client: {e}")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text"""
        try:
            result = self.client.embed(
                texts=[text],
                model=self.model,
                input_type=self.input_type
            )

            return EmbeddingResult(
                text=text,
                embedding=result.embeddings[0],
                model=self.model,
                dimensions=len(result.embeddings[0]),
                provider="voyage",
                metadata={"input_type": self.input_type}
            )
        except Exception as e:
            logger.error(f"Voyage AI embedding failed: {e}")
            raise AprepError(f"Failed to generate Voyage embedding: {e}")

    def generate_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts"""
        try:
            # Voyage AI supports batch embedding
            result = self.client.embed(
                texts=texts,
                model=self.model,
                input_type=self.input_type
            )

            return [
                EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    model=self.model,
                    dimensions=len(embedding),
                    provider="voyage",
                    metadata={"input_type": self.input_type}
                )
                for text, embedding in zip(texts, result.embeddings)
            ]
        except Exception as e:
            logger.error(f"Voyage AI batch embedding failed: {e}")
            raise AprepError(f"Failed to generate Voyage batch embeddings: {e}")

    def get_dimensions(self) -> int:
        """Get embedding dimensions"""
        return self._dimensions


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embedding service - fallback option"""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large"
    ):
        """
        Initialize OpenAI embedding service.

        Args:
            api_key: OpenAI API key
            model: Model name (text-embedding-3-large, text-embedding-3-small)
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
            self._dimensions = 3072 if "large" in model else 1536

            logger.info(f"Initialized OpenAIEmbeddingService with model {model}")
        except ImportError:
            raise AprepError("openai package not installed. Run: pip install openai")
        except Exception as e:
            raise AprepError(f"Failed to initialize OpenAI client: {e}")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text"""
        try:
            result = self.client.embeddings.create(
                input=[text],
                model=self.model
            )

            return EmbeddingResult(
                text=text,
                embedding=result.data[0].embedding,
                model=self.model,
                dimensions=len(result.data[0].embedding),
                provider="openai"
            )
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise AprepError(f"Failed to generate OpenAI embedding: {e}")

    def generate_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts"""
        try:
            result = self.client.embeddings.create(
                input=texts,
                model=self.model
            )

            return [
                EmbeddingResult(
                    text=text,
                    embedding=data.embedding,
                    model=self.model,
                    dimensions=len(data.embedding),
                    provider="openai"
                )
                for text, data in zip(texts, result.data)
            ]
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            raise AprepError(f"Failed to generate OpenAI batch embeddings: {e}")

    def get_dimensions(self) -> int:
        """Get embedding dimensions"""
        return self._dimensions


class CachedEmbeddingService(EmbeddingService):
    """
    Caching wrapper for embedding services.

    Caches embeddings to disk to avoid regenerating for same text.
    """

    def __init__(
        self,
        base_service: EmbeddingService,
        cache_dir: str = "data/embedding_cache",
        ttl_days: int = 30
    ):
        """
        Initialize cached embedding service.

        Args:
            base_service: Underlying embedding service
            cache_dir: Directory for cache files
            ttl_days: Time-to-live for cached embeddings
        """
        self.base_service = base_service
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days

        self.cache_hits = 0
        self.cache_misses = 0

        logger.info(f"Initialized CachedEmbeddingService (cache_dir={cache_dir}, ttl={ttl_days}d)")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text"""
        return hashlib.sha256(text.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid (within TTL)"""
        if not cache_path.exists():
            return False

        # Check TTL
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime

        return age < timedelta(days=self.ttl_days)

    def _read_cache(self, cache_key: str) -> Optional[EmbeddingResult]:
        """Read embedding from cache"""
        cache_path = self._get_cache_path(cache_key)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            return EmbeddingResult(**data)
        except Exception as e:
            logger.warning(f"Failed to read cache: {e}")
            return None

    def _write_cache(self, cache_key: str, result: EmbeddingResult) -> None:
        """Write embedding to cache"""
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, 'w') as f:
                json.dump(result.model_dump(), f)
        except Exception as e:
            logger.warning(f"Failed to write cache: {e}")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding with caching"""
        cache_key = self._get_cache_key(text)

        # Try cache first
        cached = self._read_cache(cache_key)
        if cached:
            self.cache_hits += 1
            logger.debug(f"Cache hit for text (key={cache_key[:8]}...)")
            return cached

        # Cache miss - generate new embedding
        self.cache_misses += 1
        logger.debug(f"Cache miss for text (key={cache_key[:8]}...)")

        result = self.base_service.generate_embedding(text)

        # Write to cache
        self._write_cache(cache_key, result)

        return result

    def generate_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings with caching (batch)"""
        results = []
        uncached_texts = []
        uncached_indices = []

        # Check cache for each text
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached = self._read_cache(cache_key)

            if cached:
                self.cache_hits += 1
                results.append((i, cached))
            else:
                self.cache_misses += 1
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Generate embeddings for uncached texts
        if uncached_texts:
            new_results = self.base_service.generate_embeddings(uncached_texts)

            # Cache new results
            for text, result in zip(uncached_texts, new_results):
                cache_key = self._get_cache_key(text)
                self._write_cache(cache_key, result)

            # Add to results
            for idx, result in zip(uncached_indices, new_results):
                results.append((idx, result))

        # Sort by original index and return
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def get_dimensions(self) -> int:
        """Get embedding dimensions"""
        return self.base_service.get_dimensions()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0.0

        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total,
            "hit_rate": hit_rate,
            "cache_dir": str(self.cache_dir),
            "ttl_days": self.ttl_days
        }
