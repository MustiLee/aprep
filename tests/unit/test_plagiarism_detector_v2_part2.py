"""
Unit tests for Plagiarism Detector V2 - Part 2

Tests Phase 3 (Structural), Phase 4 (Source-Specific), and Phase 5 (Risk Assessment)
"""

import pytest
from unittest.mock import Mock

from src.agents.plagiarism_detector_v2 import (
    StructuralAnalyzer,
    SourceSpecificChecker,
    RiskAssessor,
    RiskLevel,
    SourceType,
    MatchAnalysis,
    SimilarityMatch,
    RiskAssessment,
    Evidence,
    MatchType
)


# ============================================================================
# Tests: Phase 3 - StructuralAnalyzer
# ============================================================================

def test_structural_analyzer_initialization():
    """Test StructuralAnalyzer initialization"""
    analyzer = StructuralAnalyzer()
    assert analyzer is not None


def test_extract_structure_pattern_derivative():
    """Test extracting structure for derivative problem"""
    analyzer = StructuralAnalyzer()

    content = {
        "stimulus": "Find the derivative of f(x) = 3x^2 + 5x - 2",
        "options": ["6x + 5", "3x + 5", "6x", "3x"]
    }

    structure = analyzer.extract_structure_pattern(content)

    assert structure["problem_type"] == "derivative"
    assert structure["answer_format"] == "multiple_choice"
    assert "N" in structure["pattern"]  # Numbers replaced with N


def test_extract_structure_pattern_integral():
    """Test extracting structure for integral problem"""
    analyzer = StructuralAnalyzer()

    content = {
        "stimulus": "Evaluate the integral of 2x dx",
        "options": ["x^2 + C", "2x + C", "x + C", "2"]
    }

    structure = analyzer.extract_structure_pattern(content)

    assert structure["problem_type"] == "integral"
    assert structure["answer_format"] == "multiple_choice"


def test_extract_structure_pattern_limit():
    """Test extracting structure for limit problem"""
    analyzer = StructuralAnalyzer()

    content = {
        "stimulus": "Find the limit as x approaches 0 of sin(x)/x",
        "options": ["1", "0", "∞", "undefined"]
    }

    structure = analyzer.extract_structure_pattern(content)

    assert structure["problem_type"] == "limit"


def test_extract_structure_pattern_optimization():
    """Test extracting structure for optimization problem"""
    analyzer = StructuralAnalyzer()

    content = {
        "stimulus": "Find the maximum value of f(x) = -x^2 + 4x",
        "options": ["4", "2", "0", "-4"]
    }

    structure = analyzer.extract_structure_pattern(content)

    assert structure["problem_type"] == "optimization"


def test_extract_structure_pattern_function_replacement():
    """Test that function names are replaced with generics"""
    analyzer = StructuralAnalyzer()

    content = {
        "stimulus": "Given f(x) = x^2 and g(x) = 2x, find h(x) = f(g(x))",
        "options": ["4x^2", "2x^2", "x^2 + 2x", "4x"]
    }

    structure = analyzer.extract_structure_pattern(content)

    pattern = structure["pattern"]

    # f(x), g(x), h(x) should be replaced with F(x), G(x), H(x)
    assert "F(x)" in pattern or "f" not in pattern.lower()


def test_extract_structure_pattern_number_replacement():
    """Test that numbers are replaced with N"""
    analyzer = StructuralAnalyzer()

    content = {
        "stimulus": "If f(3) = 7 and f(5) = 11, what is f(4)?",
        "options": ["9", "8", "10", "12"]
    }

    structure = analyzer.extract_structure_pattern(content)

    pattern = structure["pattern"]

    # Numbers should be replaced (though some might remain in special contexts)
    assert "N" in pattern


def test_compare_structures_identical():
    """Test comparing identical structures"""
    analyzer = StructuralAnalyzer()

    structure1 = {
        "pattern": "find the derivative of Fx Nx",
        "problem_type": "derivative",
        "answer_format": "multiple_choice",
        "question_structure": ["find_instruction", "question_mark"]
    }

    structure2 = structure1.copy()

    similarity = analyzer.compare_structures(structure1, structure2)

    assert similarity == 1.0


def test_compare_structures_same_type_different_pattern():
    """Test comparing structures with same type but different pattern"""
    analyzer = StructuralAnalyzer()

    structure1 = {
        "pattern": "find derivative of Nx^N",
        "problem_type": "derivative",
        "answer_format": "multiple_choice",
        "question_structure": ["find_instruction"]
    }

    structure2 = {
        "pattern": "calculate derivative of sin(Nx)",
        "problem_type": "derivative",
        "answer_format": "multiple_choice",
        "question_structure": ["find_instruction"]
    }

    similarity = analyzer.compare_structures(structure1, structure2)

    # Should have some similarity (same type) but not perfect
    assert 0.3 < similarity < 0.9


