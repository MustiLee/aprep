"""
Unit tests for Plagiarism Detector V2 - Part 1

Tests Phase 1 (Exact Match) and Phase 2 (Semantic Similarity)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.agents.plagiarism_detector_v2 import (
    PlagiarismDetectorV2,
    ExactMatchDetector,
    StructuralAnalyzer,
    SourceSpecificChecker,
    RiskAssessor,
    RiskLevel,
    MatchType,
    SourceType,
    PlagiarismStatus,
    MatchAnalysis,
    SimilarityMatch,
    RiskAssessment,
    Evidence,
    PlagiarismReportV2
)
from src.services.embedding_service import EmbeddingService, EmbeddingResult
from src.services.vector_database import VectorDatabase, SearchResult


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_content():
    """Sample question content"""
    return {
        "stimulus": "Find the derivative of f(x) = x^2",
        "options": ["2x", "x", "x^2", "2"]
    }


@pytest.fixture
def sample_content_similar():
    """Similar question content"""
    return {
        "stimulus": "Find the derivative of g(x) = x squared",
        "options": ["2x", "x", "2", "x^2"]
    }


@pytest.fixture
def sample_content_different():
    """Different question content"""
    return {
        "stimulus": "Evaluate the integral of 2x dx",
        "options": ["x^2 + C", "2x + C", "x + C", "2"]
    }


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service"""
    service = Mock(spec=EmbeddingService)

    def generate_embedding(text):
        # Simple deterministic embedding based on text length
        length = len(text)
        return EmbeddingResult(
            text=text,
            embedding=[float(length % 10 * 0.1)] * 1536,
            model="mock-model",
            dimensions=1536,
            provider="mock"
        )

    service.generate_embedding.side_effect = generate_embedding
    service.get_dimensions.return_value = 1536

    return service


@pytest.fixture
def mock_vector_database():
    """Mock vector database"""
    db = Mock(spec=VectorDatabase)
    db.get_document_count.return_value = 0
    db.search.return_value = []
    return db


# ============================================================================
# Tests: Phase 1 - ExactMatchDetector
# ============================================================================

def test_exact_match_detector_initialization():
    """Test ExactMatchDetector initialization"""
    detector = ExactMatchDetector()

    assert detector.hash_index == {}


def test_exact_match_detector_add_to_index():
    """Test adding questions to hash index"""
    detector = ExactMatchDetector()

    question_id = "q_001"
    text = "Find the derivative of x^2"

    detector.add_to_index(question_id, text)

    assert len(detector.hash_index) == 1


def test_exact_match_detector_normalize_text():
    """Test text normalization"""
    detector = ExactMatchDetector()

    # Test lowercase
    assert "hello" in detector._normalize_text("HELLO")

    # Test whitespace removal
    normalized = detector._normalize_text("hello    world")
    assert "hello world" in normalized

    # Test math notation normalization
    normalized = detector._normalize_text("x²")
    assert "x^2" in normalized.lower() or "x2" in normalized


def test_exact_match_detector_exact_match_found():
    """Test detecting exact match"""
    detector = ExactMatchDetector()

    text1 = "Find the derivative of x^2"
    text2 = "Find the derivative of x^2"  # Exact match

    detector.add_to_index("q_001", text1)

    database_texts = {"q_001": text1}

    result = detector.check_exact_matches(text2, database_texts)

    assert result["found"] == True
    assert len(result["matches"]) > 0


def test_exact_match_detector_no_exact_match():
    """Test when no exact match exists"""
    detector = ExactMatchDetector()

    text1 = "Find the derivative of x^2"
    text2 = "Calculate the integral of 2x"  # Different

    detector.add_to_index("q_001", text1)

    database_texts = {"q_001": text1}

    result = detector.check_exact_matches(text2, database_texts)

    assert result["found"] == False


@pytest.mark.skipif(
    True,  # Skip if python-Levenshtein not installed
    reason="Requires python-Levenshtein package"
)
def test_exact_match_detector_fuzzy_match():
    """Test fuzzy matching with Levenshtein distance"""
    detector = ExactMatchDetector()

    text1 = "Find the derivative of x^2"
    text2 = "Find the derivative of x2"  # Very similar

    database_texts = {"q_001": text1}

    result = detector.check_exact_matches(text2, database_texts, fuzzy_threshold=0.90)

    # Should find fuzzy match
    assert result["found"] == True
    assert result["matches"][0]["match_type"] == "fuzzy"


def test_exact_match_detector_empty_database():
    """Test with empty database"""
    detector = ExactMatchDetector()

    result = detector.check_exact_matches("some text", {})

    assert result["found"] == False
    assert result["matches"] == []


# ============================================================================
# Tests: Pydantic Models
# ============================================================================

def test_match_analysis_creation():
    """Test MatchAnalysis model"""
    analysis = MatchAnalysis(
        matching_elements=["derivative_concept", "polynomial_function"],
        different_elements=["coefficient_value"],
        conclusion="MODERATE SIMILARITY",
        confidence=0.75
    )

    assert len(analysis.matching_elements) == 2
    assert len(analysis.different_elements) == 1
    assert analysis.confidence == 0.75


