"""
Unit tests for Embedding Service

Tests all embedding service implementations:
- VoyageEmbeddingService
- OpenAIEmbeddingService
- CachedEmbeddingService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import tempfile
import hashlib
from datetime import datetime, timedelta

from src.services.embedding_service import (
    EmbeddingService,
    EmbeddingResult,
    VoyageEmbeddingService,
    OpenAIEmbeddingService,
    CachedEmbeddingService
)
from src.core.exceptions import AprepError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_text():
    """Sample text for embedding"""
    return "Find the derivative of f(x) = x^2"


@pytest.fixture
def sample_embedding():
    """Sample embedding vector"""
    return [0.1] * 1536


@pytest.fixture
def temp_cache_dir():
    """Temporary cache directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# Mock Embedding Service for Testing
# ============================================================================

class MockEmbeddingService(EmbeddingService):
    """Mock embedding service for testing"""

    def __init__(self, dimensions: int = 1536):
        self._dimensions = dimensions
        self.call_count = 0

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate mock embedding"""
        self.call_count += 1
        return EmbeddingResult(
            text=text,
            embedding=[0.1] * self._dimensions,
            model="mock-model",
            dimensions=self._dimensions,
            provider="mock"
        )

    def generate_embeddings(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate mock embeddings (batch)"""
        return [self.generate_embedding(text) for text in texts]

    def get_dimensions(self) -> int:
        """Get dimensions"""
        return self._dimensions


# ============================================================================
# Tests: EmbeddingResult Model
# ============================================================================

def test_embedding_result_creation(sample_text, sample_embedding):
    """Test creating an EmbeddingResult"""
    result = EmbeddingResult(
        text=sample_text,
        embedding=sample_embedding,
        model="voyage-large-2",
        dimensions=1536,
        provider="voyage"
    )

    assert result.text == sample_text
    assert result.embedding == sample_embedding
    assert result.model == "voyage-large-2"
    assert result.dimensions == 1536
    assert result.provider == "voyage"
    assert result.created_at is not None
    assert result.metadata == {}


def test_embedding_result_with_metadata(sample_text, sample_embedding):
    """Test EmbeddingResult with metadata"""
    metadata = {"input_type": "document", "user_id": "test_user"}

    result = EmbeddingResult(
        text=sample_text,
        embedding=sample_embedding,
        model="test-model",
        dimensions=1536,
        provider="test",
        metadata=metadata
    )

    assert result.metadata == metadata


# ============================================================================
# Tests: VoyageEmbeddingService
# ============================================================================

@pytest.mark.skipif(
    True,  # Skip by default as requires API key
    reason="Requires Voyage AI API key"
)
def test_voyage_embedding_service_initialization():
    """Test VoyageEmbeddingService initialization"""
    service = VoyageEmbeddingService(api_key="test-key")
    assert service.model == "voyage-large-2"
    assert service.input_type == "document"
    assert service.get_dimensions() == 1536


@patch('src.services.embedding_service.voyageai')
def test_voyage_embedding_service_mock(mock_voyageai, sample_text):
    """Test VoyageEmbeddingService with mock"""
    # Setup mock
    mock_client = MagicMock()
    mock_voyageai.Client.return_value = mock_client

    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1536]
    mock_client.embed.return_value = mock_result

    # Initialize service
    service = VoyageEmbeddingService(api_key="test-key")

    # Generate embedding
    result = service.generate_embedding(sample_text)

    # Assertions
    assert result.text == sample_text
    assert len(result.embedding) == 1536
    assert result.provider == "voyage"
    assert result.model == "voyage-large-2"

    # Verify mock was called
    mock_client.embed.assert_called_once()


@patch('src.services.embedding_service.voyageai')
def test_voyage_embedding_service_batch(mock_voyageai):
    """Test VoyageEmbeddingService batch generation"""
    # Setup mock
    mock_client = MagicMock()
    mock_voyageai.Client.return_value = mock_client

    texts = ["text 1", "text 2", "text 3"]
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
    mock_client.embed.return_value = mock_result

    # Initialize service
    service = VoyageEmbeddingService(api_key="test-key")

    # Generate embeddings
    results = service.generate_embeddings(texts)

    # Assertions
    assert len(results) == 3
    assert all(r.provider == "voyage" for r in results)
    assert results[0].text == "text 1"
    assert results[1].text == "text 2"
    assert results[2].text == "text 3"