def test_compare_structures_completely_different():
    """Test comparing completely different structures"""
    analyzer = StructuralAnalyzer()

    structure1 = {
        "pattern": "find derivative",
        "problem_type": "derivative",
        "answer_format": "multiple_choice",
        "question_structure": []
    }

    structure2 = {
        "pattern": "evaluate limit",
        "problem_type": "limit",
        "answer_format": "free_response",
        "question_structure": []
    }

    similarity = analyzer.compare_structures(structure1, structure2)

    # Should have low similarity
    assert similarity < 0.5


def test_identify_problem_type_derivative():
    """Test problem type identification for derivatives"""
    analyzer = StructuralAnalyzer()

    assert analyzer._identify_problem_type("Find the derivative of x^2") == "derivative"
    assert analyzer._identify_problem_type("Differentiate f(x) = sin(x)") == "derivative"
    assert analyzer._identify_problem_type("What is d/dx of x^3?") == "derivative"


def test_identify_problem_type_integral():
    """Test problem type identification for integrals"""
    analyzer = StructuralAnalyzer()

    assert analyzer._identify_problem_type("Evaluate the integral of 2x") == "integral"
    assert analyzer._identify_problem_type("Find ∫x^2 dx") == "integral"
    assert analyzer._identify_problem_type("What is the antiderivative?") == "integral"


def test_identify_problem_type_limit():
    """Test problem type identification for limits"""
    analyzer = StructuralAnalyzer()

    assert analyzer._identify_problem_type("Find the limit as x approaches 0") == "limit"
    assert analyzer._identify_problem_type("Calculate lim x→∞") == "limit"


def test_identify_problem_type_other():
    """Test problem type identification for other types"""
    analyzer = StructuralAnalyzer()

    assert analyzer._identify_problem_type("What is 2 + 2?") == "other"
    assert analyzer._identify_problem_type("Define continuity") == "other"


def test_identify_answer_format():
    """Test answer format identification"""
    analyzer = StructuralAnalyzer()

    # Multiple choice
    content_mc = {"stimulus": "Question?", "options": ["A", "B", "C", "D"]}
    assert analyzer._identify_answer_format(content_mc) == "multiple_choice"

    # Free response
    content_fr = {"stimulus": "Question?", "answer": "42"}
    assert analyzer._identify_answer_format(content_fr) == "free_response"

    # Unknown
    content_unknown = {"stimulus": "Question?"}
    assert analyzer._identify_answer_format(content_unknown) == "unknown"


# ============================================================================
# Tests: Phase 4 - SourceSpecificChecker
# ============================================================================

def test_source_specific_checker_initialization():
    """Test SourceSpecificChecker initialization"""
    checker = SourceSpecificChecker()

    assert checker.thresholds[SourceType.AP_RELEASED] == 0.75  # Strictest
    assert checker.thresholds[SourceType.TEXTBOOK] == 0.85
    assert checker.thresholds[SourceType.INTERNAL] == 0.90  # Least strict


def test_check_source_ap_released_critical():
    """Test critical risk for AP released exams"""
    checker = SourceSpecificChecker()

    content = {"stimulus": "Question"}
    matched = {"stimulus": "Matched"}

    result = checker.check_source(
        similarity_score=0.90,  # Very high
        source_type=SourceType.AP_RELEASED,
        content=content,
        matched_content=matched
    )

    assert result["risk_level"] == RiskLevel.CRITICAL
    assert result["recommendation"] == "REJECT"
    assert result["legal_review_required"] == True


def test_check_source_ap_released_high():
    """Test high risk for AP released exams"""
    checker = SourceSpecificChecker()

    content = {"stimulus": "Question"}
    matched = {"stimulus": "Matched"}

    result = checker.check_source(
        similarity_score=0.78,  # Above threshold (0.75)
        source_type=SourceType.AP_RELEASED,
        content=content,
        matched_content=matched
    )

    assert result["risk_level"] == RiskLevel.HIGH
    assert result["recommendation"] == "REVIEW_REQUIRED"
    assert result["legal_review_required"] == True


def test_check_source_textbook_high():
    """Test high risk for textbook content"""
    checker = SourceSpecificChecker()

    content = {"stimulus": "Question"}
    matched = {"stimulus": "Matched"}

    result = checker.check_source(
        similarity_score=0.88,  # Above threshold (0.85)
        source_type=SourceType.TEXTBOOK,
        content=content,
        matched_content=matched
    )

    assert result["risk_level"] == RiskLevel.HIGH
    assert result["recommendation"] == "REVIEW_REQUIRED"
    assert result["legal_review_required"] == False  # Not AP


