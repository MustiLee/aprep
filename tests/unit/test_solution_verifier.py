"""Unit tests for Solution Verifier agent."""

import pytest
from src.agents.solution_verifier import SolutionVerifier, verify_batch


class TestSolutionVerifier:
    """Test Solution Verifier functionality."""

    @pytest.fixture
    def verifier(self):
        """Create SolutionVerifier instance."""
        return SolutionVerifier(numerical_samples=5)

    def test_simple_derivative_correct(self, verifier):
        """Test basic derivative verification - correct answer."""
        variant = {
            "id": "test_001",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["2x", "x", "2", "x²"],
            "answer_index": 0,
            "solution": "2x",
        }

        result = verifier.verify_symbolic(variant)

        assert result["status"] == "PASS"
        assert result["confidence"] == 1.0
        assert "proof" in result

    def test_simple_derivative_wrong(self, verifier):
        """Test basic derivative verification - wrong answer."""
        variant = {
            "id": "test_002",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["3x", "x", "2", "x²"],
            "answer_index": 0,
            "solution": "3x",
        }

        result = verifier.verify_symbolic(variant)

        assert result["status"] == "FAIL"
        assert result["confidence"] == 1.0
        assert "expected" in result

    def test_chain_rule_derivative(self, verifier):
        """Test chain rule derivative verification."""
        variant = {
            "id": "test_003",
            "stimulus": "Let f(x) = sin(2*x²). Find f'(x).",
            "options": ["4*x*cos(2*x²)", "cos(2*x²)", "2*x*cos(2*x²)", "sin(4*x)"],
            "answer_index": 0,
            "solution": "4*x*cos(2*x**2)",
        }

        result = verifier.verify_symbolic(variant)

        assert result["status"] == "PASS"

    def test_numerical_verification_correct(self, verifier):
        """Test numerical verification - correct answer."""
        variant = {
            "id": "test_004",
            "stimulus": "Let f(x) = x³. Find f'(x).",
            "options": ["3*x²", "x²", "3*x", "x³"],
            "answer_index": 0,
            "solution": "3*x**2",
        }

        result = verifier.verify_numerical(variant)

        assert result["status"] == "PASS"
        assert result["max_error"] < 1e-4
        assert result["samples_tested"] == 5

    def test_numerical_verification_wrong(self, verifier):
        """Test numerical verification - wrong answer."""
        variant = {
            "id": "test_005",
            "stimulus": "Let f(x) = x³. Find f'(x).",
            "options": ["2*x²", "x²", "3*x", "x³"],
            "answer_index": 0,
            "solution": "2*x**2",
        }

        result = verifier.verify_numerical(variant)

        assert result["status"] == "FAIL"
        assert result["max_error"] > 1e-4

    def test_distractor_verification_all_wrong(self, verifier):
        """Test that all distractors are wrong."""
        variant = {
            "id": "test_006",
            "stimulus": "Let f(x) = sin(x). Find f'(x).",
            "options": ["cos(x)", "sin(x)", "-cos(x)", "tan(x)"],
            "answer_index": 0,
            "solution": "cos(x)",
        }

        distractors = verifier.verify_distractors(variant)

        # Should have 3 distractors (excluding correct answer)
        assert len(distractors) == 3
        # All should be wrong
        assert all(d["is_wrong"] for d in distractors)

    def test_distractor_duplicate_correct(self, verifier):
        """Test detection of distractor that equals correct answer."""
        variant = {
            "id": "test_007",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["2*x", "2*x", "x", "2"],  # Duplicate!
            "answer_index": 0,
            "solution": "2*x",
        }

        distractors = verifier.verify_distractors(variant)

        # Find the duplicate
        duplicates = [d for d in distractors if not d["is_wrong"]]
        assert len(duplicates) > 0
        assert "duplicate" in duplicates[0]["reason"].lower()

    def test_operation_detection_derivative(self, verifier):
        """Test detection of derivative operation."""
        stimulus = "Let f(x) = x². Find f'(x)."
        operation = verifier._detect_operation(stimulus)
        assert operation == "derivative"

    def test_operation_detection_integral(self, verifier):
        """Test detection of integral operation."""
        stimulus = "Find the integral of 2x dx."
        operation = verifier._detect_operation(stimulus)
        assert operation == "integral"

    def test_operation_detection_limit(self, verifier):
        """Test detection of limit operation."""
        stimulus = "Find the limit as x approaches 0 of sin(x)/x."
        operation = verifier._detect_operation(stimulus)
        assert operation == "limit"

    def test_function_extraction(self, verifier):
        """Test extraction of function from question."""
        question = "Let f(x) = sin(2*x²). Find f'(x)."
        func_str = verifier._extract_function(question)
        assert "sin" in func_str
        assert "2*x" in func_str or "2x" in func_str

    def test_full_verification_pass(self, verifier):
        """Test complete verification pipeline - should pass."""
        variant = {
            "id": "test_008",
            "stimulus": "Let f(x) = x³ + 2*x. Find f'(x).",
            "options": ["3*x² + 2", "3*x²", "x² + 2", "3*x³ + 2*x"],
            "answer_index": 0,
            "solution": "3*x**2 + 2",
        }

        result = verifier.verify_variant(variant)

        assert result["verification_status"] == "PASS"
        assert result["correctness"]["answer_is_correct"] is True
        assert result["correctness"]["distractors_all_wrong"] is True
        assert result["correctness"]["exactly_one_correct"] is True
        assert result["consensus"]["confidence"] > 0.9

    def test_full_verification_fail(self, verifier):
        """Test complete verification pipeline - should fail."""
        variant = {
            "id": "test_009",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["3*x", "x", "2", "x²"],  # Wrong answer!
            "answer_index": 0,
            "solution": "3*x",
        }

        result = verifier.verify_variant(variant)

        assert result["verification_status"] == "FAIL"
        assert result["correctness"]["answer_is_correct"] is False
        assert len(result["issues"]) > 0
        assert result["issues"][0]["severity"] == "CRITICAL"

    def test_integral_verification(self, verifier):
        """Test integral verification."""
        variant = {
            "id": "test_010",
            "stimulus": "Let f(x) = 2*x. Find the integral of f(x) dx.",
            "options": ["x² + C", "2*x² + C", "x + C", "2*x + C"],
            "answer_index": 0,
            "solution": "x**2",
        }

        result = verifier.verify_symbolic(variant)

        # Should pass (ignoring constant of integration)
        assert result["status"] == "PASS"

    def test_mistake_type_inference(self, verifier):
        """Test inference of mistake type from symbolic difference."""
        from sympy import sympify

        # Coefficient error
        diff = sympify("2*x")
        mistake = verifier._infer_mistake_type(diff)
        assert "coefficient" in mistake.lower() or "error" in mistake.lower()

        # Trigonometric error
        diff = sympify("sin(x)")
        mistake = verifier._infer_mistake_type(diff)
        assert "trig" in mistake.lower() or "error" in mistake.lower()

    def test_aggregate_results_all_pass(self, verifier):
        """Test aggregation when all methods pass."""
        methods = [
            {"status": "PASS", "confidence": 1.0},
            {"status": "PASS", "confidence": 0.99},
            {"status": "PASS", "confidence": 0.95},
        ]

        consensus = verifier._aggregate_results(methods)

        assert consensus["status"] == "PASS"
        assert consensus["all_methods_agree"] is True
        assert consensus["confidence"] > 0.9

    def test_aggregate_results_all_fail(self, verifier):
        """Test aggregation when all methods fail."""
        methods = [
            {"status": "FAIL", "confidence": 1.0},
            {"status": "FAIL", "confidence": 0.99},
        ]

        consensus = verifier._aggregate_results(methods)

        assert consensus["status"] == "FAIL"
        assert consensus["all_methods_agree"] is True

    def test_aggregate_results_disagreement(self, verifier):
        """Test aggregation when methods disagree."""
        methods = [
            {"status": "PASS", "confidence": 1.0},
            {"status": "FAIL", "confidence": 0.99},
        ]

        consensus = verifier._aggregate_results(methods)

        assert consensus["all_methods_agree"] is False
        assert consensus["confidence"] < 0.8  # Low confidence

    def test_performance_metrics(self, verifier):
        """Test that performance metrics are recorded."""
        variant = {
            "id": "test_011",
            "stimulus": "Let f(x) = x². Find f'(x).",
            "options": ["2*x", "x", "2", "x²"],
            "answer_index": 0,
            "solution": "2*x",
        }

        result = verifier.verify_variant(variant)

        assert "performance" in result
        assert "duration_ms" in result["performance"]
        assert "cost_usd" in result["performance"]
        assert result["performance"]["duration_ms"] > 0


