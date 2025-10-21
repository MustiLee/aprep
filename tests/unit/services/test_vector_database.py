"""
Unit tests for Vector Database Service

Tests ChromaDB vector database implementation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

from src.services.vector_database import (
    VectorDatabase,
    SearchResult,
    ChromaDBDatabase
)
from src.core.exceptions import AprepError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_dir():
    """Temporary database directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors"""
    return [
        [0.1, 0.2, 0.3, 0.4, 0.5],  # 5-dimensional for testing
        [0.2, 0.3, 0.4, 0.5, 0.6],
        [0.9, 0.8, 0.7, 0.6, 0.5]
    ]


@pytest.fixture
def sample_texts():
    """Sample texts"""
    return [
        "Find the derivative of x^2",
        "Calculate the integral of 2x",
        "What is the limit as x approaches 0?"
    ]


@pytest.fixture
def sample_metadata():
    """Sample metadata"""
    return [
        {"source_type": "internal", "difficulty": "easy"},
        {"source_type": "textbook", "difficulty": "medium"},
        {"source_type": "ap_released_exam", "difficulty": "hard"}
    ]


# ============================================================================
# Tests: SearchResult Model
# ============================================================================

def test_search_result_creation():
    """Test creating a SearchResult"""
    result = SearchResult(
        id="q_001",
        similarity=0.95,
        text="Find the derivative",
        metadata={"source": "internal"}
    )

    assert result.id == "q_001"
    assert result.similarity == 0.95
    assert result.text == "Find the derivative"
    assert result.metadata == {"source": "internal"}


def test_search_result_similarity_bounds():
    """Test similarity is bounded [0, 1]"""
    # Valid similarities
    SearchResult(id="q1", similarity=0.0, text="text")
    SearchResult(id="q2", similarity=1.0, text="text")
    SearchResult(id="q3", similarity=0.5, text="text")

    # Invalid similarities should fail validation
    with pytest.raises(Exception):  # Pydantic validation error
        SearchResult(id="q4", similarity=1.5, text="text")

    with pytest.raises(Exception):
        SearchResult(id="q5", similarity=-0.1, text="text")


# ============================================================================
# Tests: ChromaDBDatabase Initialization
# ============================================================================

def test_chromadb_initialization_in_memory():
    """Test ChromaDB initialization in memory mode"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=None  # In-memory
    )

    assert db.collection_name == "test_questions"
    assert db.distance_metric == "cosine"
    assert db.get_document_count() == 0


def test_chromadb_initialization_persistent(temp_db_dir):
    """Test ChromaDB initialization with persistence"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    assert db.collection_name == "test_questions"
    assert Path(temp_db_dir).exists()
    assert db.get_document_count() == 0


def test_chromadb_initialization_with_distance_metric(temp_db_dir):
    """Test ChromaDB with different distance metrics"""
    # Cosine
    db_cosine = ChromaDBDatabase(
        collection_name="test_cosine",
        persist_directory=temp_db_dir,
        distance_metric="cosine"
    )
    assert db_cosine.distance_metric == "cosine"

    # L2
    db_l2 = ChromaDBDatabase(
        collection_name="test_l2",
        persist_directory=temp_db_dir,
        distance_metric="l2"
    )
    assert db_l2.distance_metric == "l2"

    # Inner Product
    db_ip = ChromaDBDatabase(
        collection_name="test_ip",
        persist_directory=temp_db_dir,
        distance_metric="ip"
    )
    assert db_ip.distance_metric == "ip"


# ============================================================================
# Tests: Add Documents
# ============================================================================

def test_add_documents(temp_db_dir, sample_embeddings, sample_texts):
    """Test adding documents to database"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    ids = ["q1", "q2", "q3"]

    db.add_documents(
        ids=ids,
        embeddings=sample_embeddings,
        texts=sample_texts
    )

    assert db.get_document_count() == 3


def test_add_documents_with_metadata(
    temp_db_dir,
    sample_embeddings,
    sample_texts,
    sample_metadata
):
    """Test adding documents with metadata"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    ids = ["q1", "q2", "q3"]

    db.add_documents(
        ids=ids,
        embeddings=sample_embeddings,
        texts=sample_texts,
        metadatas=sample_metadata
    )

    assert db.get_document_count() == 3

    # Verify metadata was stored (check via get_document)
    doc = db.get_document("q1")
    assert doc is not None
    assert doc.metadata["source_type"] == "internal"
    assert "added_at" in doc.metadata  # Auto-added timestamp


def test_add_documents_empty_lists(temp_db_dir):
    """Test error when adding empty lists"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    with pytest.raises(AprepError, match="cannot be empty"):
        db.add_documents(ids=[], embeddings=[], texts=[])


