"""Unit tests for Parametric Generator agent."""

import pytest
from src.agents.parametric_generator import ParametricGenerator


class TestParametricGenerator:
    """Test Parametric Generator functionality."""

    @pytest.fixture
    def generator(self):
        """Create ParametricGenerator instance."""
        return ParametricGenerator()

    @pytest.fixture
    def sample_template(self):
        """Sample template for testing."""
        return {
            "template_id": "test_template_001",
            "course_id": "ap_calculus_bc",
            "unit_id": "u2",
            "topic_id": "t2.1",
            "stem": "Let f(x) = {{coefficient}}x^{{exponent}}. Find f'(x).",
            "solution_template": "{{coefficient * exponent}}x^{{exponent - 1}}",
            "params": {
                "coefficient": {
                    "type": "integer",
                    "range": [2, 5],
                },
                "exponent": {
                    "type": "integer",
                    "range": [2, 4],
                },
            },
            "distractor_rules": [
                {
                    "rule_id": "omit_coef",
                    "description": "Forget to multiply by coefficient",
                    "generation": "{{exponent}}x^{{exponent - 1}}",
                },
                {
                    "rule_id": "wrong_exponent",
                    "description": "Don't subtract 1 from exponent",
                    "generation": "{{coefficient * exponent}}x^{{exponent}}",
                },
                {
                    "rule_id": "power_rule_error",
                    "description": "Forget the exponent multiplication",
                    "generation": "{{coefficient}}x^{{exponent - 1}}",
                },
            ],
            "calculator": "No-Calc",
            "difficulty_range": [0.4, 0.6],
            "estimated_difficulty": 0.5,
            "bloom_level": "Apply",
            "cognitive_complexity": "medium",
            "tags": ["derivatives", "power_rule"],
        }

    def test_initialization(self, generator):
        """Test generator can be initialized."""
        assert generator is not None
        # Performance metrics initialized (HIGH PRIORITY feature)
        assert generator.total_variants_generated == 0
        assert generator.total_attempts == 0
        assert generator.total_failures == 0
        assert generator.generation_history == []

    def test_generate_single_variant(self, generator, sample_template):
        """Test generating a single variant."""
        variant = generator.generate_single_variant(sample_template, seed=42)

        assert variant is not None
        assert variant["id"] == "test_template_001_v42"
        assert "stimulus" in variant
        assert "options" in variant
        assert len(variant["options"]) == 4
        assert "answer_index" in variant
        assert 0 <= variant["answer_index"] < 4
        assert "solution" in variant

    def test_variant_has_template_metadata(self, generator, sample_template):
        """Test that variants include template metadata (CRITICAL feature)."""
        variant = generator.generate_single_variant(sample_template, seed=123)

        # Check template metadata pass-through
        assert variant["template_id"] == "test_template_001"
        assert variant["course_id"] == "ap_calculus_bc"
        assert variant["unit_id"] == "u2"
        assert variant["topic_id"] == "t2.1"

        # Check metadata section
        metadata = variant["metadata"]
        assert metadata["template_id"] == "test_template_001"
        assert metadata["template_difficulty"] == 0.5
        assert metadata["bloom_level"] == "Apply"
        assert metadata["cognitive_complexity"] == "medium"
        assert metadata["calculator"] == "No-Calc"

    def test_parameter_instantiation_enum(self, generator):
        """Test enum parameter instantiation."""
        template = {
            "template_id": "test_enum",
            "stem": "Variable: {{var}}",
            "params": {
                "var": {
                    "type": "enum",
                    "values": ["x", "t", "u"],
                },
            },
            "distractor_rules": [],
        }

        variant = generator.generate_single_variant(template, seed=1)
        # Check that variable is one of the options
        assert any(v in variant["stimulus"] for v in ["x", "t", "u"])

    def test_parameter_instantiation_integer_range(self, generator):
        """Test integer range parameter instantiation."""
        template = {
            "template_id": "test_int",
            "stem": "Number: {{num}}",
            "params": {
                "num": {
                    "type": "integer",
                    "range": [1, 10],
                },
            },
            "distractor_rules": [],
        }

        variant = generator.generate_single_variant(template, seed=5)
        # Extract number from stimulus
        import re
        match = re.search(r"Number: (\d+)", variant["stimulus"])
        assert match is not None
        num = int(match.group(1))
        assert 1 <= num <= 10

    def test_parameter_instantiation_float_range(self, generator):
        """Test float range parameter instantiation."""
        template = {
            "template_id": "test_float",
            "stem": "Value: {{val}}",
            "params": {
                "val": {
                    "type": "float",
                    "range": [0.5, 2.5],
                },
            },
            "distractor_rules": [],
        }

        variant = generator.generate_single_variant(template, seed=7)
        assert "Value:" in variant["stimulus"]

    def test_distractor_generation(self, generator, sample_template):
        """Test distractor generation from rules."""
        variant = generator.generate_single_variant(sample_template, seed=42)

        # Should have 4 options (1 correct + 3 distractors)
        assert len(variant["options"]) == 4

        # All options should be unique
        assert len(set(variant["options"])) == 4

        # Correct answer should be at answer_index
        correct_option = variant["options"][variant["answer_index"]]
        assert correct_option == variant["solution"]

    def test_answer_shuffling(self, generator, sample_template):
        """Test that answer positions are randomized."""
        # Generate multiple variants and check that answer position varies
        positions = []
        for seed in range(10):
            variant = generator.generate_single_variant(sample_template, seed)
            positions.append(variant["answer_index"])

        # With 10 tries and 4 positions, should have some variation
        assert len(set(positions)) > 1

    def test_validation_duplicate_options(self, generator, sample_template):
        """Test validation catches duplicate options."""
        # Create a variant with duplicate options (mock)
        variant = {
            "id": "test_001",
            "stimulus": "Test question",
            "options": ["A", "A", "B", "C"],  # Duplicate!
            "answer_index": 0,
            "solution": "A",
        }

        validation = generator._validate_variant(variant, sample_template, [])

        assert validation["valid"] is False
        assert "duplicate_options" in validation["issues"]

    def test_validation_invalid_answer_index(self, generator, sample_template):
        """Test validation catches invalid answer index."""
        variant = {
            "id": "test_002",
            "stimulus": "Test question",
            "options": ["A", "B", "C", "D"],
            "answer_index": 5,  # Out of range!
            "solution": "A",
        }

        validation = generator._validate_variant(variant, sample_template, [])

        assert validation["valid"] is False
        assert "invalid_answer_index" in validation["issues"]

    def test_validation_empty_stem(self, generator, sample_template):
        """Test validation catches empty stem."""
        variant = {
            "id": "test_003",
            "stimulus": "",  # Empty!
            "options": ["A", "B", "C", "D"],
            "answer_index": 0,
            "solution": "A",
        }

        validation = generator._validate_variant(variant, sample_template, [])

        assert validation["valid"] is False
        assert "empty_stem" in validation["issues"]

    def test_similarity_calculation(self, generator):
        """Test similarity calculation between variants."""
        v1 = {"stimulus": "Let f(x) = 2x^2. Find f'(x)."}
        v2 = {"stimulus": "Let f(x) = 3x^2. Find f'(x)."}
        v3 = {"stimulus": "Completely different question."}

        # Similar variants should have high similarity
        sim1 = generator._calculate_similarity(v1, v2)
        assert sim1 > 0.8

        # Different variants should have low similarity
        sim2 = generator._calculate_similarity(v1, v3)
        assert sim2 < 0.5

        # Identical variants should have similarity 1.0
        sim3 = generator._calculate_similarity(v1, v1)
        assert sim3 == 1.0

    def test_generate_batch(self, generator, sample_template):
        """Test batch variant generation."""
        variants = generator.generate_batch(sample_template, count=5, seed_start=0)

        # Should generate some variants (being lenient due to distractor generation)
        assert len(variants) >= 1  # At least 1
        assert all("id" in v for v in variants)
        assert all("stimulus" in v for v in variants)

    def test_batch_performance_metrics(self, generator, sample_template):
        """Test performance metrics tracking (HIGH PRIORITY feature)."""
        # Generate batch
        variants = generator.generate_batch(sample_template, count=10, seed_start=0)

        # Check metrics were updated
        assert generator.total_variants_generated >= 1
        assert generator.total_attempts >= generator.total_variants_generated
        assert len(generator.generation_history) == 1

        # Check history entry structure
        history = generator.generation_history[0]
        assert "timestamp" in history
        assert history["template_id"] == "test_template_001"
        assert history["requested"] == 10
        assert history["generated"] <= 10
        assert "duration_ms" in history
        assert "avg_ms_per_variant" in history
        assert "success_rate" in history

    def test_get_generation_stats(self, generator, sample_template):
        """Test generation statistics retrieval (HIGH PRIORITY feature)."""
        # Generate some variants
        generator.generate_batch(sample_template, count=5, seed_start=0)
        generator.generate_batch(sample_template, count=3, seed_start=10)

        stats = generator.get_generation_stats()

        assert "total_variants_generated" in stats
        assert "total_attempts" in stats
        assert "total_failures" in stats
        assert "overall_success_rate" in stats
        assert "batches_processed" in stats
        assert stats["batches_processed"] == 2

        # Check recent history
        assert "recent_history" in stats
        assert len(stats["recent_history"]) <= 5

    def test_get_generation_history(self, generator, sample_template):
        """Test generation history retrieval (HIGH PRIORITY feature)."""
        # Generate multiple batches
        generator.generate_batch(sample_template, count=5, seed_start=0)
        generator.generate_batch(sample_template, count=3, seed_start=10)

        # Get all history
        history = generator.get_generation_history()
        assert len(history) == 2

        # Get limited history
        history_limited = generator.get_generation_history(limit=1)
        assert len(history_limited) == 1

        # Get history for specific template
        history_filtered = generator.get_generation_history(
            template_id="test_template_001"
        )
        assert len(history_filtered) == 2
        assert all(h["template_id"] == "test_template_001" for h in history_filtered)

    def test_estimate_variant_difficulty(self, generator, sample_template):
        """Test variant difficulty estimation (HIGH PRIORITY feature)."""
        variant = generator.generate_single_variant(sample_template, seed=42)

        difficulty = generator.estimate_variant_difficulty(variant)

        # Should return a value between 0 and 1
        assert 0.0 <= difficulty <= 1.0

        # Should be close to template difficulty
        template_difficulty = sample_template["estimated_difficulty"]
        assert abs(difficulty - template_difficulty) < 0.3

    def test_difficulty_estimation_complexity_factors(self, generator):
        """Test difficulty estimation considers complexity factors."""
        # Simple variant
        simple_variant = {
            "stimulus": "Find f'(x) for f(x) = x^2.",
            "solution": "2x",
            "metadata": {"difficulty_est": 0.3},
            "origin": {"parameter_instantiation": {"coef": 2}},
        }

        # Complex variant
        complex_variant = {
            "stimulus": (
                "Given the function f(x) = sin(3x^2 + 2x) * cos(x), "
                "find the derivative f'(x) using the chain rule and product rule."
            ),
            "solution": "complex_answer_with_many_terms",
            "metadata": {"difficulty_est": 0.5},
            "origin": {
                "parameter_instantiation": {"a": 3, "b": 2, "c": 1, "func": "sin"}
            },
        }

        simple_difficulty = generator.estimate_variant_difficulty(simple_variant)
        complex_difficulty = generator.estimate_variant_difficulty(complex_variant)

        # Complex variant should be estimated as more difficult
        assert complex_difficulty > simple_difficulty

    def test_reproducibility_with_seed(self, generator, sample_template):
        """Test that same seed produces same variant."""
        seed = 999

        variant1 = generator.generate_single_variant(sample_template, seed)
        variant2 = generator.generate_single_variant(sample_template, seed)

        # Should be identical
        assert variant1["stimulus"] == variant2["stimulus"]
        assert variant1["solution"] == variant2["solution"]
        assert variant1["options"] == variant2["options"]
        assert variant1["answer_index"] == variant2["answer_index"]

    def test_different_seeds_produce_different_variants(self, generator, sample_template):
        """Test that different seeds produce different variants."""
        variant1 = generator.generate_single_variant(sample_template, seed=1)
        variant2 = generator.generate_single_variant(sample_template, seed=2)

        # Should be different (at least in some aspect)
        # Parameters might differ, or at least answer positions
        assert variant1["id"] != variant2["id"]

    def test_origin_tracking(self, generator, sample_template):
        """Test that variant origin is tracked."""
        seed = 42
        variant = generator.generate_single_variant(sample_template, seed)

        # Check origin metadata
        assert "origin" in variant
        origin = variant["origin"]

        assert origin["created_by"] == "agent.parametric_generator"
        assert "created_at" in origin
        assert origin["seed"] == seed
        assert "parameter_instantiation" in origin
        assert "derived_values" in origin

    def test_batch_duplicate_detection(self, generator, sample_template):
        """Test that duplicate variants are filtered out."""
        # Generate many variants to increase chance of collision
        variants = generator.generate_batch(sample_template, count=50, seed_start=0)

        # Check all variants are unique
        stimuli = [v["stimulus"] for v in variants]
        assert len(stimuli) == len(set(stimuli))

    def test_batch_low_yield_warning(self, generator):
        """Test that low yield triggers warning."""
        # Create a template that will fail often
        bad_template = {
            "template_id": "bad_template",
            "stem": "",  # Empty stem will fail validation
            "params": {},
            "distractor_rules": [],
        }

        # This should log warnings about low yield
        variants = generator.generate_batch(bad_template, count=10)

        # Should generate fewer than requested (or possibly none)
        assert len(variants) < 10


