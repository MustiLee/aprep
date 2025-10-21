"""Unit tests for CED Alignment Validator agent"""

import pytest
from src.agents.ced_alignment_validator import (
    CEDAlignmentValidator,
    AlignmentResult,
    AlignmentIssue
)
from src.agents.taxonomy_manager import (
    TaxonomyManager,
    Course,
    Unit,
    Topic,
    LearningObjective
)


@pytest.fixture
def taxonomy_manager(tmp_path):
    """Create taxonomy manager with test course"""
    manager = TaxonomyManager(str(tmp_path / "taxonomy"))

    # Create test course
    course = Course(
        id="ap_calculus_bc",
        title="AP Calculus BC",
        code="AP CALCULUS BC"
    )

    # Create unit
    unit = Unit(
        code="Unit 1",
        title="Limits and Continuity"
    )

    # Create topic
    topic = Topic(
        code="1.1",
        title="Limits",
        keywords=["limit", "continuity", "function"]
    )

    # Create learning objectives
    lo1 = LearningObjective(
        code="LIM-1.A",
        description="Calculate limits of functions",
        keywords=["limit", "calculate", "function"],
        difficulty_level=2
    )

    lo2 = LearningObjective(
        code="LIM-1.B",
        description="Determine continuity of functions",
        keywords=["continuity", "function", "continuous"],
        difficulty_level=3
    )

    topic.learning_objectives = [lo1, lo2]
    unit.topics = [topic]
    course.units = [unit]

    manager.save_course(course)

    return manager


@pytest.fixture
def validator(taxonomy_manager):
    """Create validator with test taxonomy"""
    return CEDAlignmentValidator(
        taxonomy_manager=taxonomy_manager,
        min_alignment_score=0.90
    )


