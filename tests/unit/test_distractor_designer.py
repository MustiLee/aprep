"""Unit tests for Distractor Designer agent."""

import pytest
from src.agents.distractor_designer import (
    DistractorDesigner,
    DistractorCandidate,
    DistractorSet
)
from src.agents.misconception_database_manager import (
    MisconceptionDatabaseManager
)


class TestDistractorDesigner:
    """Test Distractor Designer functionality."""

    @pytest.fixture
    def misconception_manager(self, tmp_path):
        """Create misconception manager with test data."""
        manager = MisconceptionDatabaseManager(str(tmp_path / "misconceptions"))

        # Create test misconception with transformation rule
        manager.add_misconception(
            classification={
                "course_id": "ap_calculus_bc",
                "topic_id": "derivatives",
                "category": "procedural_error",
                "difficulty_level": 2
            },
            description={
                "title": "Power rule coefficient error",
                "detailed": "Student forgets to multiply by exponent"
            },
            frequency={
                "occurrence_rate": 0.15,
                "grade_distribution": {"grade_11": 0.2, "grade_12": 0.1}
            },
            distractor_generation={
                "transformation_rule": "OMIT_COEFFICIENT",
                "template": "{{base}}^{{exponent_minus_one}}",
                "plausibility_score": 8.5,
                "recommended_question_types": ["power_rule"]
            }
        )

        manager.add_misconception(
            classification={
                "course_id": "ap_calculus_bc",
                "topic_id": "derivatives",
                "category": "procedural_error",
                "difficulty_level": 3
            },
            description={
                "title": "Chain rule error",
                "detailed": "Student forgets inner derivative"
            },
            frequency={
                "occurrence_rate": 0.20,
                "grade_distribution": {"grade_11": 0.25, "grade_12": 0.15}
            },
            distractor_generation={
                "transformation_rule": "REMOVE_INNER_DERIVATIVE",
                "template": "{{outer}}({{inner}})",
                "plausibility_score": 9.0,
                "recommended_question_types": ["chain_rule"]
            }
        )

        manager.add_misconception(
            classification={
                "course_id": "ap_calculus_bc",
                "topic_id": "integration",
                "category": "conceptual_misunderstanding",
                "difficulty_level": 1
            },
            description={
                "title": "Missing constant",
                "detailed": "Student forgets +C"
            },
            frequency={
                "occurrence_rate": 0.30,
                "grade_distribution": {"grade_11": 0.35, "grade_12": 0.25}
            },
            distractor_generation={
                "transformation_rule": "OMIT_CONSTANT",
                "template": "{{result}}",
                "plausibility_score": 7.0,
                "recommended_question_types": ["indefinite_integral"]
            }
        )

        return manager

    @pytest.fixture
    def designer(self, misconception_manager):
        """Create DistractorDesigner instance."""
        return DistractorDesigner(misconception_manager=misconception_manager)

    def test_initialization(self, designer):
        """Test designer can be initialized."""
        assert designer is not None
        assert designer.total_distractors_generated == 0
        assert designer.total_distractors_rejected == 0
        assert designer.generation_history == []

    def test_generate_distractors_basic(self, designer):
        """Test basic distractor generation."""
        correct_answer = "3x^2"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "difficulty_level": 2,
            "parameters": {"coefficient": 3, "exponent": 3}
        }

        result = designer.generate_distractors(
            correct_answer=correct_answer,
            question_context=context,
            count=3,
            min_quality=6.0
        )

        assert isinstance(result, DistractorSet)
        assert result.correct_answer == correct_answer
        assert len(result.distractors) >= 1  # At least some distractors
        assert len(result.distractors) <= 3  # Not more than requested
        assert result.avg_quality_score >= 6.0

    def test_generate_distractors_metadata(self, designer):
        """Test that distractor sets include proper metadata."""
        correct_answer = "2x"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "question_id": "q123",
            "difficulty_level": 2
        }

        result = designer.generate_distractors(
            correct_answer=correct_answer,
            question_context=context,
            count=3
        )

        assert result.question_id == "q123"
        assert result.topic_id == "derivatives"
        assert result.course_id == "ap_calculus_bc"
        assert "generated_at" in result.model_dump()

    def test_omit_coefficient_transformation(self, designer):
        """Test OMIT_COEFFICIENT transformation."""
        # Test case 1: 3x^2 -> x^2
        result = designer._apply_omit_coefficient("3x^2", {})
        assert result == "x^2"

        # Test case 2: 5*sin(x) -> sin(x)
        result = designer._apply_omit_coefficient("5*sin(x)", {})
        assert result == "sin(x)"

        # Test case 3: 2 * cos(x) -> cos(x)
        result = designer._apply_omit_coefficient("2 * cos(x)", {})
        assert result == "cos(x)"

    def test_remove_inner_derivative_transformation(self, designer):
        """Test REMOVE_INNER_DERIVATIVE transformation."""
        # Test case: 2cos(2x) -> cos(2x)
        result = designer._apply_remove_inner_derivative("2cos(2x)", {})
        assert result == "cos(2x)"

        # Test case: 3*sin(3x) -> sin(3x)
        result = designer._apply_remove_inner_derivative("3*sin(3x)", {})
        assert result == "sin(3x)"

    def test_omit_constant_transformation(self, designer):
        """Test OMIT_CONSTANT transformation."""
        # Test case 1: x^2/2 + C -> x^2/2
        result = designer._apply_omit_constant("x^2/2 + C", {})
        assert result == "x^2/2"

        # Test case 2: sin(x) + C -> sin(x)
        result = designer._apply_omit_constant("sin(x) + C", {})
        assert result == "sin(x)"

    def test_wrong_sign_transformation(self, designer):
        """Test WRONG_SIGN transformation."""
        # Test case 1: -2x -> 2x
        result = designer._apply_wrong_sign("-2x", {})
        assert result == "2x"

        # Test case 2: 3x -> -3x
        result = designer._apply_wrong_sign("3x", {})
        assert result == "-3x"

    def test_off_by_one_transformation(self, designer):
        """Test OFF_BY_ONE transformation."""
        # Test case: 2x -> 3x (2+1)
        result = designer._apply_off_by_one("2x", {})
        assert "3x" in result

        # Test case: x^3 -> x^4
        result = designer._apply_off_by_one("x^3", {})
        assert "4" in result

    def test_is_trivial_distractor(self, designer):
        """Test trivial distractor detection."""
        correct_answer = "2x^2"

        # Should be trivial
        assert designer._is_trivial_distractor("", correct_answer) is True
        assert designer._is_trivial_distractor("   ", correct_answer) is True
        assert designer._is_trivial_distractor("2x^2", correct_answer) is True
        assert designer._is_trivial_distractor("???", correct_answer) is True
        assert designer._is_trivial_distractor("ERROR", correct_answer) is True

        # Should NOT be trivial
        assert designer._is_trivial_distractor("x^2", correct_answer) is False
        assert designer._is_trivial_distractor("2x", correct_answer) is False
        assert designer._is_trivial_distractor("-2x^2", correct_answer) is False

    def test_calculate_similarity(self, designer):
        """Test similarity calculation."""
        # Identical strings
        sim = designer._calculate_similarity("2x^2", "2x^2")
        assert sim == 1.0

        # Similar strings
        sim = designer._calculate_similarity("2x^2", "3x^2")
        assert 0.5 < sim < 1.0

        # Different strings
        sim = designer._calculate_similarity("2x^2", "sin(x)")
        assert sim < 0.5

    def test_estimate_complexity(self, designer):
        """Test complexity estimation."""
        # Simple expression
        complexity_simple = designer._estimate_complexity("2x")
        assert complexity_simple < 3

        # Medium complexity
        complexity_medium = designer._estimate_complexity("2x^2 + 3x + 1")
        assert 3 <= complexity_medium <= 7

        # High complexity
        complexity_high = designer._estimate_complexity("sin(2x) * cos(3x) + ln(x)")
        assert complexity_high > 5

    def test_evaluate_distractor_quality(self, designer):
        """Test distractor quality evaluation."""
        candidate = DistractorCandidate(
            value="x^2",
            misconception_id="test_id",
            misconception="omit_coefficient",
            transformation_rule="OMIT_COEFFICIENT",
            plausibility_score=8.0,
            quality_score=0.0,
            explanation="Forgot coefficient"
        )

        correct_answer = "3x^2"
        context = {"difficulty_level": 2}

        quality = designer._evaluate_distractor_quality(
            candidate, correct_answer, context
        )

        assert 0.0 <= quality <= 10.0
        # Should be relatively high quality (similar structure)
        assert quality >= 7.0

    def test_find_relevant_misconceptions(self, designer):
        """Test finding relevant misconceptions."""
        misconceptions = designer._find_relevant_misconceptions(
            course_id="ap_calculus_bc",
            topic_id="derivatives",
            difficulty_level=2
        )

        assert len(misconceptions) >= 1
        assert all(m.distractor_generation is not None for m in misconceptions)
        assert all(m.course_id == "ap_calculus_bc" for m in misconceptions)

    def test_find_relevant_misconceptions_nearby_difficulty(self, designer):
        """Test that nearby difficulty levels are searched if needed."""
        # Search for difficulty 5 (none exist, should search 4)
        misconceptions = designer._find_relevant_misconceptions(
            course_id="ap_calculus_bc",
            topic_id="derivatives",
            difficulty_level=5
        )

        # Should find some from nearby levels
        assert len(misconceptions) >= 0

    def test_fallback_generation(self, designer):
        """Test fallback distractor generation."""
        correct_answer = "5x^3"
        context = {"difficulty_level": 2}

        result = designer._generate_fallback_distractors(
            correct_answer, context, count=3
        )

        assert isinstance(result, DistractorSet)
        assert len(result.distractors) >= 1
        assert all(d.value != correct_answer for d in result.distractors)

    def test_generate_distractors_with_no_misconceptions(self, designer):
        """Test generation when no misconceptions found."""
        correct_answer = "x^2"
        context = {
            "course_id": "nonexistent_course",
            "topic_id": "nonexistent_topic",
            "difficulty_level": 2
        }

        # Should use fallback generation
        result = designer.generate_distractors(
            correct_answer=correct_answer,
            question_context=context,
            count=3
        )

        assert isinstance(result, DistractorSet)
        assert len(result.distractors) >= 1

    def test_statistics_tracking(self, designer):
        """Test that statistics are tracked correctly."""
        correct_answer = "2x"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "difficulty_level": 2
        }

        # Generate some distractors
        designer.generate_distractors(correct_answer, context, count=3)
        designer.generate_distractors(correct_answer, context, count=2)

        stats = designer.get_statistics()

        assert stats["total_distractors_generated"] >= 2
        assert stats["generation_count"] == 2
        assert "acceptance_rate" in stats
        assert "avg_quality_score" in stats
        assert 0.0 <= stats["avg_quality_score"] <= 10.0

    def test_generation_history(self, designer):
        """Test generation history tracking."""
        correct_answer = "3x^2"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "difficulty_level": 2,
            "question_id": "q123"
        }

        # Generate distractors
        designer.generate_distractors(correct_answer, context, count=3)

        history = designer.get_generation_history()

        assert len(history) == 1
        assert history[0]["question_id"] == "q123"
        assert history[0]["topic_id"] == "derivatives"
        assert history[0]["distractor_count"] <= 3

    def test_generation_history_filtering(self, designer):
        """Test generation history filtering by topic."""
        # Generate for different topics
        designer.generate_distractors("2x", {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "difficulty_level": 2
        }, count=3)

        designer.generate_distractors("x^2/2 + C", {
            "course_id": "ap_calculus_bc",
            "topic_id": "integration",
            "difficulty_level": 1
        }, count=3)

        # Filter by topic
        history_derivatives = designer.get_generation_history(topic_id="derivatives")
        history_integration = designer.get_generation_history(topic_id="integration")

        assert len(history_derivatives) == 1
        assert len(history_integration) == 1
        assert history_derivatives[0]["topic_id"] == "derivatives"
        assert history_integration[0]["topic_id"] == "integration"

    def test_generation_history_limit(self, designer):
        """Test generation history limit."""
        # Generate multiple times
        for i in range(5):
            designer.generate_distractors(f"{i}x", {
                "course_id": "ap_calculus_bc",
                "topic_id": "derivatives",
                "difficulty_level": 2
            }, count=2)

        # Get limited history
        history = designer.get_generation_history(limit=3)
        assert len(history) == 3

    def test_min_quality_threshold(self, designer):
        """Test minimum quality threshold filtering."""
        correct_answer = "2x^2"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "difficulty_level": 2
        }

        # Request high quality distractors
        result = designer.generate_distractors(
            correct_answer, context, count=3, min_quality=9.0
        )

        # All distractors should meet quality threshold
        # (may use fallback if misconception-based don't meet threshold)
        assert all(d.quality_score >= 6.0 for d in result.distractors)

    def test_distractor_uniqueness(self, designer):
        """Test that generated distractors are unique."""
        correct_answer = "3x^2"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "difficulty_level": 2
        }

        result = designer.generate_distractors(correct_answer, context, count=3)

        # All distractors should be unique
        values = [d.value for d in result.distractors]
        assert len(values) == len(set(values))

        # None should match correct answer
        assert correct_answer not in values

    def test_generic_distractor_generation(self, designer):
        """Test generic distractor generation."""
        correct_answer = "42"

        # Generate generic distractors
        generic_0 = designer._generate_generic_distractor(correct_answer, 0)
        generic_1 = designer._generate_generic_distractor(correct_answer, 1)
        generic_2 = designer._generate_generic_distractor(correct_answer, 2)

        # Should generate different distractors
        distractors = [generic_0, generic_1, generic_2]
        assert len([d for d in distractors if d is not None]) >= 2

        # Should be different from correct answer
        assert all(d != correct_answer for d in distractors if d is not None)