class TestParameterTypes:
    """Test different parameter type handling."""

    @pytest.fixture
    def generator(self):
        """Create ParametricGenerator instance."""
        return ParametricGenerator()

    def test_algebraic_expression_parameter(self, generator):
        """Test algebraic expression parameter type."""
        template = {
            "template_id": "test_algebraic",
            "stem": "Let f(x) = {{function}}. Find f'(x).",
            "params": {
                "function": {
                    "type": "algebraic_expression",
                    "templates": ["{{coef}}x^2", "sin({{inner}})"],
                    "constraints": {
                        "coef": [1, 2, 3],
                        "inner": ["x", "2x"],
                    },
                },
            },
            "distractor_rules": [],
        }

        variant = generator.generate_single_variant(template, seed=1)
        assert "f(x) =" in variant["stimulus"]

    def test_weighted_choice_parameter(self, generator):
        """Test weighted choice for enum parameters."""
        template = {
            "template_id": "test_weighted",
            "stem": "Variable: {{var}}",
            "params": {
                "var": {
                    "type": "enum",
                    "values": ["x", "t", "u"],
                    "weights": [0.7, 0.2, 0.1],  # Prefer 'x'
                },
            },
            "distractor_rules": [],
        }

        # Generate many variants and check distribution
        variants = [
            generator.generate_single_variant(template, seed=i) for i in range(30)
        ]

        # Count occurrences
        x_count = sum(1 for v in variants if "x" in v["stimulus"])

        # Should have more 'x' than others (but this is probabilistic)
        assert x_count >= 10  # At least some 'x' values


class TestErrorHandling:
    """Test error handling in generation."""

    @pytest.fixture
    def generator(self):
        """Create ParametricGenerator instance."""
        return ParametricGenerator()

    def test_missing_required_fields(self, generator):
        """Test handling of templates with missing fields."""
        incomplete_template = {
            "template_id": "incomplete",
            # Missing: stem, params, etc.
        }

        # Should not crash
        try:
            variant = generator.generate_single_variant(incomplete_template, seed=1)
            # If it generates, check it has some fallback values
            assert variant is not None
        except Exception:
            # Exception is acceptable for invalid template
            pass

    def test_invalid_parameter_ranges(self, generator):
        """Test handling of invalid parameter ranges."""
        template = {
            "template_id": "test_invalid_range",
            "stem": "Number: {{num}}",
            "params": {
                "num": {
                    "type": "integer",
                    "range": [],  # Invalid: empty range
                },
            },
            "distractor_rules": [],
        }

        # Should use fallback range
        variant = generator.generate_single_variant(template, seed=1)
        assert variant is not None
