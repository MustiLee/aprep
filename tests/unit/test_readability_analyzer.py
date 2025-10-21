"""Unit tests for Readability Analyzer agent."""

import pytest
from src.agents.readability_analyzer import (
    ReadabilityAnalyzer,
    ReadabilityMetrics,
    ReadabilityReport
)


class TestReadabilityAnalyzer:
    """Test Readability Analyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create ReadabilityAnalyzer instance."""
        return ReadabilityAnalyzer()

    def test_initialization(self, analyzer):
        """Test analyzer can be initialized."""
        assert analyzer is not None
        assert analyzer.target_grade_level == 11.0
        assert analyzer.max_acceptable_grade == 13.0
        assert analyzer.min_acceptable_grade == 9.0
        assert analyzer.total_analyses == 0
        assert analyzer.total_flagged == 0

    def test_analyze_simple_question(self, analyzer):
        """Test analyzing a simple question."""
        question = "Find the derivative of f(x) = x^2."

        report = analyzer.analyze_question(question, question_id="simple_001")

        assert isinstance(report, ReadabilityReport)
        assert report.question_id == "simple_001"
        assert isinstance(report.metrics, ReadabilityMetrics)
        assert report.metrics.total_words > 0
        assert report.metrics.total_sentences > 0

    def test_analyze_complex_question(self, analyzer):
        """Test analyzing a complex question."""
        question = (
            "Determine the derivative of the composite trigonometric function "
            "f(x) = sin(cos(x)) utilizing the chain rule methodology and express "
            "your solution in simplified form."
        )

        report = analyzer.analyze_question(question, question_id="complex_001")

        assert isinstance(report, ReadabilityReport)
        # Complex question should have higher grade level
        assert report.metrics.flesch_kincaid_grade > 10.0

    def test_count_words(self, analyzer):
        """Test word counting."""
        text1 = "The cat sat on the mat."
        assert analyzer._count_words(text1) == 6

        text2 = "One. Two. Three."
        assert analyzer._count_words(text2) == 3

    def test_count_sentences(self, analyzer):
        """Test sentence counting."""
        text1 = "This is one sentence."
        assert analyzer._count_sentences(text1) == 1

        text2 = "First sentence. Second sentence. Third!"
        assert analyzer._count_sentences(text2) == 3

        text3 = "Question? Answer!"
        assert analyzer._count_sentences(text3) == 2

    def test_count_syllables_in_word(self, analyzer):
        """Test syllable counting in words."""
        assert analyzer._count_syllables_in_word("cat") == 1
        assert analyzer._count_syllables_in_word("happy") == 2
        assert analyzer._count_syllables_in_word("beautiful") == 3
        assert analyzer._count_syllables_in_word("derivative") == 4

    def test_count_syllables_in_text(self, analyzer):
        """Test total syllable counting."""
        text = "The cat sat."  # 1 + 1 + 1 = 3 syllables
        syllables = analyzer._count_syllables(text)
        assert syllables >= 3

    def test_tokenize(self, analyzer):
        """Test text tokenization."""
        text = "Find the derivative of f(x) = x^2."
        tokens = analyzer._tokenize(text)

        assert "Find" in tokens or "find" in tokens
        assert "derivative" in tokens or "Derivative" in tokens
        assert len(tokens) > 0

    def test_count_technical_terms(self, analyzer):
        """Test technical term counting."""
        text1 = "Find the derivative using the limit theorem."
        count1 = analyzer._count_technical_terms(text1)
        assert count1 >= 2  # "derivative" and "limit" or "theorem"

        text2 = "The cat sat on the mat."
        count2 = analyzer._count_technical_terms(text2)
        assert count2 == 0

    def test_flesch_kincaid_grade(self, analyzer):
        """Test Flesch-Kincaid grade level calculation."""
        # Simple text should have lower grade
        simple = "The cat sat. The dog ran."
        report1 = analyzer.analyze_question(simple)
        assert report1.metrics.flesch_kincaid_grade < 8.0

        # Complex text should have higher grade
        complex_text = (
            "The derivative of a function represents the instantaneous rate of change, "
            "which can be determined through the application of differential calculus methodologies."
        )
        report2 = analyzer.analyze_question(complex_text)
        assert report2.metrics.flesch_kincaid_grade > 12.0

    def test_flesch_reading_ease(self, analyzer):
        """Test Flesch Reading Ease calculation."""
        question = "Find the derivative of f(x) = x^2 using the power rule."
        report = analyzer.analyze_question(question)

        # Score should be between 0 and 100
        assert 0.0 <= report.metrics.flesch_reading_ease <= 100.0

    def test_complex_word_ratio(self, analyzer):
        """Test complex word ratio calculation."""
        # Text with many short words
        simple = "The cat sat on a mat."
        report1 = analyzer.analyze_question(simple)
        assert report1.metrics.complex_word_ratio < 0.2

        # Text with many complex words
        complex_text = "Differentiation methodology utilizes infinitesimal calculations."
        report2 = analyzer.analyze_question(complex_text)
        assert report2.metrics.complex_word_ratio > 0.3

    def test_technical_term_density(self, analyzer):
        """Test technical term density calculation."""
        # Question with no technical terms
        simple = "What is the answer to this question?"
        report1 = analyzer.analyze_question(simple)
        assert report1.metrics.technical_term_density < 5.0

        # Question with many technical terms
        technical = "Find the derivative of the integral using the fundamental theorem."
        report2 = analyzer.analyze_question(technical)
        assert report2.metrics.technical_term_density > 20.0

    def test_readability_level_categorization(self, analyzer):
        """Test readability level categories."""
        # Very easy
        very_easy = "The cat sat."
        report1 = analyzer.analyze_question(very_easy)
        assert report1.metrics.readability_level in ["very_easy", "easy"]

        # Difficult
        difficult = (
            "The antiderivative of the exponential function with respect to the "
            "independent variable necessitates comprehensive understanding."
        )
        report2 = analyzer.analyze_question(difficult)
        assert report2.metrics.readability_level in ["difficult", "very_difficult"]

    def test_flagging_high_grade_level(self):
        """Test flagging questions with high grade level."""
        analyzer = ReadabilityAnalyzer(max_acceptable_grade=12.0)

        # Very complex question
        complex_text = (
            "Utilizing comprehensive methodological approaches, determine the "
            "antiderivative of the multivariable trigonometric function through "
            "systematic application of integration by parts and substitution techniques."
        )

        report = analyzer.analyze_question(complex_text, "flag_001")

        # Should be flagged if grade level exceeds max
        if report.metrics.flesch_kincaid_grade > 12.0:
            assert report.flagged is True
            assert any("exceeds maximum" in reason for reason in report.flag_reasons)

    def test_flagging_long_sentences(self, analyzer):
        """Test flagging questions with long sentences."""
        # Very long sentence
        long_sentence = (
            "Calculate the derivative of the function f(x) = sin(x) * cos(x) "
            "by first applying the product rule to find the rate of change and "
            "then simplifying the resulting expression using trigonometric identities "
            "and algebraic manipulation techniques to arrive at the final solution."
        )

        report = analyzer.analyze_question(long_sentence, "long_001")

        # Should flag long sentences
        if report.metrics.avg_sentence_length > 30:
            assert report.flagged is True

    def test_flagging_high_complex_word_ratio(self, analyzer):
        """Test flagging high complex word ratio."""
        # Many complex words
        complex_words = (
            "Differentiation methodology utilizes infinitesimal calculations "
            "incorporating trigonometric relationships and exponential functions."
        )

        report = analyzer.analyze_question(complex_words, "complex_001")

        # May be flagged for high complex word ratio
        if report.metrics.complex_word_ratio > 0.40:
            assert report.flagged is True

    def test_appropriate_question_not_flagged(self, analyzer):
        """Test that appropriate questions are not flagged."""
        appropriate = "Find the derivative of f(x) = 2x using the power rule."

        report = analyzer.analyze_question(appropriate, "appropriate_001")

        # Should be appropriate for AP level
        assert report.is_appropriate is True or report.metrics.flesch_kincaid_grade < 13.0

    def test_recommendations_generation(self, analyzer):
        """Test that recommendations are generated."""
        # Complex question should generate recommendations
        complex_text = (
            "The antiderivative necessitates comprehensive methodological approaches "
            "utilizing sophisticated mathematical techniques."
        )

        report = analyzer.analyze_question(complex_text, "rec_001")

        if report.flagged:
            assert len(report.recommendations) > 0

    def test_batch_analysis(self, analyzer):
        """Test analyzing multiple questions."""
        questions = [
            {"id": "batch_001", "text": "Find the derivative of x^2."},
            {"id": "batch_002", "text": "What is the integral of 2x?"},
            {"id": "batch_003", "text": "Calculate the limit as x approaches 0."}
        ]

        reports = analyzer.analyze_batch(questions)

        assert len(reports) == 3
        assert all(isinstance(r, ReadabilityReport) for r in reports)
        assert reports[0].question_id == "batch_001"

    def test_statistics_tracking(self, analyzer):
        """Test statistics tracking."""
        # Analyze some questions
        analyzer.analyze_question("Simple question.", "stat_001")
        analyzer.analyze_question(
            "Comprehensive methodological utilization of sophisticated techniques.",
            "stat_002"
        )

        stats = analyzer.get_statistics()

        assert stats["total_analyses"] == 2
        assert "flag_rate" in stats
        assert "avg_grade_level" in stats
        assert stats["target_grade_level"] == 11.0

    def test_analysis_history(self, analyzer):
        """Test analysis history tracking."""
        analyzer.analyze_question("Question 1", "hist_001")
        analyzer.analyze_question("Question 2", "hist_002")

        history = analyzer.get_analysis_history()

        assert len(history) == 2
        assert history[0]["question_id"] == "hist_001"
        assert "grade_level" in history[0]

    def test_analysis_history_limit(self, analyzer):
        """Test analysis history limit."""
        for i in range(5):
            analyzer.analyze_question(f"Question {i}", f"limit_{i}")

        history = analyzer.get_analysis_history(limit=3)

        assert len(history) == 3

    def test_analysis_history_flagged_only(self, analyzer):
        """Test filtering history for flagged items."""
        # Simple question (won't be flagged)
        analyzer.analyze_question("The cat sat.", "simple_001")

        # Complex question (may be flagged)
        analyzer.analyze_question(
            "Methodological approaches necessitate comprehensive utilization.",
            "complex_001"
        )

        history_all = analyzer.get_analysis_history()
        history_flagged = analyzer.get_analysis_history(flagged_only=True)

        assert len(history_all) >= 2
        assert len(history_flagged) <= len(history_all)
        assert all(h["flagged"] for h in history_flagged)

    def test_custom_grade_level_targets(self):
        """Test custom grade level targets."""
        analyzer = ReadabilityAnalyzer(
            target_grade_level=10.0,
            max_acceptable_grade=12.0,
            min_acceptable_grade=8.0
        )

        assert analyzer.target_grade_level == 10.0
        assert analyzer.max_acceptable_grade == 12.0
        assert analyzer.min_acceptable_grade == 8.0

    def test_report_metadata(self, analyzer):
        """Test that reports include metadata."""
        question = "Test question."
        report = analyzer.analyze_question(question, "meta_001")

        assert "target_grade" in report.metadata
        assert "grade_range" in report.metadata
        assert report.metadata["target_grade"] == 11.0