def test_similarity_match_creation():
    """Test SimilarityMatch model"""
    analysis = MatchAnalysis(
        matching_elements=["concept"],
        different_elements=["value"],
        conclusion="Similar",
        confidence=0.8
    )

    match = SimilarityMatch(
        source_id="q_001",
        source_type=SourceType.INTERNAL,
        similarity_score=0.85,
        similarity_type=MatchType.SEMANTIC,
        matched_content="Find derivative of x^3",
        analysis=analysis
    )

    assert match.source_id == "q_001"
    assert match.source_type == SourceType.INTERNAL
    assert match.similarity_score == 0.85
    assert match.similarity_type == MatchType.SEMANTIC


def test_risk_assessment_creation():
    """Test RiskAssessment model"""
    risk = RiskAssessment(
        copyright_risk=RiskLevel.LOW,
        originality_score=0.85,
        recommendation="APPROVE",
        requires_review=False,
        legal_review_required=False
    )

    assert risk.copyright_risk == RiskLevel.LOW
    assert risk.originality_score == 0.85
    assert risk.recommendation == "APPROVE"


def test_evidence_creation():
    """Test Evidence model"""
    evidence = Evidence(
        unique_elements=["specific coefficient 2"],
        common_elements=["derivative calculation"]
    )

    assert len(evidence.unique_elements) == 1
    assert len(evidence.common_elements) == 1


def test_plagiarism_report_v2_creation():
    """Test PlagiarismReportV2 model"""
    risk = RiskAssessment(
        copyright_risk=RiskLevel.NEGLIGIBLE,
        originality_score=0.90,
        recommendation="APPROVE",
        requires_review=False,
        legal_review_required=False
    )

    report = PlagiarismReportV2(
        check_id="plg_test_001",
        content_id="q_new_001",
        overall_assessment={
            "status": "ORIGINAL",
            "max_similarity": 0.45,
            "pass": True,
            "confidence": 0.94
        },
        risk_assessment=risk
    )

    assert report.check_id == "plg_test_001"
    assert report.content_id == "q_new_001"
    assert report.overall_assessment["status"] == "ORIGINAL"
    assert report.risk_assessment.recommendation == "APPROVE"


# ============================================================================
# Tests: PlagiarismDetectorV2 Initialization
# ============================================================================

def test_plagiarism_detector_v2_initialization(
    mock_embedding_service,
    mock_vector_database
):
    """Test PlagiarismDetectorV2 initialization"""
    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database,
        similarity_threshold=0.80
    )

    assert detector.embedding_service == mock_embedding_service
    assert detector.vector_database == mock_vector_database
    assert detector.similarity_threshold == 0.80
    assert detector.total_checks == 0
    assert detector.total_flagged == 0

    # Check phase components initialized
    assert isinstance(detector.exact_matcher, ExactMatchDetector)
    assert isinstance(detector.structural_analyzer, StructuralAnalyzer)
    assert isinstance(detector.source_checker, SourceSpecificChecker)
    assert isinstance(detector.risk_assessor, RiskAssessor)


# ============================================================================
# Tests: Add to Database
# ============================================================================