def test_check_source_internal_high():
    """Test high risk for internal content"""
    checker = SourceSpecificChecker()

    content = {"stimulus": "Question"}
    matched = {"stimulus": "Matched"}

    result = checker.check_source(
        similarity_score=0.92,  # Above threshold (0.90)
        source_type=SourceType.INTERNAL,
        content=content,
        matched_content=matched
    )

    assert result["risk_level"] == RiskLevel.HIGH
    assert result["recommendation"] == "REVIEW_REQUIRED"


def test_check_source_below_threshold():
    """Test low risk below threshold"""
    checker = SourceSpecificChecker()

    content = {"stimulus": "Question"}
    matched = {"stimulus": "Matched"}

    result = checker.check_source(
        similarity_score=0.60,  # Below all thresholds
        source_type=SourceType.AP_RELEASED,
        content=content,
        matched_content=matched
    )

    assert result["risk_level"] == RiskLevel.LOW
    assert result["recommendation"] == "APPROVE"


def test_check_source_standard_problem_type():
    """Test standard problem type is approved"""
    checker = SourceSpecificChecker()

    # Both contain "chain rule" - standard pattern
    content = {"stimulus": "Use the chain rule to find the derivative"}
    matched = {"stimulus": "Apply chain rule to differentiate"}

    result = checker.check_source(
        similarity_score=0.78,  # Close to threshold
        source_type=SourceType.TEXTBOOK,
        content=content,
        matched_content=matched
    )

    # Should recognize as standard problem type
    assert result["recommendation"] == "APPROVE"
    assert "Standard problem type" in result["reason"]


def test_is_standard_problem_type_chain_rule():
    """Test detecting chain rule as standard"""
    checker = SourceSpecificChecker()

    content1 = {"stimulus": "Use the chain rule"}
    content2 = {"stimulus": "Apply chain rule"}

    assert checker._is_standard_problem_type(content1, content2) == True


def test_is_standard_problem_type_product_rule():
    """Test detecting product rule as standard"""
    checker = SourceSpecificChecker()

    content1 = {"stimulus": "Use the product rule"}
    content2 = {"stimulus": "Apply product rule"}

    assert checker._is_standard_problem_type(content1, content2) == True


def test_is_standard_problem_type_not_standard():
    """Test detecting non-standard problems"""
    checker = SourceSpecificChecker()

    content1 = {"stimulus": "Solve this unique problem"}
    content2 = {"stimulus": "Calculate this specific case"}

    assert checker._is_standard_problem_type(content1, content2) == False


# ============================================================================
# Tests: Phase 5 - RiskAssessor
# ============================================================================

def test_risk_assessor_initialization():
    """Test RiskAssessor initialization"""
    assessor = RiskAssessor()
    assert assessor is not None


def test_assess_risk_exact_match():
    """Test risk assessment for exact match"""
    assessor = RiskAssessor()

    risk = assessor.assess_risk(
        exact_matches={"found": True, "matches": [{"score": 1.0}]},
        semantic_max_similarity=0.0,
        structural_max_similarity=0.0,
        source_checks=[],
        content={}
    )

    assert risk.copyright_risk == RiskLevel.CRITICAL
    assert risk.originality_score == 0.0
    assert risk.recommendation == "REJECT"
    assert risk.requires_review == True
    assert risk.legal_review_required == True


def test_assess_risk_high_semantic_similarity():
    """Test risk assessment for high semantic similarity"""
    assessor = RiskAssessor()

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.92,  # High (≥0.80)
        structural_max_similarity=0.0,
        source_checks=[],
        content={}
    )

    assert risk.copyright_risk == RiskLevel.HIGH
    assert risk.originality_score == 0.08  # 1.0 - 0.92
    assert risk.recommendation == "REJECT"
    assert risk.requires_review == True


def test_assess_risk_very_high_semantic_triggers_legal():
    """Test that very high semantic similarity triggers legal review"""
    assessor = RiskAssessor()

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.95,  # Very high (≥0.90)
        structural_max_similarity=0.0,
        source_checks=[],
        content={}
    )

    assert risk.copyright_risk == RiskLevel.HIGH
    assert risk.legal_review_required == True


def test_assess_risk_high_structural_similarity():
    """Test risk assessment for high structural similarity"""
    assessor = RiskAssessor()

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.50,
        structural_max_similarity=0.88,  # High (≥0.85)
        source_checks=[],
        content={}
    )

    assert risk.copyright_risk == RiskLevel.MEDIUM
    assert risk.recommendation == "REVIEW_REQUIRED"
    assert risk.requires_review == True


def test_assess_risk_moderate_similarity():
    """Test risk assessment for moderate similarity"""
    assessor = RiskAssessor()

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.65,  # Moderate (0.60-0.80)
        structural_max_similarity=0.50,
        source_checks=[],
        content={}
    )

    assert risk.copyright_risk == RiskLevel.LOW
    assert risk.recommendation == "APPROVE"
    assert risk.requires_review == False


