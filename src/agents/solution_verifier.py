"""Solution Verifier Agent - Mathematical correctness verification.

Verifies mathematical correctness of generated MCQ variants through:
1. Symbolic computation (SymPy)
2. Numerical validation
3. Claude Opus reasoning (fallback)
4. Distractor verification
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sympy import (
    symbols,
    diff,
    integrate,
    limit,
    solve,
    simplify,
    sympify,
    lambdify,
    SympifyError,
    oo,
)
from anthropic import Anthropic, APIError, APITimeoutError

from ..core.config import get_settings
from ..core.logger import setup_logger
from ..core.exceptions import VerificationError, AprepError


class SolutionVerifier:
    """Verify mathematical correctness of question variants."""

    def __init__(
        self,
        model: str = None,
        numerical_samples: int = 10,
        numerical_tolerance: float = 1e-6,
    ):
        """Initialize Solution Verifier.

        Args:
            model: Claude model for reasoning (defaults to Opus 4)
            numerical_samples: Number of points for numerical validation
            numerical_tolerance: Error tolerance for numerical checks
        """
        self.settings = get_settings()
        self.logger = setup_logger(__name__)
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = model or self.settings.claude_model_opus
        self.numerical_samples = numerical_samples
        self.numerical_tolerance = numerical_tolerance

        # Symbolic variables
        self.x = symbols("x")
        self.t = symbols("t")

        self.logger.info(
            f"SolutionVerifier initialized with model={self.model}, "
            f"samples={numerical_samples}, tolerance={numerical_tolerance}"
        )

    def verify_variant(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Main verification entry point.

        Args:
            variant: Question variant with stimulus, options, answer

        Returns:
            Verification result with status, confidence, and analysis
        """
        start_time = datetime.utcnow()
        variant_id = variant.get("id", "unknown")

        self.logger.info(f"Verifying variant: {variant_id}")

        try:
            # Phase 1: Symbolic verification (primary)
            symbolic_result = self.verify_symbolic(variant)
            self.logger.debug(f"Symbolic result: {symbolic_result['status']}")

            # Phase 2: Numerical validation (secondary)
            numerical_result = self.verify_numerical(variant)
            self.logger.debug(f"Numerical result: {numerical_result['status']}")

            # Phase 3: Claude reasoning (if needed)
            claude_result = None
            if symbolic_result["status"] != numerical_result["status"]:
                # Contradiction - use Claude as tiebreaker
                self.logger.warning(
                    f"Contradiction detected for {variant_id}: "
                    f"symbolic={symbolic_result['status']}, "
                    f"numerical={numerical_result['status']}"
                )
                claude_result = self.verify_with_claude(variant)
                self.logger.debug(f"Claude result: {claude_result['status']}")

            # Phase 4: Distractor verification
            distractors = self.verify_distractors(variant)
            all_distractors_wrong = all(d["is_wrong"] for d in distractors)

            # Phase 5: Aggregate results
            methods = [symbolic_result, numerical_result]
            if claude_result:
                methods.append(claude_result)

            consensus = self._aggregate_results(methods)

            # Final status
            verification_status = (
                "PASS"
                if consensus["status"] == "PASS" and all_distractors_wrong
                else "FAIL"
            )

            # Calculate duration and cost
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            cost_usd = 0.003 if claude_result else 0.0  # Claude usage cost

            result = {
                "variant_id": variant_id,
                "verification_status": verification_status,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "correctness": {
                    "answer_is_correct": consensus["status"] == "PASS",
                    "distractors_all_wrong": all_distractors_wrong,
                    "exactly_one_correct": consensus["status"] == "PASS"
                    and all_distractors_wrong,
                },
                "methods_used": {
                    "symbolic": symbolic_result,
                    "numerical": numerical_result,
                    "claude_reasoning": claude_result,
                },
                "consensus": consensus,
                "distractor_analysis": distractors,
                "issues": self._collect_issues(
                    consensus, distractors, symbolic_result, numerical_result
                ),
                "warnings": self._collect_warnings(
                    consensus, symbolic_result, numerical_result, claude_result
                ),
                "performance": {
                    "duration_ms": round(duration_ms, 2),
                    "cost_usd": cost_usd,
                },
            }

            self.logger.info(
                f"Verification complete for {variant_id}: {verification_status} "
                f"(confidence={consensus['confidence']:.2f})"
            )

            return result

        except Exception as e:
            self.logger.error(f"Verification failed for {variant_id}: {e}")
            raise VerificationError(
                f"Verification failed for variant {variant_id}: {str(e)}"
            ) from e

    def verify_symbolic(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Symbolic verification using SymPy.

        Args:
            variant: Question variant

        Returns:
            Symbolic verification result
        """
        try:
            # Detect operation type
            stimulus = variant.get("stimulus", "")
            operation = self._detect_operation(stimulus)

            if operation == "derivative":
                return self._verify_derivative(variant)
            elif operation == "integral":
                return self._verify_integral(variant)
            elif operation == "limit":
                return self._verify_limit(variant)
            elif operation == "solve":
                return self._verify_equation_solution(variant)
            else:
                return {
                    "status": "UNSUPPORTED",
                    "confidence": 0.0,
                    "reason": f"Operation type '{operation}' not supported",
                }

        except SympifyError as e:
            self.logger.warning(f"SymPy parse error: {e}")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": f"Failed to parse expression: {str(e)}",
            }
        except Exception as e:
            self.logger.error(f"Symbolic verification error: {e}")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": str(e),
            }

    def _verify_derivative(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Verify derivative problem.

        Args:
            variant: Question variant

        Returns:
            Derivative verification result
        """
        # Extract function from question
        func_str = self._extract_function(variant["stimulus"])
        if not func_str:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": "Could not extract function from question",
            }

        # Detect variable from stimulus
        var_match = re.search(r"f\(([a-zA-Z])\)", variant["stimulus"])
        if var_match:
            var_name = var_match.group(1)
            var_symbol = symbols(var_name)
        else:
            var_symbol = self.x  # Default to x

        # Preprocess and parse function
        func_str = self._preprocess_math_expression(func_str)
        f = sympify(func_str)
        f_prime = diff(f, var_symbol)
        f_prime_simplified = simplify(f_prime)

        # Get claimed answer
        claimed_solution = variant.get("solution") or variant.get("claimed_solution")
        if not claimed_solution:
            # Use the option at answer_index
            answer_idx = variant.get("answer_index", 0)
            claimed_solution = variant["options"][answer_idx]

        # Extract just the mathematical expression
        claimed_solution = self._extract_solution_expression(claimed_solution)

        # Preprocess and parse claimed solution
        claimed_solution = self._preprocess_math_expression(claimed_solution)
        claimed = sympify(claimed_solution)
        claimed_simplified = simplify(claimed)

        difference = simplify(f_prime_simplified - claimed_simplified)

        if difference == 0:
            return {
                "status": "PASS",
                "confidence": 1.0,
                "proof": f"diff({func_str}, x) = {f_prime_simplified} ✓",
                "computed": str(f_prime_simplified),
                "claimed": str(claimed_simplified),
            }
        else:
            return {
                "status": "FAIL",
                "confidence": 1.0,
                "proof": f"Expected {f_prime_simplified}, got {claimed_simplified}",
                "expected": str(f_prime_simplified),
                "got": str(claimed_simplified),
                "difference": str(difference),
            }

    def _verify_integral(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Verify integral problem.

        Args:
            variant: Question variant

        Returns:
            Integral verification result
        """
        # Extract function from question
        func_str = self._extract_function(variant["stimulus"])
        if not func_str:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": "Could not extract function from question",
            }

        # Parse function and compute integral
        f = sympify(func_str)
        F = integrate(f, self.x)
        F_simplified = simplify(F)

        # Get claimed answer
        claimed_solution = variant.get("solution") or variant.get("claimed_solution")
        if not claimed_solution:
            answer_idx = variant.get("answer_index", 0)
            claimed_solution = variant["options"][answer_idx]

        # Compare (accounting for constant of integration)
        claimed = sympify(claimed_solution)
        claimed_simplified = simplify(claimed)

        # Check if derivatives are equal (ignoring constant)
        diff_computed = simplify(diff(F_simplified, self.x))
        diff_claimed = simplify(diff(claimed_simplified, self.x))

        if simplify(diff_computed - diff_claimed) == 0:
            return {
                "status": "PASS",
                "confidence": 1.0,
                "proof": f"integrate({func_str}, x) = {F_simplified} + C ✓",
                "computed": str(F_simplified),
                "claimed": str(claimed_simplified),
            }
        else:
            return {
                "status": "FAIL",
                "confidence": 1.0,
                "expected": str(F_simplified),
                "got": str(claimed_simplified),
            }

    def _verify_limit(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Verify limit problem.

        Args:
            variant: Question variant

        Returns:
            Limit verification result
        """
        # Extract function and limit point
        func_str = self._extract_function(variant["stimulus"])
        limit_point = self._extract_limit_point(variant["stimulus"])

        if not func_str or limit_point is None:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": "Could not extract function or limit point",
            }

        # Parse and compute limit
        f = sympify(func_str)
        lim_result = limit(f, self.x, limit_point)
        lim_simplified = simplify(lim_result)

        # Get claimed answer
        claimed_solution = variant.get("solution") or variant.get("claimed_solution")
        if not claimed_solution:
            answer_idx = variant.get("answer_index", 0)
            claimed_solution = variant["options"][answer_idx]

        claimed = sympify(claimed_solution)

        if simplify(lim_simplified - claimed) == 0:
            return {
                "status": "PASS",
                "confidence": 1.0,
                "proof": f"lim(x→{limit_point}) {func_str} = {lim_simplified} ✓",
                "computed": str(lim_simplified),
                "claimed": str(claimed),
            }
        else:
            return {
                "status": "FAIL",
                "confidence": 1.0,
                "expected": str(lim_simplified),
                "got": str(claimed),
            }

    def _verify_equation_solution(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Verify equation solution.

        Args:
            variant: Question variant

        Returns:
            Equation solution verification result
        """
        # This is more complex - would need equation extraction
        # For now, return UNSUPPORTED
        return {
            "status": "UNSUPPORTED",
            "confidence": 0.0,
            "reason": "Equation solving verification not yet implemented",
        }

    def verify_numerical(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Numerical validation at random test points.

        Args:
            variant: Question variant

        Returns:
            Numerical verification result
        """
        try:
            # Extract function from question
            func_str = self._extract_function(variant["stimulus"])
            if not func_str:
                return {
                    "status": "ERROR",
                    "confidence": 0.0,
                    "error": "Could not extract function",
                }

            # Get claimed answer
            claimed_solution = variant.get("solution") or variant.get(
                "claimed_solution"
            )
            if not claimed_solution:
                answer_idx = variant.get("answer_index", 0)
                claimed_solution = variant["options"][answer_idx]

            # Detect operation type
            operation = self._detect_operation(variant["stimulus"])

            if operation == "derivative":
                return self._verify_derivative_numerical(
                    func_str, claimed_solution, self.numerical_samples
                )
            elif operation == "integral":
                return self._verify_integral_numerical(
                    func_str, claimed_solution, self.numerical_samples
                )
            else:
                return {
                    "status": "UNSUPPORTED",
                    "confidence": 0.0,
                    "reason": f"Numerical verification for '{operation}' not supported",
                }

        except Exception as e:
            self.logger.error(f"Numerical verification error: {e}")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": str(e),
            }

    def _verify_derivative_numerical(
        self, func_str: str, claimed_solution: str, n_samples: int
    ) -> Dict[str, Any]:
        """Numerically verify derivative.

        Args:
            func_str: Function string
            claimed_solution: Claimed derivative
            n_samples: Number of test points

        Returns:
            Numerical verification result
        """
        try:
            # Create numeric functions
            f = lambdify(self.x, sympify(func_str), "numpy")
            claimed_f_prime = lambdify(self.x, sympify(claimed_solution), "numpy")

            # Numerical derivative function
            def numerical_derivative(func, x_val, h=1e-7):
                return (func(x_val + h) - func(x_val - h)) / (2 * h)

            # Test at random points
            test_points = np.random.uniform(-5, 5, n_samples)
            errors = []
            samples = []

            for x_val in test_points:
                try:
                    actual_deriv = numerical_derivative(f, x_val)
                    claimed_deriv = claimed_f_prime(x_val)

                    error = abs(actual_deriv - claimed_deriv)
                    errors.append(error)
                    samples.append(
                        {
                            "x": float(x_val),
                            "expected": float(actual_deriv),
                            "got": float(claimed_deriv),
                            "error": float(error),
                        }
                    )
                except (OverflowError, ZeroDivisionError, ValueError) as e:
                    # Skip problematic points
                    self.logger.debug(f"Skipping x={x_val}: {e}")
                    continue

            if not errors:
                return {
                    "status": "ERROR",
                    "confidence": 0.0,
                    "error": "All test points failed",
                }

            max_error = max(errors)
            avg_error = np.mean(errors)

            if max_error < self.numerical_tolerance:
                return {
                    "status": "PASS",
                    "confidence": 0.99,
                    "max_error": float(max_error),
                    "avg_error": float(avg_error),
                    "samples_tested": len(errors),
                }
            else:
                return {
                    "status": "FAIL",
                    "confidence": 0.99,
                    "max_error": float(max_error),
                    "avg_error": float(avg_error),
                    "samples_tested": len(errors),
                    "failed_samples": [s for s in samples if s["error"] > self.numerical_tolerance][:3],
                }

        except Exception as e:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": str(e),
            }

    def _verify_integral_numerical(
        self, func_str: str, claimed_solution: str, n_samples: int
    ) -> Dict[str, Any]:
        """Numerically verify integral (by checking derivatives match).

        Args:
            func_str: Function string
            claimed_solution: Claimed antiderivative
            n_samples: Number of test points

        Returns:
            Numerical verification result
        """
        # Verify by checking d/dx of both equals original function
        return self._verify_derivative_numerical(claimed_solution, func_str, n_samples)

    def verify_with_claude(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Use Claude Opus for complex reasoning verification.

        Args:
            variant: Question variant

        Returns:
            Claude verification result
        """
        try:
            prompt = f"""You are a mathematical verification system. Verify the correctness of this solution.

**Problem:**
{variant['stimulus']}

**Claimed Answer:**
{variant.get('solution') or variant['options'][variant['answer_index']]}

**Task:**
1. Solve the problem step-by-step
2. Compare your solution with the claimed answer
3. Determine if the claimed answer is correct

**Output Format (JSON only):**
{{
  "is_correct": true/false,
  "your_solution": "...",
  "reasoning": "...",
  "confidence": 0.0-1.0
}}

Be rigorous and show all work. Output ONLY valid JSON."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_match = re.search(
                    r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL
                )
                if json_match:
                    response_text = json_match.group(1)
            elif "```" in response_text:
                json_match = re.search(r"```\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            result = json.loads(response_text)

            return {
                "status": "PASS" if result["is_correct"] else "FAIL",
                "confidence": result["confidence"],
                "reasoning": result["reasoning"],
                "claude_solution": result["your_solution"],
            }

        except APITimeoutError:
            self.logger.error("Claude API timeout")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": "Claude API timeout",
            }
        except APIError as e:
            self.logger.error(f"Claude API error: {e}")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": f"Claude API error: {str(e)}",
            }
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Claude response: {e}")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": "Failed to parse Claude response",
            }
        except Exception as e:
            self.logger.error(f"Claude verification error: {e}")
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "error": str(e),
            }

    def verify_distractors(self, variant: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Verify that all distractors are definitively wrong.

        Args:
            variant: Question variant with options

        Returns:
            List of distractor analyses
        """
        answer_idx = variant.get("answer_index", 0)
        correct_answer = variant["options"][answer_idx]

        distractor_analysis = []

        for i, option in enumerate(variant["options"]):
            if i == answer_idx:
                continue  # Skip correct answer

            try:
                # Extract expressions from both
                correct_expr_str = self._extract_solution_expression(correct_answer)
                distractor_expr_str = self._extract_solution_expression(option)

                # Preprocess expressions
                correct_expr_str = self._preprocess_math_expression(correct_expr_str)
                distractor_expr_str = self._preprocess_math_expression(distractor_expr_str)

                # Symbolic comparison
                correct_expr = sympify(correct_expr_str)
                distractor_expr = sympify(distractor_expr_str)

                diff = simplify(correct_expr - distractor_expr)

                if diff == 0:
                    # CRITICAL: Distractor equals correct answer!
                    distractor_analysis.append(
                        {
                            "option_index": i,
                            "value": option,
                            "is_wrong": False,
                            "reason": "CRITICAL: Distractor equals correct answer",
                            "issue_type": "duplicate_correct",
                        }
                    )
                else:
                    distractor_analysis.append(
                        {
                            "option_index": i,
                            "value": option,
                            "is_wrong": True,
                            "reason": self._infer_mistake_type(diff),
                            "symbolic_difference": str(diff),
                        }
                    )

            except Exception as e:
                # Fallback: assume different if can't parse
                self.logger.debug(f"Distractor parse error for '{option}': {e}")
                distractor_analysis.append(
                    {
                        "option_index": i,
                        "value": option,
                        "is_wrong": True,
                        "reason": "Parse error (assumed different from correct)",
                        "parse_error": str(e),
                    }
                )

        return distractor_analysis

    def _detect_operation(self, stimulus: str) -> str:
        """Detect mathematical operation type from question text.

        Args:
            stimulus: Question text

        Returns:
            Operation type (derivative, integral, limit, solve, etc.)
        """
        stimulus_lower = stimulus.lower()

        if any(
            keyword in stimulus_lower
            for keyword in ["derivative", "f'(x)", "f'", "differentiate", "dy/dx"]
        ):
            return "derivative"
        elif any(
            keyword in stimulus_lower
            for keyword in ["integral", "integrate", "antiderivative", "∫"]
        ):
            return "integral"
        elif "limit" in stimulus_lower or "lim" in stimulus_lower:
            return "limit"
        elif any(keyword in stimulus_lower for keyword in ["solve", "find x", "x ="]):
            return "solve"
        else:
            return "unknown"

    def _extract_function(self, question: str) -> str:
        """Extract function expression from question text.

        Args:
            question: Question text

        Returns:
            Function expression string
        """
        # Match "f(var) = ..." pattern (supports any variable)
        match = re.search(r"f\(([a-zA-Z])\)\s*=\s*(.+?)(?:[.\?,]|$)", question)
        if match:
            return match.group(2).strip()

        # Match "y = ..." pattern
        match = re.search(r"y\s*=\s*(.+?)(?:[.\?,]|$)", question)
        if match:
            return match.group(1).strip()

        return ""

    def _extract_solution_expression(self, solution: str) -> str:
        """Extract mathematical expression from solution string.

        Handles formats like:
        - "f'(x) = 12x^2" -> "12x^2"
        - "12x^2" -> "12x^2"
        - "y' = 5x + 3" -> "5x + 3"

        Args:
            solution: Solution string

        Returns:
            Mathematical expression
        """
        # Match "f'(var) = ..." pattern
        match = re.search(r"f['\u2032]\([a-zA-Z]\)\s*=\s*(.+?)$", solution)
        if match:
            return match.group(1).strip()

        # Match "y' = ..." pattern
        match = re.search(r"y['\u2032]\s*=\s*(.+?)$", solution)
        if match:
            return match.group(1).strip()

        # No pattern match - return as is
        return solution.strip()

    def _preprocess_math_expression(self, expr: str) -> str:
        """Preprocess mathematical expression for SymPy.

        Converts common mathematical notation to SymPy-compatible format:
        - Replaces ^ with ** for exponents
        - Handles implicit multiplication (e.g., 4t -> 4*t, 12t^2 -> 12*t**2)

        Args:
            expr: Mathematical expression string

        Returns:
            Preprocessed expression string
        """
        # Replace ^ with **
        expr = expr.replace("^", "**")

        # Add implicit multiplication between number and variable
        # e.g., "4t" -> "4*t", "12t**2" -> "12*t**2"
        expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)

        return expr

    def _extract_limit_point(self, question: str) -> Optional[float]:
        """Extract limit point from question text.

        Args:
            question: Question text

        Returns:
            Limit point (number or infinity)
        """
        # Match "as x → 0" or "x approaches 0"
        match = re.search(r"x\s*(?:→|approaches?)\s*(\d+|∞|infinity)", question.lower())
        if match:
            point_str = match.group(1)
            if point_str in ["∞", "infinity"]:
                return float("inf")
            return float(point_str)
        return None

    def _infer_mistake_type(self, symbolic_diff) -> str:
        """Infer student misconception from symbolic difference.

        Args:
            symbolic_diff: Symbolic difference between correct and distractor

        Returns:
            Mistake type description
        """
        diff_str = str(symbolic_diff)

        if "x" not in diff_str:
            return "Coefficient error"
        elif "sin" in diff_str or "cos" in diff_str or "tan" in diff_str:
            return "Trigonometric error"
        elif diff_str.count("x") > 1:
            return "Product/chain rule confusion"
        elif "**" in diff_str or "^" in diff_str:
            return "Exponent error"
        else:
            return "Algebraic error"

    def _aggregate_results(self, methods: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate results from multiple verification methods.

        Args:
            methods: List of method results

        Returns:
            Consensus result
        """
        # Filter out errors
        valid_methods = [m for m in methods if m["status"] in ["PASS", "FAIL"]]

        if not valid_methods:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "all_methods_agree": False,
                "reason": "All methods failed",
            }

        # Check consensus
        statuses = [m["status"] for m in valid_methods]

        if all(s == "PASS" for s in statuses):
            # All agree: PASS
            confidence = np.mean([m["confidence"] for m in valid_methods])
            return {
                "status": "PASS",
                "confidence": float(confidence),
                "all_methods_agree": True,
            }
        elif all(s == "FAIL" for s in statuses):
            # All agree: FAIL
            confidence = np.mean([m["confidence"] for m in valid_methods])
            return {
                "status": "FAIL",
                "confidence": float(confidence),
                "all_methods_agree": True,
            }
        else:
            # Disagreement - use symbolic as primary tiebreaker
            symbolic_result = next(
                (m for m in methods if "symbolic" in str(m).lower()), None
            )
            if symbolic_result and symbolic_result["status"] in ["PASS", "FAIL"]:
                return {
                    "status": symbolic_result["status"],
                    "confidence": 0.5,  # Low confidence due to disagreement
                    "all_methods_agree": False,
                    "reason": "Methods disagree, using symbolic as tiebreaker",
                }
            else:
                # No symbolic result, use majority vote
                pass_count = sum(1 for s in statuses if s == "PASS")
                fail_count = sum(1 for s in statuses if s == "FAIL")
                status = "PASS" if pass_count > fail_count else "FAIL"
                return {
                    "status": status,
                    "confidence": 0.6,
                    "all_methods_agree": False,
                    "reason": "Using majority vote",
                }

    def _collect_issues(
        self,
        consensus: Dict[str, Any],
        distractors: List[Dict[str, Any]],
        symbolic: Dict[str, Any],
        numerical: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Collect verification issues.

        Args:
            consensus: Consensus result
            distractors: Distractor analysis
            symbolic: Symbolic result
            numerical: Numerical result

        Returns:
            List of issues
        """
        issues = []

        # Check if answer is wrong
        if consensus["status"] == "FAIL":
            issue = {
                "severity": "CRITICAL",
                "type": "wrong_answer",
                "description": "Claimed answer does not match computed solution",
            }

            if symbolic["status"] != "ERROR":
                issue["evidence"] = {
                    "symbolic_expected": symbolic.get("expected", ""),
                    "symbolic_got": symbolic.get("got", ""),
                }

            if numerical["status"] != "ERROR" and "failed_samples" in numerical:
                issue["evidence"]["numerical_samples"] = numerical["failed_samples"]

            issues.append(issue)

        # Check for duplicate correct answers
        duplicate_correct = [d for d in distractors if not d["is_wrong"]]
        if duplicate_correct:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "type": "duplicate_correct_answer",
                    "description": "One or more distractors are identical to correct answer",
                    "distractors": duplicate_correct,
                }
            )

        return issues

    def _collect_warnings(
        self,
        consensus: Dict[str, Any],
        symbolic: Dict[str, Any],
        numerical: Dict[str, Any],
        claude: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Collect verification warnings.

        Args:
            consensus: Consensus result
            symbolic: Symbolic result
            numerical: Numerical result
            claude: Claude result (optional)

        Returns:
            List of warnings
        """
        warnings = []

        # Low confidence warning
        if consensus["confidence"] < 0.8:
            warnings.append(
                {
                    "type": "low_confidence",
                    "message": f"Verification confidence is low: {consensus['confidence']:.2f}",
                }
            )

        # Disagreement warning
        if not consensus.get("all_methods_agree", True):
            warnings.append(
                {
                    "type": "method_disagreement",
                    "message": "Verification methods disagree",
                    "symbolic": symbolic["status"],
                    "numerical": numerical["status"],
                    "claude": claude["status"] if claude else None,
                }
            )

        # Error warnings
        if symbolic["status"] == "ERROR":
            warnings.append(
                {
                    "type": "symbolic_error",
                    "message": symbolic.get("error", "Symbolic verification failed"),
                }
            )

        if numerical["status"] == "ERROR":
            warnings.append(
                {
                    "type": "numerical_error",
                    "message": numerical.get("error", "Numerical verification failed"),
                }
            )

        return warnings


# Batch verification function
def verify_batch(
    variants: List[Dict[str, Any]], verifier: Optional[SolutionVerifier] = None
) -> Dict[str, Any]:
    """Verify a batch of variants.

    Args:
        variants: List of question variants
        verifier: SolutionVerifier instance (creates new if None)

    Returns:
        Batch verification results
    """
    if verifier is None:
        verifier = SolutionVerifier()

    passed = []
    failed = []
    needs_review = []

    for variant in variants:
        result = verifier.verify_variant(variant)

        if (
            result["verification_status"] == "PASS"
            and result["consensus"]["confidence"] > 0.95
        ):
            passed.append(variant)
        elif result["verification_status"] == "FAIL":
            failed.append((variant, result))
        else:
            # Low confidence or contradictory results
            needs_review.append((variant, result))

    return {
        "passed": passed,
        "failed": failed,
        "needs_review": needs_review,
        "summary": {
            "total": len(variants),
            "passed": len(passed),
            "failed": len(failed),
            "needs_review": len(needs_review),
            "pass_rate": len(passed) / len(variants) if variants else 0.0,
        },
    }