def test_add_to_database(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test adding question to database"""
    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    detector.add_to_database(
        question_id="q_001",
        content=sample_content,
        source_type=SourceType.INTERNAL,
        metadata={"difficulty": "easy"}
    )

    # Verify embedding service was called
    mock_embedding_service.generate_embedding.assert_called_once()

    # Verify vector database was called
    mock_vector_database.add_documents.assert_called_once()

    # Verify exact matcher was updated
    assert len(detector.exact_matcher.hash_index) > 0


def test_add_to_database_with_different_source_types(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test adding questions from different sources"""
    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    # Add AP released exam question
    detector.add_to_database(
        question_id="ap_001",
        content=sample_content,
        source_type=SourceType.AP_RELEASED
    )

    # Add textbook question
    detector.add_to_database(
        question_id="tb_001",
        content=sample_content,
        source_type=SourceType.TEXTBOOK
    )

    # Verify both were added
    assert mock_vector_database.add_documents.call_count == 2


# ============================================================================
# Tests: Check Content - Basic Flow
# ============================================================================

def test_check_content_original(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test checking original content (no matches)"""
    # Setup: empty database (no matches)
    mock_vector_database.search.return_value = []

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    report = detector.check_content(
        content=sample_content,
        content_id="q_new_001"
    )

    assert isinstance(report, PlagiarismReportV2)
    assert report.content_id == "q_new_001"
    assert report.overall_assessment["status"] == PlagiarismStatus.ORIGINAL.value
    assert report.risk_assessment.recommendation == "APPROVE"
    assert report.risk_assessment.requires_review == False


def test_check_content_with_moderate_similarity(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test checking content with moderate similarity"""
    # Setup: one moderate match
    mock_search_result = SearchResult(
        id="q_existing",
        similarity=0.65,  # Moderate (0.60-0.80)
        text="Find the derivative of x squared",
        metadata={"source_type": "internal_database"}
    )

    mock_vector_database.search.return_value = [mock_search_result]

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    report = detector.check_content(
        content=sample_content,
        content_id="q_new_002"
    )

    assert report.overall_assessment["status"] == PlagiarismStatus.MODERATE_SIMILARITY.value
    assert report.risk_assessment.recommendation == "APPROVE"
    assert len(report.moderate_similarity_matches["matches"]) > 0


def test_check_content_with_high_similarity(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test checking content with high similarity"""
    # Setup: one high similarity match
    mock_search_result = SearchResult(
        id="q_existing",
        similarity=0.92,  # High (≥0.80)
        text="Find the derivative of f(x) = x^2",
        metadata={"source_type": "internal_database"}
    )

    mock_vector_database.search.return_value = [mock_search_result]

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database,
        similarity_threshold=0.80
    )

    report = detector.check_content(
        content=sample_content,
        content_id="q_new_003"
    )

    assert report.overall_assessment["status"] == PlagiarismStatus.HIGH_SIMILARITY.value
    assert report.risk_assessment.recommendation == "REJECT"
    assert report.risk_assessment.requires_review == True
    assert len(report.high_similarity_matches["matches"]) > 0


def test_check_content_increments_counters(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test that check_content increments performance counters"""
    mock_vector_database.search.return_value = []

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    assert detector.total_checks == 0
    assert detector.total_flagged == 0

    # Check original content
    detector.check_content(content=sample_content, content_id="q1")

    assert detector.total_checks == 1
    assert detector.total_flagged == 0  # Not flagged

    # Check high similarity content
    mock_vector_database.search.return_value = [
        SearchResult(
            id="q_existing",
            similarity=0.95,
            text="exact match",
            metadata={"source_type": "internal_database"}
        )
    ]

    detector.check_content(content=sample_content, content_id="q2")

    assert detector.total_checks == 2
    assert detector.total_flagged == 1  # Flagged!


# ============================================================================
# Tests: Prepare Text for Embedding
# ============================================================================

def test_prepare_text_for_embedding_with_options(
    mock_embedding_service,
    mock_vector_database
):
    """Test text preparation includes options"""
    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    content = {
        "stimulus": "Question text",
        "options": ["A", "B", "C", "D"]
    }

    text = detector._prepare_text_for_embedding(content)

    assert "Question text" in text
    assert "A" in text
    assert "B" in text
    assert "C" in text
    assert "D" in text


def test_prepare_text_for_embedding_without_options(
    mock_embedding_service,
    mock_vector_database
):
    """Test text preparation without options"""
    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    content = {
        "stimulus": "Question text only"
    }

    text = detector._prepare_text_for_embedding(content)

    assert text == "Question text only"


# ============================================================================
# Tests: Statistics
# ============================================================================

def test_get_statistics(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test getting detector statistics"""
    mock_vector_database.search.return_value = []
    mock_vector_database.get_document_count.return_value = 100

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    # Perform some checks
    detector.check_content(content=sample_content, content_id="q1")
    detector.check_content(content=sample_content, content_id="q2")

    stats = detector.get_statistics()

    assert stats["total_checks"] == 2
    assert stats["total_flagged"] == 0
    assert stats["flag_rate"] == 0.0
    assert stats["database_size"] == 100
    assert stats["similarity_threshold"] == 0.80


def test_get_statistics_with_flags(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test statistics with flagged content"""
    # First check: no flags
    mock_vector_database.search.return_value = []

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    detector.check_content(content=sample_content, content_id="q1")

    # Second check: flagged
    mock_vector_database.search.return_value = [
        SearchResult(id="q_ex", similarity=0.95, text="match", metadata={})
    ]

    detector.check_content(content=sample_content, content_id="q2")

    stats = detector.get_statistics()

    assert stats["total_checks"] == 2
    assert stats["total_flagged"] == 1
    assert stats["flag_rate"] == 0.5  # 1 out of 2


# ============================================================================
# Tests: Error Handling
# ============================================================================

def test_check_content_handles_embedding_error(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test error handling when embedding generation fails"""
    mock_embedding_service.generate_embedding.side_effect = Exception("API Error")

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    with pytest.raises(Exception):
        detector.check_content(content=sample_content, content_id="q_test")


def test_check_content_handles_search_error(
    mock_embedding_service,
    mock_vector_database,
    sample_content
):
    """Test error handling when vector search fails"""
    mock_vector_database.search.side_effect = Exception("Database Error")

    detector = PlagiarismDetectorV2(
        embedding_service=mock_embedding_service,
        vector_database=mock_vector_database
    )

    with pytest.raises(Exception):
        detector.check_content(content=sample_content, content_id="q_test")
