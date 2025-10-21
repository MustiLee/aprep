"""
Difficulty Calibrator Agent

This agent implements IRT-lite (2-Parameter Logistic model) for difficulty estimation
of MCQ variants. It provides initial difficulty estimates, maintains anchor items,
and handles cold-start scenarios for new questions.

Responsibilities:
- Initial difficulty estimation for new variants
- IRT-lite calibration using 2PL model
- Anchor item management per topic
- Cold-start handling for new content
- Difficulty updating based on student performance
- Export calibrated parameters
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from uuid import uuid4
import math

import numpy as np
from scipy.optimize import minimize
from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError

logger = setup_logger(__name__)


class IRTParameters(BaseModel):
    """IRT 2PL model parameters for an item"""

    item_id: str = Field(..., description="Question variant ID")
    a: float = Field(..., description="Discrimination parameter (0.5-2.5 typical)")
    b: float = Field(..., description="Difficulty parameter (-3 to +3 typical)")

    se_a: Optional[float] = Field(None, description="Standard error of a")
    se_b: Optional[float] = Field(None, description="Standard error of b")

    n_responses: int = Field(default=0, description="Number of student responses")
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())

    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnchorItem(BaseModel):
    """An anchor item for a topic (well-calibrated reference)"""

    item_id: str
    topic_id: str
    course_id: str

    irt_params: IRTParameters

    is_validated: bool = Field(default=False)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ResponseData(BaseModel):
    """Student response data for calibration"""

    student_id: str
    item_id: str
    correct: bool
    response_time_seconds: Optional[float] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DifficultyCalibrator:
    """
    Implements IRT-lite (2PL model) for difficulty calibration of MCQ variants.

    The 2PL model: P(correct | θ, a, b) = 1 / (1 + exp(-a(θ - b)))
    where:
    - θ (theta) = student ability
    - a = discrimination (how well item differentiates ability levels)
    - b = difficulty (ability level needed for 50% success probability)
    """

    def __init__(
        self,
        data_dir: str = "data/irt",
        models_dir: str = "models/irt"
    ):
        """
        Initialize the Difficulty Calibrator.

        Args:
            data_dir: Directory for IRT data storage
            models_dir: Directory for saved models
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize item parameters
        self.item_params_file = self.models_dir / "item_parameters.json"
        self.item_params: Dict[str, IRTParameters] = self._load_item_params()

        # Load or initialize anchor items
        self.anchors_file = self.models_dir / "anchor_items.json"
        self.anchor_items: Dict[str, List[AnchorItem]] = self._load_anchors()

        # Create empty files if they don't exist
        if not self.item_params_file.exists():
            self._save_item_params()
        if not self.anchors_file.exists():
            self._save_anchors()

        logger.info("Initialized DifficultyCalibrator with IRT-lite (2PL model)")

    def estimate_initial_difficulty(
        self,
        variant: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> IRTParameters:
        """
        Estimate initial difficulty for a new variant using heuristics.

        Args:
            variant: Question variant dictionary
            context: Additional context (topic, LOs, etc.)

        Returns:
            Initial IRT parameters

        The initial estimates are based on:
        1. Topic-level anchor items (if available)
        2. Template-level average (if template has calibrated variants)
        3. Heuristic features (number of steps, complexity indicators)
        4. Default values for completely new content
        """
        try:
            item_id = variant.get("id", str(uuid4()))

            # Try to use anchor items from same topic
            if context and "topic_id" in context:
                topic_id = context["topic_id"]
                anchors = self.get_topic_anchors(topic_id)

                if anchors:
                    # Use median anchor difficulty
                    anchor_bs = [anchor.irt_params.b for anchor in anchors]
                    anchor_as = [anchor.irt_params.a for anchor in anchors]

                    initial_b = np.median(anchor_bs)
                    initial_a = np.median(anchor_as)

                    logger.info(f"Using anchor-based initial estimate: b={initial_b:.2f}, a={initial_a:.2f}")

                    return IRTParameters(
                        item_id=item_id,
                        a=initial_a,
                        b=initial_b,
                        n_responses=0,
                        metadata={"estimation_method": "anchor_based"}
                    )

            # Try template-level average
            template_id = variant.get("template_id")
            if template_id:
                template_params = self._get_template_average_params(template_id)
                if template_params:
                    logger.info(f"Using template-based estimate: b={template_params['b']:.2f}")
                    return IRTParameters(
                        item_id=item_id,
                        a=template_params["a"],
                        b=template_params["b"],
                        n_responses=0,
                        metadata={"estimation_method": "template_based"}
                    )

            # Heuristic-based estimation
            complexity_score = self._estimate_complexity(variant)

            # Map complexity to difficulty (-3 to +3 scale)
            # complexity 0-1 maps to difficulty -2 to +2
            initial_b = (complexity_score - 0.5) * 4  # Range: -2 to +2

            # Default discrimination
            initial_a = 1.0

            logger.info(f"Using heuristic-based estimate: b={initial_b:.2f}, a={initial_a:.2f}")

            return IRTParameters(
                item_id=item_id,
                a=initial_a,
                b=initial_b,
                n_responses=0,
                metadata={
                    "estimation_method": "heuristic",
                    "complexity_score": complexity_score
                }
            )

        except Exception as e:
            logger.error(f"Failed to estimate initial difficulty: {e}")
            # Return default moderate difficulty
            return IRTParameters(
                item_id=variant.get("id", str(uuid4())),
                a=1.0,
                b=0.0,
                n_responses=0,
                metadata={"estimation_method": "default"}
            )

    def calibrate_from_responses(
        self,
        item_id: str,
        responses: List[ResponseData],
        student_abilities: Optional[Dict[str, float]] = None
    ) -> IRTParameters:
        """
        Calibrate item parameters using student response data.

        Args:
            item_id: Item to calibrate
            responses: List of student responses
            student_abilities: Optional dict of student_id -> ability estimates

        Returns:
            Calibrated IRT parameters
        """
        try:
            if len(responses) < 10:
                logger.warning(f"Insufficient responses ({len(responses)}) for reliable calibration")

            # Get current parameters or use defaults
            current_params = self.item_params.get(
                item_id,
                IRTParameters(item_id=item_id, a=1.0, b=0.0)
            )

            # If no student abilities provided, estimate from responses
            if student_abilities is None:
                student_abilities = self._estimate_student_abilities(responses)

            # Prepare data
            y = np.array([1 if r.correct else 0 for r in responses])
            theta = np.array([student_abilities.get(r.student_id, 0.0) for r in responses])

            # Optimize parameters using MLE
            def negative_log_likelihood(params):
                a, b = params
                prob = self._irt_2pl(theta, a, b)
                # Avoid log(0)
                prob = np.clip(prob, 1e-10, 1 - 1e-10)
                ll = np.sum(y * np.log(prob) + (1 - y) * np.log(1 - prob))
                return -ll

            # Initial guess
            initial_guess = [current_params.a, current_params.b]

            # Bounds: a in [0.1, 3.0], b in [-4, 4]
            bounds = [(0.1, 3.0), (-4.0, 4.0)]

            # Optimize
            result = minimize(
                negative_log_likelihood,
                initial_guess,
                bounds=bounds,
                method='L-BFGS-B'
            )

            if result.success:
                a_new, b_new = result.x

                # Estimate standard errors from Hessian
                # (simplified - could use more sophisticated methods)
                se_a = 0.1  # Placeholder
                se_b = 0.1  # Placeholder

                calibrated_params = IRTParameters(
                    item_id=item_id,
                    a=float(a_new),
                    b=float(b_new),
                    se_a=se_a,
                    se_b=se_b,
                    n_responses=len(responses),
                    metadata={"calibration_method": "mle_2pl"}
                )

                # Save
                self.item_params[item_id] = calibrated_params
                self._save_item_params()

                logger.info(f"Calibrated item {item_id}: a={a_new:.2f}, b={b_new:.2f}")
                return calibrated_params

            else:
                logger.warning(f"Calibration optimization failed: {result.message}")
                return current_params

        except Exception as e:
            logger.error(f"Failed to calibrate item {item_id}: {e}")
            return self.item_params.get(
                item_id,
                IRTParameters(item_id=item_id, a=1.0, b=0.0)
            )

    def update_difficulty_online(
        self,
        item_id: str,
        response: ResponseData,
        student_ability: float,
        learning_rate: float = 0.1
    ) -> IRTParameters:
        """
        Online update of difficulty using exponential moving average.

        Useful for incremental updates without full re-calibration.

        Args:
            item_id: Item to update
            response: New response data
            student_ability: Estimated ability of student
            learning_rate: Update rate (0-1)

        Returns:
            Updated parameters
        """
        try:
            params = self.item_params.get(
                item_id,
                IRTParameters(item_id=item_id, a=1.0, b=0.0)
            )

            # Predicted probability
            p_pred = self._irt_2pl(student_ability, params.a, params.b)

            # Actual outcome
            y_actual = 1.0 if response.correct else 0.0

            # Error
            error = y_actual - p_pred

            # Update difficulty (b) based on error
            # If error is positive (easier than expected), decrease b
            # If error is negative (harder than expected), increase b
            b_new = params.b - learning_rate * error * params.a

            # Clip to reasonable range
            b_new = np.clip(b_new, -4.0, 4.0)

            # Update discrimination (a) based on response consistency
            # (simplified - could use more sophisticated methods)
            a_new = params.a

            params.a = float(a_new)
            params.b = float(b_new)
            params.n_responses += 1
            params.last_updated = datetime.now().isoformat()

            self.item_params[item_id] = params
            self._save_item_params()

            logger.debug(f"Online update for {item_id}: b={b_new:.2f}")

            return params

        except Exception as e:
            logger.error(f"Failed to update difficulty for {item_id}: {e}")
            return self.item_params.get(
                item_id,
                IRTParameters(item_id=item_id, a=1.0, b=0.0)
            )

    def add_anchor_item(
        self,
        item_id: str,
        topic_id: str,
        course_id: str,
        irt_params: Optional[IRTParameters] = None,
        validate: bool = False
    ) -> AnchorItem:
        """
        Add an item as an anchor for a topic.

        Args:
            item_id: Item to use as anchor
            topic_id: Topic identifier
            course_id: Course identifier
            irt_params: Optional pre-calibrated parameters
            validate: Whether to validate anchor quality

        Returns:
            AnchorItem object
        """
        try:
            # Get or use provided parameters
            if irt_params is None:
                irt_params = self.item_params.get(item_id)

            if irt_params is None:
                raise AprepError(f"No IRT parameters found for item {item_id}")

            # Create anchor
            anchor = AnchorItem(
                item_id=item_id,
                topic_id=topic_id,
                course_id=course_id,
                irt_params=irt_params,
                is_validated=validate
            )

            # Add to anchors
            topic_key = f"{course_id}:{topic_id}"
            if topic_key not in self.anchor_items:
                self.anchor_items[topic_key] = []

            self.anchor_items[topic_key].append(anchor)
            self._save_anchors()

            logger.info(f"Added anchor item {item_id} for topic {topic_id}")
            return anchor

        except Exception as e:
            logger.error(f"Failed to add anchor item: {e}")
            raise AprepError(f"Anchor item addition failed: {e}")

    def get_topic_anchors(self, topic_id: str, course_id: Optional[str] = None) -> List[AnchorItem]:
        """Get anchor items for a topic"""
        if course_id:
            topic_key = f"{course_id}:{topic_id}"
            return self.anchor_items.get(topic_key, [])
        else:
            # Search all courses
            results = []
            for key, anchors in self.anchor_items.items():
                if key.endswith(f":{topic_id}"):
                    results.extend(anchors)
            return results

    def get_item_probability(
        self,
        item_id: str,
        student_ability: float
    ) -> float:
        """
        Get probability of correct response for a student ability level.

        Args:
            item_id: Item identifier
            student_ability: Student ability (theta)

        Returns:
            Probability of correct response (0-1)
        """
        params = self.item_params.get(item_id)

        if params is None:
            # No calibration - assume moderate difficulty
            return 0.5

        return self._irt_2pl(student_ability, params.a, params.b)

    def recommend_items_by_difficulty(
        self,
        target_difficulty: float,
        topic_id: Optional[str] = None,
        count: int = 5,
        tolerance: float = 0.5
    ) -> List[Tuple[str, IRTParameters]]:
        """
        Recommend items matching target difficulty.

        Args:
            target_difficulty: Target difficulty (b parameter)
            topic_id: Optional topic filter
            count: Number of recommendations
            tolerance: Difficulty tolerance range

        Returns:
            List of (item_id, params) tuples
        """
        candidates = []

        for item_id, params in self.item_params.items():
            # Check difficulty range
            if abs(params.b - target_difficulty) <= tolerance:
                # Filter by topic if specified
                if topic_id:
                    # Would need topic metadata in params
                    pass

                candidates.append((item_id, params, abs(params.b - target_difficulty)))

        # Sort by closeness to target
        candidates.sort(key=lambda x: x[2])

        # Return top matches
        return [(item_id, params) for item_id, params, _ in candidates[:count]]

    def get_statistics(self) -> Dict[str, Any]:
        """Get calibration statistics"""
        if not self.item_params:
            return {}

        all_as = [p.a for p in self.item_params.values()]
        all_bs = [p.b for p in self.item_params.values()]

        calibrated = [p for p in self.item_params.values() if p.n_responses >= 10]

        return {
            "total_items": len(self.item_params),
            "calibrated_items": len(calibrated),
            "difficulty_mean": float(np.mean(all_bs)),
            "difficulty_std": float(np.std(all_bs)),
            "difficulty_range": [float(np.min(all_bs)), float(np.max(all_bs))],
            "discrimination_mean": float(np.mean(all_as)),
            "discrimination_std": float(np.std(all_as)),
            "total_anchors": sum(len(anchors) for anchors in self.anchor_items.values())
        }

    def _irt_2pl(self, theta: float, a: float, b: float) -> float:
        """
        2-Parameter Logistic IRT model.

        P(correct | θ, a, b) = 1 / (1 + exp(-a(θ - b)))
        """
        if isinstance(theta, np.ndarray):
            return 1.0 / (1.0 + np.exp(-a * (theta - b)))
        else:
            return 1.0 / (1.0 + math.exp(-a * (theta - b)))

    def _estimate_complexity(self, variant: Dict[str, Any]) -> float:
        """
        Estimate complexity from variant features (0-1 scale).

        Factors:
        - Number of steps in solution
        - Mathematical operations complexity
        - Text length
        """
        complexity = 0.5  # Default moderate

        # Check solution steps
        solution = variant.get("solution", "")
        if solution:
            # Count mathematical expressions
            import re
            math_exprs = len(re.findall(r'\$.*?\$', solution))
            complexity += min(math_exprs * 0.05, 0.3)

        # Check stimulus length
        stimulus = variant.get("stimulus", "")
        if len(stimulus) > 200:
            complexity += 0.1

        # Clip to 0-1
        return np.clip(complexity, 0.0, 1.0)

    def _estimate_student_abilities(
        self,
        responses: List[ResponseData]
    ) -> Dict[str, float]:
        """
        Estimate student abilities from response patterns.

        Simple approach: proportion correct mapped to logit scale.
        """
        student_scores = {}

        for response in responses:
            if response.student_id not in student_scores:
                student_scores[response.student_id] = []
            student_scores[response.student_id].append(1 if response.correct else 0)

        abilities = {}
        for student_id, scores in student_scores.items():
            prop_correct = np.mean(scores)
            # Map to logit scale (-3 to +3)
            # Clip to avoid infinity
            prop_correct = np.clip(prop_correct, 0.05, 0.95)
            ability = np.log(prop_correct / (1 - prop_correct))
            abilities[student_id] = float(ability)

        return abilities

    def _get_template_average_params(self, template_id: str) -> Optional[Dict[str, float]]:
        """Get average parameters for variants of a template"""
        template_params = [
            p for p in self.item_params.values()
            if p.metadata.get("template_id") == template_id and p.n_responses >= 5
        ]

        if not template_params:
            return None

        return {
            "a": float(np.mean([p.a for p in template_params])),
            "b": float(np.mean([p.b for p in template_params]))
        }

    def _load_item_params(self) -> Dict[str, IRTParameters]:
        """Load item parameters from file"""
        if not self.item_params_file.exists():
            return {}

        try:
            with open(self.item_params_file, 'r') as f:
                data = json.load(f)

            return {k: IRTParameters(**v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load item parameters: {e}")
            return {}

    def _save_item_params(self) -> None:
        """Save item parameters to file"""
        try:
            data = {k: v.model_dump() for k, v in self.item_params.items()}

            with open(self.item_params_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save item parameters: {e}")

    def _load_anchors(self) -> Dict[str, List[AnchorItem]]:
        """Load anchor items from file"""
        if not self.anchors_file.exists():
            return {}

        try:
            with open(self.anchors_file, 'r') as f:
                data = json.load(f)

            return {k: [AnchorItem(**item) for item in v] for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load anchors: {e}")
            return {}

    def _save_anchors(self) -> None:
        """Save anchor items to file"""
        try:
            data = {k: [item.model_dump() for item in v] for k, v in self.anchor_items.items()}

            with open(self.anchors_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save anchors: {e}")