class TestBatchVerification:
    """Test batch verification functionality."""

    def test_batch_verification(self):
        """Test verifying multiple variants."""
        variants = [
            {
                "id": "batch_001",
                "stimulus": "Let f(x) = x². Find f'(x).",
                "options": ["2*x", "x", "2", "x²"],
                "answer_index": 0,
                "solution": "2*x",
            },
            {
                "id": "batch_002",
                "stimulus": "Let f(x) = x³. Find f'(x).",
                "options": ["3*x²", "x²", "3*x", "x³"],
                "answer_index": 0,
                "solution": "3*x**2",
            },
            {
                "id": "batch_003",
                "stimulus": "Let f(x) = x². Find f'(x).",
                "options": ["5*x", "x", "2", "x²"],  # Wrong!
                "answer_index": 0,
                "solution": "5*x",
            },
        ]

        results = verify_batch(variants)

        assert "summary" in results
        assert results["summary"]["total"] == 3
        assert results["summary"]["passed"] >= 2
        assert results["summary"]["failed"] >= 1

    def test_batch_needs_review(self):
        """Test that low-confidence results are flagged for review."""
        verifier = SolutionVerifier()

        # Create a variant that might have low confidence
        variants = [
            {
                "id": "review_001",
                "stimulus": "Let f(x) = x². Find f'(x).",
                "options": ["2*x", "x", "2", "x²"],
                "answer_index": 0,
                "solution": "2*x",
            }
        ]

        results = verify_batch(variants, verifier)

        # Should have summary with needs_review count
        assert "needs_review" in results
        assert isinstance(results["needs_review"], list)


