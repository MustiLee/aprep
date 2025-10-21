"""
Unit tests for Bias Detector Agent
"""

import pytest
from src.agents.bias_detector import BiasDetector, detect_bias, BiasFlag, BiasReport


class TestBiasDetector:
    """Test suite for BiasDetector"""

    def test_initialization(self):
        """Test detector initialization"""
        detector = BiasDetector(sensitivity="high", flag_threshold=0.70)

        assert detector.sensitivity == "high"
        assert detector.flag_threshold == 0.70

    def test_no_bias_content(self):
        """Test content with no bias"""
        detector = BiasDetector()

        content = {
            "stimulus": "A student solved the equation x^2 - 5x + 6 = 0.",
            "options": {
                "A": "x = 2 or x = 3",
                "B": "x = -2 or x = -3",
                "C": "x = 1 or x = 6",
                "D": "x = 0 or x = 5"
            }
        }

        report = detector.analyze("test_001", content)

        assert report.item_id == "test_001"
        assert report.passed is True
        assert report.overall_risk == "acceptable"
        assert report.bias_score < 0.3

    def test_gender_bias_male_pronouns(self):
        """Test detection of default male pronouns"""
        detector = BiasDetector()

        content = {
            "stimulus": "An engineer is designing a bridge. He must calculate the load capacity.",
        }

        report = detector.analyze("test_002", content)

        assert len(report.flags) > 0
        gender_flags = [f for f in report.flags if f.category == "gender"]
        assert len(gender_flags) > 0
        assert any("pronoun" in f.issue.lower() or "engineer" in f.issue.lower() for f in gender_flags)

    def test_gender_bias_gendered_occupation(self):
        """Test detection of gendered occupation terms"""
        detector = BiasDetector()

        content = {
            "stimulus": "The fireman responded to the emergency call.",
        }

        report = detector.analyze("test_003", content)

        gender_flags = [f for f in report.flags if f.category == "gender"]
        assert len(gender_flags) > 0
        assert any("fireman" in f.evidence.lower() for f in gender_flags)

    def test_socioeconomic_bias_luxury_items(self):
        """Test detection of luxury item assumptions"""
        detector = BiasDetector()

        content = {
            "stimulus": "Maria's family owns a yacht. Calculate the fuel cost for a trip.",
        }

        report = detector.analyze("test_004", content)

        socio_flags = [f for f in report.flags if f.category == "socioeconomic"]
        assert len(socio_flags) > 0
        assert any("yacht" in f.evidence.lower() for f in socio_flags)

    def test_ableist_language_detection(self):
        """Test detection of ableist language"""
        detector = BiasDetector()

        content = {
            "stimulus": "This problem is so simple, even a crazy person could solve it.",
        }

        report = detector.analyze("test_005", content)

        disability_flags = [f for f in report.flags if f.category == "disability"]
        assert len(disability_flags) > 0
        assert any("crazy" in f.evidence.lower() for f in disability_flags)

    def test_geographic_bias_us_centric(self):
        """Test detection of US-centric content"""
        detector = BiasDetector()

        content = {
            "stimulus": "On Thanksgiving, the temperature was 72 Fahrenheit.",
        }

        report = detector.analyze("test_006", content)

        geo_flags = [f for f in report.flags if f.category == "geographic"]
        assert len(geo_flags) > 0

    def test_name_diversity_scoring(self):
        """Test name diversity scoring"""
        detector = BiasDetector()

        # Low diversity (all Western names)
        content1 = {
            "stimulus": "John, Mary, and David are working on a project.",
        }

        report1 = detector.analyze("test_007", content1)
        assert report1.diversity_score < 0.5

        # High diversity (multiple cultures)
        content2 = {
            "stimulus": "Carlos, Mei, Amina, and Ravi are working on a project.",
        }

        report2 = detector.analyze("test_008", content2)
        assert report2.diversity_score > report1.diversity_score

    def test_severity_levels(self):
        """Test different severity levels"""
        detector = BiasDetector()

        # High severity content
        content = {
            "stimulus": "The policeman told her she was crazy for thinking that.",
        }

        report = detector.analyze("test_009", content)

        high_severity = [f for f in report.flags if f.severity == "high"]
        assert len(high_severity) > 0

    def test_threshold_filtering(self):
        """Test confidence threshold filtering"""
        # Low threshold - more flags
        detector_low = BiasDetector(flag_threshold=0.50)

        # High threshold - fewer flags
        detector_high = BiasDetector(flag_threshold=0.85)

        content = {
            "stimulus": "He is an engineer working on the project.",
        }

        report_low = detector_low.analyze("test_010", content)
        report_high = detector_high.analyze("test_010", content)

        assert len(report_low.flags) >= len(report_high.flags)

    def test_risk_assessment(self):
        """Test risk level assessment"""
        detector = BiasDetector()

        # Acceptable risk
        content1 = {
            "stimulus": "A student calculated the derivative of f(x) = x^2.",
        }

        report1 = detector.analyze("test_011", content1)
        assert report1.overall_risk == "acceptable"

        # Higher risk
        content2 = {
            "stimulus": "The chairman told his secretary that poor people don't understand math.",
        }

        report2 = detector.analyze("test_012", content2)
        assert report2.overall_risk in ["review_recommended", "reject_recommended"]

    def test_recommendations_generated(self):
        """Test that recommendations are generated"""
        detector = BiasDetector()

        content = {
            "stimulus": "The fireman told him that Thanksgiving is on Thursday.",
        }

        report = detector.analyze("test_013", content)

        assert len(report.recommendations) > 0
        assert isinstance(report.recommendations[0], str)

    def test_multiple_bias_categories(self):
        """Test detection of multiple bias categories"""
        detector = BiasDetector()

        content = {
            "stimulus": "The policeman drove his yacht to the country club on Thanksgiving.",
        }

        report = detector.analyze("test_014", content)

        categories = set(f.category for f in report.flags)
        assert len(categories) > 1  # Multiple bias types

    def test_convenience_function(self):
        """Test convenience function"""
        content = {
            "stimulus": "Calculate the area of a rectangle.",
        }

        report = detect_bias("test_015", content)

        assert isinstance(report, BiasReport)
        assert report.item_id == "test_015"

    def test_bias_score_calculation(self):
        """Test bias score calculation"""
        detector = BiasDetector()

        # No bias
        content1 = {
            "stimulus": "Find the derivative of f(x) = 3x + 2.",
        }

        report1 = detector.analyze("test_016", content1)
        assert report1.bias_score == 0.0

        # Some bias
        content2 = {
            "stimulus": "The chairman used his yacht for Thanksgiving.",
        }

        report2 = detector.analyze("test_017", content2)
        assert report2.bias_score > 0.0
        assert report2.bias_score <= 1.0

    def test_empty_content(self):
        """Test handling of empty content"""
        detector = BiasDetector()

        content = {}

        report = detector.analyze("test_018", content)

        assert report.passed is True
        assert len(report.flags) == 0

    def test_report_structure(self):
        """Test report data structure"""
        detector = BiasDetector()

        content = {
            "stimulus": "A mathematician solved the problem.",
        }

        report = detector.analyze("test_019", content)

        assert hasattr(report, "item_id")
        assert hasattr(report, "analyzed_at")
        assert hasattr(report, "overall_risk")
        assert hasattr(report, "bias_score")
        assert hasattr(report, "flags")
        assert hasattr(report, "passed")
        assert hasattr(report, "recommendations")
        assert hasattr(report, "diversity_score")

        assert isinstance(report.flags, list)
        assert isinstance(report.bias_score, float)
        assert isinstance(report.passed, bool)


class TestBiasFlag:
    """Test BiasFlag dataclass"""

    def test_flag_creation(self):
        """Test creating a bias flag"""
        flag = BiasFlag(
            category="gender",
            severity="medium",
            confidence=0.75,
            location="stimulus",
            issue="Test issue",
            evidence="test evidence",
            suggestion="test suggestion"
        )

        assert flag.category == "gender"
        assert flag.severity == "medium"
        assert flag.confidence == 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
