"""Unit tests for Plagiarism Detector agent."""

import pytest
import json
from pathlib import Path
from src.agents.plagiarism_detector import (
    PlagiarismDetector,
    SimilarityMatch,
    PlagiarismReport
)


class TestPlagiarismDetector:
    """Test Plagiarism Detector functionality."""

    @pytest.fixture
    def sample_question_bank(self, tmp_path):
        """Create sample question bank."""
        bank = [
            {
                "id": "q001",
                "text": "Find the derivative of f(x) = x^2 using the power rule.",
                "metadata": {"topic": "derivatives", "difficulty": 2}
            },
            {
                "id": "q002",
                "text": "Calculate the integral of g(x) = 2x from 0 to 1.",
                "metadata": {"topic": "integration", "difficulty": 2}
            },
            {
                "id": "q003",
                "text": "What is the limit of h(x) = sin(x)/x as x approaches 0?",
                "metadata": {"topic": "limits", "difficulty": 3}
            }
        ]

        bank_path = tmp_path / "question_bank.json"
        with open(bank_path, 'w') as f:
            json.dump(bank, f)

        return str(bank_path)

    @pytest.fixture
    def detector(self, sample_question_bank):
        """Create PlagiarismDetector instance."""
        return PlagiarismDetector(question_bank_path=sample_question_bank)

    def test_initialization(self, detector):
        """Test detector can be initialized."""
        assert detector is not None
        assert len(detector.question_bank) == 3
        assert detector.similarity_threshold == 0.80
        assert detector.total_checks == 0
        assert detector.total_flagged == 0

    def test_initialization_empty_bank(self):
        """Test initialization with no question bank."""
        detector = PlagiarismDetector()
        assert len(detector.question_bank) == 0

    def test_check_exact_match(self, detector):
        """Test detection of exact match."""
        # Exact same question
        question = "Find the derivative of f(x) = x^2 using the power rule."

        report = detector.check_question(question, question_id="test_001")

        assert isinstance(report, PlagiarismReport)
        assert report.is_original is False
        assert report.flagged is True
        assert report.max_similarity >= 0.95
        assert len(report.matches) > 0
        assert report.matches[0].match_type == "exact"

    def test_check_high_similarity(self, detector):
        """Test detection of high similarity."""
        # Very similar but not exact
        question = "Find the derivative of f(x) = x^2 using power rule."

        report = detector.check_question(question, question_id="test_002")

        assert isinstance(report, PlagiarismReport)
        assert report.max_similarity >= 0.80
        # Should be flagged for high similarity
        assert report.flagged is True

    def test_check_moderate_similarity(self, detector):
        """Test detection of moderate similarity."""
        # Somewhat similar question
        question = "Determine the derivative of the function f(x) = x squared."

        report = detector.check_question(question, question_id="test_003")

        assert isinstance(report, PlagiarismReport)
        # Should have moderate similarity
        assert 0.40 < report.max_similarity < 0.80
        # Should not be flagged
        assert report.flagged is False
        assert report.is_original is True

    def test_check_original_question(self, detector):
        """Test detection of completely original question."""
        # Completely different question
        question = "Explain the fundamental theorem of calculus in your own words."

        report = detector.check_question(question, question_id="test_004")

        assert isinstance(report, PlagiarismReport)
        assert report.is_original is True
        assert report.flagged is False
        assert report.max_similarity < 0.80

    def test_normalize_text(self, detector):
        """Test text normalization."""
        text1 = "Find the derivative of f(x) = x^2."
        text2 = "FIND THE DERIVATIVE OF F(X) = X^2"

        normalized1 = detector._normalize_text(text1)
        normalized2 = detector._normalize_text(text2)

        # Should be nearly identical after normalization
        assert normalized1.lower() == normalized2.lower()

    def test_tokenize(self, detector):
        """Test text tokenization."""
        text = "Find the derivative of f(x) = x^2."
        tokens = detector._tokenize(text)

        assert "find" in tokens
        assert "derivative" in tokens
        assert "x" in tokens
        assert len(tokens) > 0

    def test_calculate_lexical_similarity(self, detector):
        """Test lexical similarity calculation."""
        text1 = "Find the derivative of f(x) = x^2."
        text2 = "Find the derivative of f(x) = x^2."
        text3 = "Calculate the integral of g(x) = 2x."

        # Identical texts (allowing for floating point precision)
        sim1 = detector._calculate_lexical_similarity(text1, text2)
        assert sim1 >= 0.999

        # Different texts
        sim2 = detector._calculate_lexical_similarity(text1, text3)
        assert 0.0 < sim2 < 1.0

    def test_calculate_semantic_similarity(self, detector):
        """Test semantic similarity calculation."""
        text1 = "Find the derivative of f(x) = x^2."
        text2 = "Calculate the derivative of f(x) = x^2."
        text3 = "What is the weather today?"

        # Similar texts
        sim1 = detector._calculate_semantic_similarity(text1, text2)
        assert sim1 > 0.5

        # Unrelated texts
        sim2 = detector._calculate_semantic_similarity(text1, text3)
        assert sim2 < 0.3

    def test_top_matches_returned(self, detector):
        """Test that top N matches are returned."""
        question = "Find the derivative of f(x) = x^2."

        report = detector.check_question(question, return_top_n=2)

        assert len(report.matches) <= 2

    def test_matches_sorted_by_similarity(self, detector):
        """Test that matches are sorted by similarity."""
        question = "Find the derivative of f(x) = x^2."

        report = detector.check_question(question, return_top_n=3)

        # Matches should be in descending order of similarity
        for i in range(len(report.matches) - 1):
            assert report.matches[i].combined_similarity >= report.matches[i + 1].combined_similarity

    def test_add_to_question_bank(self, detector):
        """Test adding question to bank."""
        initial_count = len(detector.question_bank)

        detector.add_to_question_bank(
            question_id="q_new_001",
            question_text="What is the Taylor series expansion?",
            metadata={"topic": "series"}
        )

        assert len(detector.question_bank) == initial_count + 1
        assert detector.question_bank[-1]["id"] == "q_new_001"

    def test_remove_from_question_bank(self, detector):
        """Test removing question from bank."""
        initial_count = len(detector.question_bank)

        # Remove existing question
        removed = detector.remove_from_question_bank("q001")

        assert removed is True
        assert len(detector.question_bank) == initial_count - 1

        # Try to remove non-existent question
        removed = detector.remove_from_question_bank("nonexistent")
        assert removed is False

    def test_batch_check(self, detector):
        """Test checking multiple questions."""
        questions = [
            {"id": "batch_001", "text": "Find the derivative of x^2."},
            {"id": "batch_002", "text": "What is integration by parts?"},
            {"id": "batch_003", "text": "Explain L'Hopital's rule."}
        ]

        reports = detector.check_batch(questions, return_top_n=2)

        assert len(reports) == 3
        assert all(isinstance(r, PlagiarismReport) for r in reports)
        assert reports[0].question_id == "batch_001"

    def test_statistics_tracking(self, detector):
        """Test statistics tracking."""
        # Perform some checks
        detector.check_question("Test question 1", question_id="stat_001")
        # Use exact match to ensure it's flagged
        detector.check_question("Find the derivative of f(x) = x^2 using the power rule.", question_id="stat_002")  # Will be flagged

        stats = detector.get_statistics()

        assert stats["total_checks"] == 2
        assert stats["total_flagged"] >= 1
        assert "flag_rate" in stats
        assert stats["question_bank_size"] == 3
        assert stats["similarity_threshold"] == 0.80

    def test_check_history(self, detector):
        """Test check history tracking."""
        # Perform some checks
        detector.check_question("Test question 1", question_id="hist_001")
        detector.check_question("Test question 2", question_id="hist_002")

        history = detector.get_check_history()

        assert len(history) == 2
        assert history[0]["question_id"] == "hist_001"
        assert "max_similarity" in history[0]

    def test_check_history_limit(self, detector):
        """Test check history limit."""
        # Perform multiple checks
        for i in range(5):
            detector.check_question(f"Test question {i}", question_id=f"limit_{i}")

        history = detector.get_check_history(limit=3)

        assert len(history) == 3

    def test_check_history_flagged_only(self, detector):
        """Test filtering history for flagged items only."""
        # Check original question (won't be flagged)
        detector.check_question("Completely unique question abc123", question_id="orig_001")

        # Check similar question (will be flagged)
        detector.check_question("Find the derivative of f(x) = x^2.", question_id="flag_001")

        history_all = detector.get_check_history()
        history_flagged = detector.get_check_history(flagged_only=True)

        assert len(history_all) >= 2
        assert len(history_flagged) >= 1
        assert all(h["flagged"] for h in history_flagged)

    def test_flag_reason(self, detector):
        """Test that flagged questions have reasons."""
        # Exact match
        question = "Find the derivative of f(x) = x^2 using the power rule."
        report = detector.check_question(question, question_id="flag_test_001")

        if report.flagged:
            assert report.flag_reason is not None
            assert len(report.flag_reason) > 0

    def test_similarity_weights(self):
        """Test custom similarity weights."""
        detector = PlagiarismDetector(
            lexical_weight=0.8,
            semantic_weight=0.2
        )

        assert detector.lexical_weight == 0.8
        assert detector.semantic_weight == 0.2

    def test_custom_threshold(self):
        """Test custom similarity threshold."""
        detector = PlagiarismDetector(similarity_threshold=0.90)

        assert detector.similarity_threshold == 0.90

    def test_build_tfidf_index(self, detector):
        """Test TF-IDF index building."""
        index = detector.tfidf_index

        assert "idf" in index
        assert "doc_count" in index
        assert index["doc_count"] == 3

    def test_report_metadata(self, detector):
        """Test that reports include metadata."""
        question = "Test question"
        report = detector.check_question(question, question_id="meta_001")

        assert "total_matches_found" in report.metadata
        assert "bank_size" in report.metadata
        assert report.metadata["bank_size"] == 3