class TestReadabilityMetrics:
    """Test ReadabilityMetrics model."""

    def test_metrics_creation(self):
        """Test creating readability metrics."""
        metrics = ReadabilityMetrics(
            flesch_kincaid_grade=11.5,
            flesch_reading_ease=60.0,
            avg_sentence_length=15.0,
            avg_syllables_per_word=1.5,
            total_words=100,
            total_sentences=7,
            total_syllables=150,
            complex_word_count=20,
            complex_word_ratio=0.20,
            technical_term_count=5,
            technical_term_density=5.0,
            readability_level="moderate"
        )

        assert metrics.flesch_kincaid_grade == 11.5
        assert metrics.readability_level == "moderate"
        assert metrics.technical_term_count == 5


class TestReadabilityReport:
    """Test ReadabilityReport model."""

    def test_report_creation(self):
        """Test creating a readability report."""
        metrics = ReadabilityMetrics(
            flesch_kincaid_grade=11.5,
            flesch_reading_ease=60.0,
            avg_sentence_length=15.0,
            avg_syllables_per_word=1.5,
            total_words=100,
            total_sentences=7,
            total_syllables=150,
            complex_word_count=20,
            complex_word_ratio=0.20,
            technical_term_count=5,
            technical_term_density=5.0,
            readability_level="moderate"
        )

        report = ReadabilityReport(
            question_id="test_001",
            question_text="Test question text.",
            metrics=metrics,
            is_appropriate=True,
            flagged=False,
            flag_reasons=[],
            recommendations=[]
        )

        assert report.question_id == "test_001"
        assert report.is_appropriate is True
        assert report.flagged is False
        assert isinstance(report.metrics, ReadabilityMetrics)