def test_add_documents_mismatched_lengths(temp_db_dir):
    """Test error when lists have mismatched lengths"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    with pytest.raises(AprepError, match="same length"):
        db.add_documents(
            ids=["q1", "q2"],
            embeddings=[[0.1, 0.2]],  # Only 1 embedding
            texts=["text1", "text2"]
        )


# ============================================================================
# Tests: Search
# ============================================================================

def test_search_basic(temp_db_dir, sample_embeddings, sample_texts):
    """Test basic similarity search"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents
    ids = ["q1", "q2", "q3"]
    db.add_documents(ids=ids, embeddings=sample_embeddings, texts=sample_texts)

    # Search with first embedding (should find itself)
    query_embedding = sample_embeddings[0]
    results = db.search(query_embedding=query_embedding, top_k=3)

    assert len(results) <= 3
    assert all(isinstance(r, SearchResult) for r in results)

    # First result should be the same document (highest similarity)
    if results:
        assert results[0].id == "q1"
        assert results[0].similarity > 0.9  # Should be very similar to itself


def test_search_with_top_k(temp_db_dir, sample_embeddings, sample_texts):
    """Test search with different top_k values"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents
    ids = ["q1", "q2", "q3", "q4", "q5"]
    embeddings = sample_embeddings + [
        [0.3, 0.4, 0.5, 0.6, 0.7],
        [0.4, 0.5, 0.6, 0.7, 0.8]
    ]
    texts = sample_texts + ["text4", "text5"]

    db.add_documents(ids=ids, embeddings=embeddings, texts=texts)

    # Search with top_k=2
    query_embedding = embeddings[0]
    results = db.search(query_embedding=query_embedding, top_k=2)

    assert len(results) <= 2


def test_search_with_metadata_filter(
    temp_db_dir,
    sample_embeddings,
    sample_texts,
    sample_metadata
):
    """Test search with metadata filtering"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents with metadata
    ids = ["q1", "q2", "q3"]
    db.add_documents(
        ids=ids,
        embeddings=sample_embeddings,
        texts=sample_texts,
        metadatas=sample_metadata
    )

    # Search with filter for source_type
    query_embedding = sample_embeddings[0]
    results = db.search(
        query_embedding=query_embedding,
        top_k=10,
        filter_metadata={"source_type": "internal"}
    )

    # Should only return documents with source_type=internal
    assert len(results) >= 1
    for result in results:
        assert result.metadata.get("source_type") == "internal"


def test_search_empty_database(temp_db_dir):
    """Test search in empty database"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    results = db.search(query_embedding=query_embedding, top_k=5)

    assert results == []


# ============================================================================
# Tests: Delete Documents
# ============================================================================

def test_delete_documents(temp_db_dir, sample_embeddings, sample_texts):
    """Test deleting documents"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents
    ids = ["q1", "q2", "q3"]
    db.add_documents(ids=ids, embeddings=sample_embeddings, texts=sample_texts)

    assert db.get_document_count() == 3

    # Delete one document
    db.delete_documents(ids=["q2"])

    assert db.get_document_count() == 2

    # Verify q2 is gone
    doc = db.get_document("q2")
    assert doc is None


def test_delete_multiple_documents(temp_db_dir, sample_embeddings, sample_texts):
    """Test deleting multiple documents"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents
    ids = ["q1", "q2", "q3"]
    db.add_documents(ids=ids, embeddings=sample_embeddings, texts=sample_texts)

    # Delete multiple
    db.delete_documents(ids=["q1", "q3"])

    assert db.get_document_count() == 1

    # Verify only q2 remains
    assert db.get_document("q2") is not None
    assert db.get_document("q1") is None
    assert db.get_document("q3") is None


def test_delete_empty_list(temp_db_dir):
    """Test deleting with empty list (should do nothing)"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Should not raise error
    db.delete_documents(ids=[])


# ============================================================================
# Tests: Get Document
# ============================================================================

def test_get_document(temp_db_dir, sample_embeddings, sample_texts):
    """Test getting a document by ID"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents
    ids = ["q1", "q2", "q3"]
    db.add_documents(ids=ids, embeddings=sample_embeddings, texts=sample_texts)

    # Get document
    doc = db.get_document("q2")

    assert doc is not None
    assert doc.id == "q2"
    assert doc.text == sample_texts[1]
    assert doc.similarity == 1.0  # Exact match


def test_get_nonexistent_document(temp_db_dir):
    """Test getting a document that doesn't exist"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    doc = db.get_document("nonexistent_id")
    assert doc is None