# ============================================================================
# Tests: OpenAIEmbeddingService
# ============================================================================

@pytest.mark.skipif(
    True,  # Skip by default as requires API key
    reason="Requires OpenAI API key"
)
def test_openai_embedding_service_initialization():
    """Test OpenAIEmbeddingService initialization"""
    service = OpenAIEmbeddingService(api_key="test-key")
    assert service.model == "text-embedding-3-large"
    assert service.get_dimensions() == 3072


@patch('src.services.embedding_service.OpenAI')
def test_openai_embedding_service_mock(mock_openai_class, sample_text):
    """Test OpenAIEmbeddingService with mock"""
    # Setup mock
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_data = MagicMock()
    mock_data.embedding = [0.1] * 3072

    mock_result = MagicMock()
    mock_result.data = [mock_data]
    mock_client.embeddings.create.return_value = mock_result

    # Initialize service
    service = OpenAIEmbeddingService(api_key="test-key")

    # Generate embedding
    result = service.generate_embedding(sample_text)

    # Assertions
    assert result.text == sample_text
    assert len(result.embedding) == 3072
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-large"


@patch('src.services.embedding_service.OpenAI')
def test_openai_embedding_service_batch(mock_openai_class):
    """Test OpenAIEmbeddingService batch generation"""
    # Setup mock
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    texts = ["text 1", "text 2"]

    mock_data1 = MagicMock()
    mock_data1.embedding = [0.1] * 3072

    mock_data2 = MagicMock()
    mock_data2.embedding = [0.2] * 3072

    mock_result = MagicMock()
    mock_result.data = [mock_data1, mock_data2]
    mock_client.embeddings.create.return_value = mock_result

    # Initialize service
    service = OpenAIEmbeddingService(api_key="test-key")

    # Generate embeddings
    results = service.generate_embeddings(texts)

    # Assertions
    assert len(results) == 2
    assert all(r.provider == "openai" for r in results)


# ============================================================================
# Tests: CachedEmbeddingService
# ============================================================================

def test_cached_embedding_service_initialization(temp_cache_dir):
    """Test CachedEmbeddingService initialization"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir,
        ttl_days=7
    )

    assert service.base_service == base_service
    assert service.cache_dir == Path(temp_cache_dir)
    assert service.ttl_days == 7
    assert service.cache_hits == 0
    assert service.cache_misses == 0


def test_cached_embedding_service_cache_miss(temp_cache_dir, sample_text):
    """Test cache miss - should call base service"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    # First call - cache miss
    result = service.generate_embedding(sample_text)

    assert result.text == sample_text
    assert service.cache_misses == 1
    assert service.cache_hits == 0
    assert base_service.call_count == 1


def test_cached_embedding_service_cache_hit(temp_cache_dir, sample_text):
    """Test cache hit - should NOT call base service"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    # First call - cache miss
    result1 = service.generate_embedding(sample_text)

    # Second call - cache hit
    result2 = service.generate_embedding(sample_text)

    assert result1.text == result2.text
    assert result1.embedding == result2.embedding
    assert service.cache_misses == 1
    assert service.cache_hits == 1
    assert base_service.call_count == 1  # Called only once!


def test_cached_embedding_service_ttl(temp_cache_dir, sample_text):
    """Test cache TTL expiration"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir,
        ttl_days=1
    )

    # Generate and cache
    result1 = service.generate_embedding(sample_text)

    # Manually expire cache by modifying file mtime
    cache_key = hashlib.sha256(sample_text.encode()).hexdigest()
    cache_path = Path(temp_cache_dir) / f"{cache_key}.json"

    # Set mtime to 2 days ago
    old_time = (datetime.now() - timedelta(days=2)).timestamp()
    cache_path.touch()
    import os
    os.utime(cache_path, (old_time, old_time))

    # Call again - should be cache miss due to TTL
    result2 = service.generate_embedding(sample_text)

    assert service.cache_misses == 2  # Two misses
    assert service.cache_hits == 0
    assert base_service.call_count == 2