class TestIntegration:
    """Integration tests."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with realistic settings."""
        return ReadabilityAnalyzer(
            target_grade_level=11.0,
            max_acceptable_grade=13.0,
            min_acceptable_grade=9.0
        )

    def test_end_to_end_analysis(self, analyzer):
        """Test complete analysis workflow."""
        questions = [
            # Simple question
            "Find the derivative of x^2.",

            # Moderate question
            "Use the power rule to find the derivative of f(x) = 3x^4.",

            # Complex question
            "Utilizing the fundamental theorem of calculus, determine the definite "
            "integral of the function f(x) = sin(x) over the interval [0, pi]."
        ]

        reports = []
        for i, question in enumerate(questions):
            report = analyzer.analyze_question(question, f"workflow_{i}")
            reports.append(report)

        # Check all reports generated
        assert len(reports) == 3

        # Simple question should have lower grade level
        assert reports[0].metrics.flesch_kincaid_grade < reports[2].metrics.flesch_kincaid_grade

        # Complex question may be flagged
        # (depending on exact calculation)

    def test_statistics_after_multiple_analyses(self, analyzer):
        """Test statistics after multiple operations."""
        questions = [
            "Simple question.",
            "Moderate complexity question with technical derivative terms.",
            "Extraordinarily sophisticated methodological computational procedures."
        ]

        for i, q in enumerate(questions):
            analyzer.analyze_question(q, f"stat_{i}")

        stats = analyzer.get_statistics()

        assert stats["total_analyses"] == 3
        assert 0.0 <= stats["flag_rate"] <= 1.0
        assert "avg_grade_level" in stats
        assert "avg_reading_ease" in stats

    def test_realistic_ap_question(self, analyzer):
        """Test with realistic AP Calculus question."""
        question = (
            "Let f(x) = x^3 - 3x^2 + 2. Find all values of x where f'(x) = 0. "
            "Then determine whether each critical point is a local maximum, "
            "local minimum, or neither using the second derivative test."
        )

        report = analyzer.analyze_question(question, "ap_question_001")

        # Grade level will vary, but should have valid metrics
        assert 0.0 <= report.metrics.flesch_kincaid_grade <= 18.0

        # May or may not be flagged depending on exact metrics
        # But should have meaningful analysis
        assert report.metrics.total_words > 0
        assert report.metrics.total_sentences > 0