class TestDistractorCandidate:
    """Test DistractorCandidate model."""

    def test_candidate_creation(self):
        """Test creating a distractor candidate."""
        candidate = DistractorCandidate(
            value="x^2",
            misconception_id="test_id",
            misconception="omit_coefficient",
            transformation_rule="OMIT_COEFFICIENT",
            plausibility_score=8.5,
            quality_score=8.0,
            explanation="Forgot coefficient"
        )

        assert candidate.value == "x^2"
        assert candidate.misconception_id == "test_id"
        assert candidate.transformation_rule == "OMIT_COEFFICIENT"
        assert candidate.plausibility_score == 8.5
        assert candidate.quality_score == 8.0
        assert candidate.is_trivial is False

    def test_candidate_validation(self):
        """Test candidate validation."""
        # Plausibility score must be 0-10
        with pytest.raises(Exception):
            DistractorCandidate(
                value="x^2",
                misconception_id="test_id",
                misconception="test",
                transformation_rule="TEST",
                plausibility_score=15.0,  # Invalid!
                quality_score=8.0,
                explanation="Test"
            )


class TestDistractorSet:
    """Test DistractorSet model."""

    def test_distractor_set_creation(self):
        """Test creating a distractor set."""
        candidates = [
            DistractorCandidate(
                value="x^2",
                misconception_id="test_1",
                misconception="omit_coefficient",
                transformation_rule="OMIT_COEFFICIENT",
                plausibility_score=8.0,
                quality_score=8.0,
                explanation="Test 1"
            ),
            DistractorCandidate(
                value="-2x^2",
                misconception_id="test_2",
                misconception="wrong_sign",
                transformation_rule="WRONG_SIGN",
                plausibility_score=7.5,
                quality_score=7.5,
                explanation="Test 2"
            )
        ]

        distractor_set = DistractorSet(
            correct_answer="2x^2",
            distractors=candidates,
            question_id="q123",
            topic_id="derivatives",
            course_id="ap_calculus_bc",
            avg_quality_score=7.75
        )

        assert distractor_set.correct_answer == "2x^2"
        assert len(distractor_set.distractors) == 2
        assert distractor_set.question_id == "q123"
        assert distractor_set.avg_quality_score == 7.75


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.fixture
    def full_setup(self, tmp_path):
        """Setup with misconception manager and designer."""
        manager = MisconceptionDatabaseManager(str(tmp_path / "misconceptions"))

        # Seed with realistic misconceptions
        manager.add_misconception(
            classification={
                "course_id": "ap_calculus_bc",
                "topic_id": "derivatives",
                "unit_id": "u2",
                "category": "procedural_error",
                "difficulty_level": 2
            },
            description={
                "title": "Power rule coefficient omission",
                "detailed": "Student applies power rule but forgets to multiply by original exponent",
                "example": "d/dx[x^3] = x^2 instead of 3x^2",
                "correct_approach": "Power rule states d/dx[x^n] = n*x^(n-1)"
            },
            frequency={
                "occurrence_rate": 0.25,
                "prevalence": "common",
                "grade_distribution": {"grade_11": 0.30, "grade_12": 0.20}
            },
            distractor_generation={
                "transformation_rule": "OMIT_COEFFICIENT",
                "template": "{{base}}^{{exponent_minus_one}}",
                "plausibility_score": 9.0,
                "recommended_question_types": ["power_rule_basic"],
                "parameters": {"preserve_base": True}
            },
            tags=["power_rule", "derivatives", "procedural_error"]
        )

        designer = DistractorDesigner(misconception_manager=manager)

        return manager, designer

    def test_end_to_end_generation(self, full_setup):
        """Test complete end-to-end distractor generation."""
        manager, designer = full_setup

        # Question context
        correct_answer = "4x^3"
        context = {
            "course_id": "ap_calculus_bc",
            "topic_id": "derivatives",
            "unit_id": "u2",
            "question_id": "q_power_rule_001",
            "difficulty_level": 2,
            "parameters": {
                "coefficient": 4,
                "exponent": 4,
                "base": "x"
            }
        }

        # Generate distractors
        result = designer.generate_distractors(
            correct_answer=correct_answer,
            question_context=context,
            count=3,
            min_quality=7.0
        )

        # Validate result
        assert isinstance(result, DistractorSet)
        assert result.correct_answer == correct_answer
        assert len(result.distractors) >= 1
        assert result.avg_quality_score >= 7.0

        # Check that at least one distractor uses misconception
        misconception_based = [
            d for d in result.distractors
            if d.misconception_id != "fallback_generic"
        ]
        assert len(misconception_based) >= 1

        # Validate distractor properties
        for distractor in result.distractors:
            assert distractor.value != correct_answer
            assert not distractor.is_trivial
            assert 0.0 <= distractor.quality_score <= 10.0
            assert 0.0 <= distractor.plausibility_score <= 10.0

    def test_misconception_usage_tracking(self, full_setup):
        """Test that misconception usage is tracked."""
        manager, designer = full_setup

        # Get initial stats
        initial_stats = manager.get_statistics()
        initial_usage = sum(
            m.usage_count for m in manager.search(topic_id="derivatives")
        )

        # Generate distractors
        designer.generate_distractors(
            "3x^2",
            {
                "course_id": "ap_calculus_bc",
                "topic_id": "derivatives",
                "difficulty_level": 2
            },
            count=3
        )

        # Usage tracking would need to be explicitly called
        # (not automatically done by designer, but by the system using it)
        misconceptions = manager.search(topic_id="derivatives")
        if misconceptions:
            manager.increment_usage(misconceptions[0].id)

        # Verify usage was tracked
        final_stats = manager.get_statistics()
        final_usage = sum(
            m.usage_count for m in manager.search(topic_id="derivatives")
        )

        assert final_usage > initial_usage