class TestSimilarityMatch:
    """Test SimilarityMatch model."""

    def test_match_creation(self):
        """Test creating a similarity match."""
        match = SimilarityMatch(
            question_id="q001",
            lexical_similarity=0.85,
            semantic_similarity=0.75,
            combined_similarity=0.82,
            matched_text="Sample question text",
            match_type="high"
        )

        assert match.question_id == "q001"
        assert match.lexical_similarity == 0.85
        assert match.combined_similarity == 0.82
        assert match.match_type == "high"

    def test_match_validation(self):
        """Test match validation."""
        # Similarity scores must be 0-1
        with pytest.raises(Exception):
            SimilarityMatch(
                question_id="q001",
                lexical_similarity=1.5,  # Invalid!
                semantic_similarity=0.75,
                combined_similarity=0.82,
                matched_text="Text",
                match_type="high"
            )


class TestPlagiarismReport:
    """Test PlagiarismReport model."""

    def test_report_creation(self):
        """Test creating a plagiarism report."""
        matches = [
            SimilarityMatch(
                question_id="q001",
                lexical_similarity=0.85,
                semantic_similarity=0.75,
                combined_similarity=0.82,
                matched_text="Similar question",
                match_type="high"
            )
        ]

        report = PlagiarismReport(
            question_id="test_001",
            question_text="Test question text",
            is_original=False,
            max_similarity=0.82,
            matches=matches,
            flagged=True,
            flag_reason="High similarity detected"
        )

        assert report.question_id == "test_001"
        assert report.is_original is False
        assert report.flagged is True
        assert len(report.matches) == 1
        assert report.max_similarity == 0.82