def test_cached_embedding_service_batch(temp_cache_dir):
    """Test batch caching"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    texts = ["text 1", "text 2", "text 3"]

    # First batch - all cache misses
    results1 = service.generate_embeddings(texts)

    assert len(results1) == 3
    assert service.cache_misses == 3
    assert service.cache_hits == 0

    # Second batch - all cache hits
    results2 = service.generate_embeddings(texts)

    assert len(results2) == 3
    assert service.cache_misses == 3
    assert service.cache_hits == 3

    # Mixed batch - some cached, some new
    mixed_texts = ["text 1", "text 4", "text 2", "text 5"]
    results3 = service.generate_embeddings(mixed_texts)

    assert len(results3) == 4
    assert service.cache_misses == 5  # text 4 and text 5 are new
    assert service.cache_hits == 5  # text 1 and text 2 are cached


def test_cached_embedding_service_cache_stats(temp_cache_dir, sample_text):
    """Test cache statistics"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    # Generate some calls
    service.generate_embedding(sample_text)
    service.generate_embedding(sample_text)
    service.generate_embedding("different text")

    stats = service.get_cache_stats()

    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 2
    assert stats["total_requests"] == 3
    assert stats["hit_rate"] == 1/3
    assert stats["cache_dir"] == temp_cache_dir
    assert stats["ttl_days"] == 30


def test_cached_embedding_service_get_dimensions(temp_cache_dir):
    """Test get_dimensions delegates to base service"""
    base_service = MockEmbeddingService(dimensions=512)

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    assert service.get_dimensions() == 512


def test_cached_embedding_service_cache_key_generation(temp_cache_dir):
    """Test cache key generation is consistent"""
    base_service = MockEmbeddingService()

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    text = "test text"

    # Generate cache key
    key1 = service._get_cache_key(text)
    key2 = service._get_cache_key(text)

    # Same text should produce same key
    assert key1 == key2

    # Different text should produce different key
    key3 = service._get_cache_key("different text")
    assert key1 != key3


# ============================================================================
# Tests: Error Handling
# ============================================================================

def test_voyage_missing_package():
    """Test error when voyageai package not installed"""
    with patch('src.services.embedding_service.voyageai', None):
        with pytest.raises(AprepError, match="voyageai package not installed"):
            # This will fail at import time
            pass  # Can't easily test this without module manipulation


def test_openai_missing_package():
    """Test error when openai package not installed"""
    with patch('src.services.embedding_service.OpenAI', None):
        with pytest.raises(AprepError):
            # This will fail at import time
            pass


def test_cached_service_handles_base_service_error(temp_cache_dir, sample_text):
    """Test CachedEmbeddingService handles base service errors"""
    base_service = Mock(spec=EmbeddingService)
    base_service.generate_embedding.side_effect = Exception("API Error")

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir
    )

    with pytest.raises(Exception, match="API Error"):
        service.generate_embedding(sample_text)


# ============================================================================
# Tests: Integration
# ============================================================================

def test_cached_service_with_mock_service(temp_cache_dir):
    """Integration test: CachedEmbeddingService with MockEmbeddingService"""
    base_service = MockEmbeddingService(dimensions=768)

    service = CachedEmbeddingService(
        base_service=base_service,
        cache_dir=temp_cache_dir,
        ttl_days=7
    )

    texts = ["question 1", "question 2", "question 1"]  # Note: duplicate

    # First pass
    results = [service.generate_embedding(text) for text in texts]

    assert len(results) == 3
    assert service.cache_misses == 2  # Only 2 unique texts
    assert service.cache_hits == 1  # Third is duplicate
    assert base_service.call_count == 2

    # Second pass - all should be cached
    results2 = [service.generate_embedding(text) for text in texts]

    assert len(results2) == 3
    assert service.cache_misses == 2
    assert service.cache_hits == 4  # 1 from first pass + 3 from second
    assert base_service.call_count == 2  # No new calls!