class TestCEDAlignmentValidator:
    """Test CED Alignment Validator functionality"""

    def test_initialization(self, validator):
        """Test validator initialization"""
        assert validator is not None
        assert validator.min_alignment_score == 0.90
        assert validator.total_validations == 0

    def test_validate_fully_aligned_question(self, validator):
        """Test validation of fully aligned question"""
        question = {
            "question_id": "q001",
            "lo_code": "LIM-1.A",
            "topic_id": "1.1",
            "unit_id": "Unit 1",
            "text": "Calculate the limit of the function as x approaches 2"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        assert isinstance(result, AlignmentResult)
        assert result.is_aligned is True
        assert result.alignment_score >= 0.90
        assert result.lo_matched is True
        assert result.topic_matched is True
        assert result.unit_matched is True
        assert result.matched_lo_code == "LIM-1.A"
        assert len(result.issues) == 0

    def test_validate_missing_lo(self, validator):
        """Test validation with missing LO code"""
        question = {
            "question_id": "q002",
            "topic_id": "1.1",
            "unit_id": "Unit 1",
            "text": "Calculate the limit"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        assert result.is_aligned is False
        assert result.lo_matched is False
        assert len(result.issues) > 0
        assert any(i.issue_type == "missing_lo" for i in result.issues)
        assert any(i.severity == "critical" for i in result.issues)

    def test_validate_invalid_lo_code(self, validator):
        """Test validation with invalid LO code"""
        question = {
            "question_id": "q003",
            "lo_code": "INVALID-CODE",
            "topic_id": "1.1",
            "text": "Calculate something"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        assert result.is_aligned is False
        assert result.lo_matched is False
        assert any(
            i.issue_type == "missing_lo" and "not found" in i.description.lower()
            for i in result.issues
        )

    def test_validate_wrong_topic(self, validator, taxonomy_manager):
        """Test validation with LO in wrong topic"""
        # Create another topic without LIM-1.A
        course = taxonomy_manager.load_course("ap_calculus_bc")

        new_topic = Topic(
            code="1.2",
            title="Derivatives",
            keywords=["derivative"]
        )

        course.units[0].topics.append(new_topic)
        taxonomy_manager.save_course(course)

        question = {
            "question_id": "q004",
            "lo_code": "LIM-1.A",
            "topic_id": "1.2",  # Wrong topic
            "text": "Calculate the limit"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        # Should still match LO but warn about wrong topic
        assert result.lo_matched is True
        assert any(i.issue_type == "wrong_topic" for i in result.issues)

    def test_validate_weak_content_alignment(self, validator):
        """Test validation with weak content alignment"""
        question = {
            "question_id": "q005",
            "lo_code": "LIM-1.A",
            "topic_id": "1.1",
            "text": "The quick brown fox jumps over the lazy dog"  # Unrelated content
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        assert any(i.issue_type == "weak_alignment" for i in result.issues)

    def test_content_alignment_scoring(self, validator):
        """Test content alignment scoring"""
        # Get LO
        lo = validator.taxonomy_manager.get_learning_objective("ap_calculus_bc", "LIM-1.A")

        # Good alignment
        good_text = "Calculate the limit of the function"
        good_score = validator._check_content_alignment(good_text, lo)
        assert good_score > 0.3

        # Poor alignment
        poor_text = "The weather is nice today"
        poor_score = validator._check_content_alignment(poor_text, lo)
        assert poor_score < 0.3

    def test_alignment_score_calculation(self, validator):
        """Test alignment score calculation"""
        # Perfect alignment
        score = validator._calculate_alignment_score(
            lo_matched=True,
            topic_matched=True,
            unit_matched=True,
            content_aligned=True,
            issue_count=0
        )
        assert score == 1.0

        # Only LO matched
        score = validator._calculate_alignment_score(
            lo_matched=True,
            topic_matched=False,
            unit_matched=False,
            content_aligned=False,
            issue_count=0
        )
        assert score == 0.4

        # With issues penalty
        score = validator._calculate_alignment_score(
            lo_matched=True,
            topic_matched=True,
            unit_matched=True,
            content_aligned=True,
            issue_count=3
        )
        assert score < 1.0

    def test_validate_batch(self, validator):
        """Test batch validation"""
        questions = [
            {
                "question_id": "q001",
                "lo_code": "LIM-1.A",
                "topic_id": "1.1",
                "unit_id": "Unit 1",
                "text": "Calculate the limit of the function as x approaches infinity"
            },
            {
                "question_id": "q002",
                "lo_code": "LIM-1.B",
                "topic_id": "1.1",
                "unit_id": "Unit 1",
                "text": "Determine if the function is continuous at the given point"
            },
            {
                "question_id": "q003",
                "lo_code": "INVALID",
                "topic_id": "1.1",
                "text": "Some question"
            }
        ]

        batch_result = validator.validate_batch(questions, "ap_calculus_bc")

        assert batch_result["total_questions"] == 3
        assert batch_result["aligned_count"] == 2
        assert batch_result["misaligned_count"] == 1
        assert batch_result["alignment_rate"] == pytest.approx(2/3)
        assert len(batch_result["results"]) == 3

    def test_check_curriculum_coverage(self, validator):
        """Test curriculum coverage check"""
        questions = [
            {"question_id": "q001", "lo_code": "LIM-1.A"},
            {"question_id": "q002", "lo_code": "LIM-1.A"},  # Duplicate
        ]

        coverage = validator.check_curriculum_coverage(questions, "ap_calculus_bc")

        assert coverage["total_los"] == 2  # LIM-1.A and LIM-1.B
        assert coverage["covered_los"] == 1  # Only LIM-1.A
        assert coverage["uncovered_los"] == 1  # LIM-1.B not covered
        assert coverage["coverage_ratio"] == 0.5
        assert "LIM-1.B" in coverage["uncovered_lo_codes"]

    def test_full_curriculum_coverage(self, validator):
        """Test full curriculum coverage"""
        questions = [
            {"question_id": "q001", "lo_code": "LIM-1.A"},
            {"question_id": "q002", "lo_code": "LIM-1.B"},
        ]

        coverage = validator.check_curriculum_coverage(questions, "ap_calculus_bc")

        assert coverage["coverage_ratio"] == 1.0
        assert coverage["uncovered_los"] == 0

    def test_get_statistics(self, validator):
        """Test statistics tracking"""
        # Validate some questions
        validator.validate_question({
            "lo_code": "LIM-1.A",
            "topic_id": "1.1",
            "unit_id": "Unit 1",
            "text": "Calculate the limit of the function as x approaches 2"
        }, "ap_calculus_bc")

        validator.validate_question({
            "lo_code": "INVALID",
            "topic_id": "1.1",
            "text": "Invalid question"
        }, "ap_calculus_bc")

        stats = validator.get_statistics()

        assert stats["total_validations"] == 2
        assert stats["total_aligned"] == 1
        assert stats["total_misaligned"] == 1
        assert stats["alignment_rate"] == 0.5
        assert stats["min_alignment_score"] == 0.90

    def test_issue_severity_levels(self, validator):
        """Test different issue severity levels"""
        question = {
            "question_id": "q001",
            "lo_code": "INVALID",  # Critical
            "topic_id": "1.1",
            "unit_id": "WRONG_UNIT",  # Warning
            "text": "Some text"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        critical_issues = [i for i in result.issues if i.severity == "critical"]
        warning_issues = [i for i in result.issues if i.severity == "warning"]

        assert len(critical_issues) > 0
        assert len(warning_issues) > 0

    def test_alignment_result_metadata(self, validator):
        """Test alignment result metadata"""
        question = {
            "question_id": "test_q",
            "lo_code": "LIM-1.A",
            "topic_id": "1.1",
            "text": "Test question"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        assert "question_id" in result.metadata
        assert "course_id" in result.metadata
        assert result.metadata["question_id"] == "test_q"
        assert result.metadata["course_id"] == "ap_calculus_bc"

    def test_empty_question_text(self, validator):
        """Test validation with empty question text"""
        question = {
            "question_id": "q001",
            "lo_code": "LIM-1.A",
            "topic_id": "1.1",
            "text": ""
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        # Should still validate LO and topic, but content alignment may be weak
        assert result.lo_matched is True
        assert result.topic_matched is True

    def test_missing_all_identifiers(self, validator):
        """Test validation with missing all identifiers"""
        question = {
            "question_id": "q001",
            "text": "Some question text"
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        assert result.is_aligned is False
        assert result.alignment_score < 0.90
        assert len(result.issues) >= 1  # At least missing LO

    def test_validator_with_custom_threshold(self, taxonomy_manager):
        """Test validator with custom alignment threshold"""
        validator = CEDAlignmentValidator(
            taxonomy_manager=taxonomy_manager,
            min_alignment_score=0.75
        )

        assert validator.min_alignment_score == 0.75

        question = {
            "lo_code": "LIM-1.A",
            "topic_id": "1.1",
            "unit_id": "Unit 1",
            "text": "Calculate the limit"  # Better alignment
        }

        result = validator.validate_question(question, "ap_calculus_bc")

        # With lower threshold and better content, should have decent score
        assert result.alignment_score >= 0.65


class TestAlignmentIssue:
    """Test AlignmentIssue model"""

    def test_issue_creation(self):
        """Test creating an alignment issue"""
        issue = AlignmentIssue(
            issue_type="missing_lo",
            severity="critical",
            description="LO code not found"
        )

        assert issue.issue_type == "missing_lo"
        assert issue.severity == "critical"
        assert issue.description == "LO code not found"

    def test_issue_with_suggested_fix(self):
        """Test issue with suggested fix"""
        issue = AlignmentIssue(
            issue_type="wrong_topic",
            severity="warning",
            description="LO not in topic",
            suggested_fix="Move to correct topic",
            affected_field="topic_id"
        )

        assert issue.suggested_fix == "Move to correct topic"
        assert issue.affected_field == "topic_id"


class TestIntegration:
    """Integration tests"""

    def test_end_to_end_validation_workflow(self, validator):
        """Test complete validation workflow"""
        # Create questions
        questions = [
            {
                "question_id": "q001",
                "lo_code": "LIM-1.A",
                "topic_id": "1.1",
                "unit_id": "Unit 1",
                "text": "Calculate the limit of the function f(x) as x approaches 3"
            },
            {
                "question_id": "q002",
                "lo_code": "LIM-1.B",
                "topic_id": "1.1",
                "unit_id": "Unit 1",
                "text": "Determine if the function is continuous at x = 5"
            }
        ]

        # Validate batch
        batch_result = validator.validate_batch(questions, "ap_calculus_bc")

        assert batch_result["total_questions"] == 2
        assert batch_result["aligned_count"] == 2
        assert batch_result["alignment_rate"] == 1.0

        # Check coverage
        coverage = validator.check_curriculum_coverage(questions, "ap_calculus_bc")

        assert coverage["coverage_ratio"] == 1.0

        # Check statistics
        stats = validator.get_statistics()

        assert stats["total_validations"] == 2
        assert stats["alignment_rate"] == 1.0