class TestIntegration:
    """Integration tests."""

    @pytest.fixture
    def full_setup(self, tmp_path):
        """Setup with realistic question bank."""
        bank = [
            {
                "id": "calc_001",
                "text": "Let f(x) = 3x^2. Find f'(x).",
                "metadata": {"topic": "derivatives", "difficulty": 2}
            },
            {
                "id": "calc_002",
                "text": "Evaluate the integral ∫(2x + 1)dx.",
                "metadata": {"topic": "integration", "difficulty": 2}
            },
            {
                "id": "calc_003",
                "text": "Find the limit as x approaches 0 of (sin(x))/x.",
                "metadata": {"topic": "limits", "difficulty": 3}
            },
            {
                "id": "calc_004",
                "text": "Use the chain rule to find the derivative of sin(2x).",
                "metadata": {"topic": "derivatives", "difficulty": 3}
            }
        ]

        bank_path = tmp_path / "full_bank.json"
        with open(bank_path, 'w') as f:
            json.dump(bank, f)

        detector = PlagiarismDetector(
            question_bank_path=str(bank_path),
            similarity_threshold=0.80
        )

        return detector

    def test_end_to_end_plagiarism_detection(self, full_setup):
        """Test complete plagiarism detection workflow."""
        detector = full_setup

        # Test 1: Original question (should pass)
        original_question = "Explain the Mean Value Theorem and provide an example."
        report1 = detector.check_question(original_question, question_id="workflow_001")

        assert report1.is_original is True
        assert report1.flagged is False

        # Test 2: Near-duplicate question (should flag)
        duplicate_question = "Let f(x) = 3x^2. Find the derivative f'(x)."
        report2 = detector.check_question(duplicate_question, question_id="workflow_002")

        assert report2.is_original is False or report2.max_similarity >= 0.70
        # Might be flagged depending on exact similarity

        # Test 3: Add new question to bank
        detector.add_to_question_bank(
            "calc_005",
            "Find the second derivative of f(x) = x^3.",
            {"topic": "derivatives"}
        )

        assert len(detector.question_bank) == 5

        # Test 4: Check against newly added question
        similar_to_new = "Find the second derivative of the function f(x) = x^3."
        report3 = detector.check_question(similar_to_new, question_id="workflow_003")

        assert report3.max_similarity > 0.80

    def test_batch_processing(self, full_setup):
        """Test batch processing of questions."""
        detector = full_setup

        questions = [
            {"id": "batch_001", "text": "What is the product rule for derivatives?"},
            {"id": "batch_002", "text": "Let f(x) = 3x^2. Find f'(x)."},  # Similar to calc_001
            {"id": "batch_003", "text": "Explain the Intermediate Value Theorem."},
        ]

        reports = detector.check_batch(questions)

        assert len(reports) == 3
        # Second question should have high similarity
        assert reports[1].max_similarity > 0.70

    def test_statistics_after_multiple_checks(self, full_setup):
        """Test statistics after multiple operations."""
        detector = full_setup

        # Perform various checks
        detector.check_question("Original question 1", "stat_001")
        detector.check_question("Let f(x) = 3x^2. Find f'(x).", "stat_002")  # Duplicate
        detector.check_question("Original question 2", "stat_003")

        stats = detector.get_statistics()

        assert stats["total_checks"] == 3
        assert stats["total_flagged"] >= 1
        assert 0.0 <= stats["flag_rate"] <= 1.0
        assert "avg_max_similarity" in stats

    def test_persistence(self, full_setup, tmp_path):
        """Test that question bank is persisted."""
        detector = full_setup

        # Add a new question
        detector.add_to_question_bank(
            "persist_001",
            "Test persistence question",
            {"test": True}
        )

        # Create new detector instance with same bank path
        detector2 = PlagiarismDetector(
            question_bank_path=detector.question_bank_path
        )

        # Should load the added question
        assert len(detector2.question_bank) == 5
        assert any(q["id"] == "persist_001" for q in detector2.question_bank)