# ============================================================================
# Tests: Clear Collection
# ============================================================================

def test_clear_collection(temp_db_dir, sample_embeddings, sample_texts):
    """Test clearing all documents from collection"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add documents
    ids = ["q1", "q2", "q3"]
    db.add_documents(ids=ids, embeddings=sample_embeddings, texts=sample_texts)

    assert db.get_document_count() == 3

    # Clear
    db.clear_collection()

    assert db.get_document_count() == 0


# ============================================================================
# Tests: Update Metadata
# ============================================================================

def test_update_document_metadata(temp_db_dir, sample_embeddings, sample_texts):
    """Test updating document metadata"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Add document
    db.add_documents(
        ids=["q1"],
        embeddings=[sample_embeddings[0]],
        texts=[sample_texts[0]],
        metadatas=[{"status": "draft"}]
    )

    # Update metadata
    db.update_document_metadata(
        document_id="q1",
        metadata={"status": "published", "version": 2}
    )

    # Verify update
    doc = db.get_document("q1")
    assert doc.metadata["status"] == "published"
    assert doc.metadata["version"] == 2


# ============================================================================
# Tests: Statistics
# ============================================================================

def test_get_statistics(temp_db_dir, sample_embeddings, sample_texts):
    """Test getting database statistics"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir,
        distance_metric="cosine"
    )

    # Add documents
    ids = ["q1", "q2", "q3"]
    db.add_documents(ids=ids, embeddings=sample_embeddings, texts=sample_texts)

    stats = db.get_statistics()

    assert stats["collection_name"] == "test_questions"
    assert stats["document_count"] == 3
    assert stats["distance_metric"] == "cosine"


# ============================================================================
# Tests: Persistence
# ============================================================================

def test_persistence(temp_db_dir, sample_embeddings, sample_texts):
    """Test that data persists across instances"""
    collection_name = "persistent_test"

    # Create first instance and add data
    db1 = ChromaDBDatabase(
        collection_name=collection_name,
        persist_directory=temp_db_dir
    )

    ids = ["q1", "q2"]
    db1.add_documents(
        ids=ids,
        embeddings=sample_embeddings[:2],
        texts=sample_texts[:2]
    )

    assert db1.get_document_count() == 2

    # Create second instance (should load persisted data)
    db2 = ChromaDBDatabase(
        collection_name=collection_name,
        persist_directory=temp_db_dir
    )

    assert db2.get_document_count() == 2

    # Verify data is accessible
    doc = db2.get_document("q1")
    assert doc is not None
    assert doc.text == sample_texts[0]


# ============================================================================
# Tests: Error Handling
# ============================================================================

def test_chromadb_missing_package():
    """Test error when chromadb package not installed"""
    with patch('src.services.vector_database.chromadb', None):
        with pytest.raises(AprepError, match="chromadb package not installed"):
            # This would fail at import
            pass


def test_add_documents_with_invalid_data(temp_db_dir):
    """Test error handling for invalid data"""
    db = ChromaDBDatabase(
        collection_name="test_questions",
        persist_directory=temp_db_dir
    )

    # Try adding with invalid types
    with pytest.raises(AprepError):
        db.add_documents(
            ids=["q1"],
            embeddings=["not_a_list"],  # Invalid
            texts=["text"]
        )


# ============================================================================
# Tests: Different Distance Metrics
# ============================================================================

def test_cosine_similarity(temp_db_dir):
    """Test cosine similarity metric"""
    db = ChromaDBDatabase(
        collection_name="test_cosine",
        persist_directory=temp_db_dir,
        distance_metric="cosine"
    )

    # Add orthogonal vectors
    db.add_documents(
        ids=["v1", "v2"],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        texts=["vec1", "vec2"]
    )

    # Search with v1
    results = db.search(query_embedding=[1.0, 0.0], top_k=2)

    # v1 should be first (highest similarity to itself)
    assert results[0].id == "v1"


def test_l2_similarity(temp_db_dir):
    """Test L2 distance metric"""
    db = ChromaDBDatabase(
        collection_name="test_l2",
        persist_directory=temp_db_dir,
        distance_metric="l2"
    )

    # Add vectors
    db.add_documents(
        ids=["v1", "v2", "v3"],
        embeddings=[
            [0.0, 0.0],
            [1.0, 0.0],
            [10.0, 0.0]
        ],
        texts=["origin", "close", "far"]
    )

    # Search near origin
    results = db.search(query_embedding=[0.1, 0.0], top_k=3)

    # Should find origin first (smallest L2 distance)
    assert results[0].id == "v1"