class TestErrorHandling:
    """Test error handling in verification."""

    @pytest.fixture
    def verifier(self):
        """Create SolutionVerifier instance."""
        return SolutionVerifier()

    def test_invalid_function_extraction(self, verifier):
        """Test handling of invalid function extraction."""
        variant = {
            "id": "error_001",
            "stimulus": "This is not a valid math question.",
            "options": ["a", "b", "c", "d"],
            "answer_index": 0,
            "solution": "a",
        }

        result = verifier.verify_symbolic(variant)

        # Should return ERROR status
        assert result["status"] == "ERROR"

    def test_sympify_error(self, verifier):
        """Test handling of SymPy parsing errors."""
        variant = {
            "id": "error_002",
            "stimulus": "Let f(x) = invalid_expression. Find f'(x).",
            "options": ["a", "b", "c", "d"],
            "answer_index": 0,
            "solution": "invalid",
        }

        result = verifier.verify_symbolic(variant)

        assert result["status"] == "ERROR"
        assert "error" in result

    def test_numerical_overflow_handling(self, verifier):
        """Test handling of numerical overflow."""
        variant = {
            "id": "error_003",
            "stimulus": "Let f(x) = exp(x). Find f'(x).",
            "options": ["exp(x)", "x*exp(x)", "exp(2*x)", "1"],
            "answer_index": 0,
            "solution": "exp(x)",
        }

        # Should handle gracefully even if some test points overflow
        result = verifier.verify_numerical(variant)

        # Should not crash, either PASS or ERROR
        assert result["status"] in ["PASS", "ERROR", "FAIL"]