def test_assess_risk_low_similarity():
    """Test risk assessment for low similarity"""
    assessor = RiskAssessor()

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.35,  # Low
        structural_max_similarity=0.40,
        source_checks=[],
        content={}
    )

    assert risk.copyright_risk == RiskLevel.NEGLIGIBLE
    assert risk.recommendation == "APPROVE"
    assert risk.requires_review == False


def test_assess_risk_critical_source_check():
    """Test risk assessment with critical source check"""
    assessor = RiskAssessor()

    source_checks = [
        {"risk_level": RiskLevel.CRITICAL, "legal_review_required": True}
    ]

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.50,
        structural_max_similarity=0.40,
        source_checks=source_checks,
        content={}
    )

    assert risk.copyright_risk == RiskLevel.CRITICAL
    assert risk.recommendation == "REJECT"
    assert risk.legal_review_required == True


def test_assess_risk_high_source_check():
    """Test risk assessment with high risk source check"""
    assessor = RiskAssessor()

    source_checks = [
        {"risk_level": RiskLevel.HIGH, "legal_review_required": False}
    ]

    risk = assessor.assess_risk(
        exact_matches={"found": False},
        semantic_max_similarity=0.50,
        structural_max_similarity=0.40,
        source_checks=source_checks,
        content={}
    )

    assert risk.copyright_risk == RiskLevel.HIGH
    assert risk.recommendation == "REVIEW_REQUIRED"


def test_extract_evidence():
    """Test extracting evidence from content"""
    assessor = RiskAssessor()

    content = {
        "stimulus": "Find the derivative of 3x^2 + 5x - 2",
        "options": ["6x + 5", "3x + 5", "6x", "3x"]
    }

    matches = []  # No matches for this test

    evidence = assessor.extract_evidence(content, matches)

    assert isinstance(evidence, Evidence)
    assert len(evidence.unique_elements) > 0
    assert len(evidence.common_elements) > 0

    # Should detect unique coefficients
    assert any("coefficient" in elem.lower() for elem in evidence.unique_elements)

    # Should detect common elements
    assert any("derivative" in elem.lower() for elem in evidence.common_elements)


def test_extract_evidence_multiple_choice():
    """Test evidence extraction detects multiple choice format"""
    assessor = RiskAssessor()

    content = {
        "stimulus": "Question?",
        "options": ["A", "B", "C", "D"]
    }

    evidence = assessor.extract_evidence(content, [])

    # Should recognize multiple choice as common
    assert any("multiple choice" in elem.lower() for elem in evidence.common_elements)


def test_extract_evidence_find_instruction():
    """Test evidence extraction detects 'find' instruction"""
    assessor = RiskAssessor()

    content = {
        "stimulus": "Find the value of x"
    }

    evidence = assessor.extract_evidence(content, [])

    # Should recognize 'find' as common
    assert any("find" in elem.lower() for elem in evidence.common_elements)


# ============================================================================
# Tests: Integration of All Phases
# ============================================================================

def test_all_phases_low_risk_scenario():
    """Integration test: all phases agree on low risk"""
    # Setup components
    exact_matcher = ExactMatchDetector()
    structural_analyzer = StructuralAnalyzer()
    source_checker = SourceSpecificChecker()
    risk_assessor = RiskAssessor()

    # No exact match
    exact_matches = {"found": False, "matches": []}

    # Low semantic and structural similarity
    semantic_max = 0.45
    structural_max = 0.50

    # No concerning source checks
    source_checks = []

    # Assess risk
    risk = risk_assessor.assess_risk(
        exact_matches=exact_matches,
        semantic_max_similarity=semantic_max,
        structural_max_similarity=structural_max,
        source_checks=source_checks,
        content={}
    )

    assert risk.copyright_risk == RiskLevel.NEGLIGIBLE
    assert risk.recommendation == "APPROVE"


def test_all_phases_high_risk_scenario():
    """Integration test: all phases agree on high risk"""
    # Setup components
    risk_assessor = RiskAssessor()

    # Exact match found
    exact_matches = {"found": True, "matches": [{"score": 1.0}]}

    # High similarities (though exact match alone should trigger critical)
    semantic_max = 0.95
    structural_max = 0.90

    # Critical source check
    source_checks = [{"risk_level": RiskLevel.CRITICAL}]

    # Assess risk
    risk = risk_assessor.assess_risk(
        exact_matches=exact_matches,
        semantic_max_similarity=semantic_max,
        structural_max_similarity=structural_max,
        source_checks=source_checks,
        content={}
    )

    assert risk.copyright_risk == RiskLevel.CRITICAL
    assert risk.recommendation == "REJECT"
    assert risk.requires_review == True
    assert risk.legal_review_required == True
