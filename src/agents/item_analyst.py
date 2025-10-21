"""
Item Analyst Agent

This agent performs statistical analysis on test items to evaluate their quality and
effectiveness. It calculates key item statistics like p-values, discrimination indices,
and distractor effectiveness.

Responsibilities:
- Calculate p-values (proportion correct)
- Compute point-biserial correlation (discrimination)
- Analyze distractor effectiveness
- Flag problematic items
- Integrate with Difficulty Calibrator for ability estimates
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import math

from pydantic import BaseModel, Field
import numpy as np

from src.core.logger import setup_logger
from src.core.exceptions import AprepError
from src.agents.difficulty_calibrator import DifficultyCalibrator

logger = setup_logger(__name__)


class DistractorStats(BaseModel):
    """Statistics for a distractor"""

    distractor_id: str = Field(..., description="Distractor identifier")
    selection_count: int = Field(..., ge=0, description="Number of times selected")
    selection_rate: float = Field(..., ge=0.0, le=1.0, description="Selection rate")

    # Point-biserial for distractor (negative expected)
    point_biserial: Optional[float] = Field(None, description="Point-biserial correlation")

    is_problematic: bool = Field(default=False, description="Whether distractor is problematic")
    issue_type: Optional[str] = Field(None, description="Type of problem if any")


class ItemStatistics(BaseModel):
    """Statistical analysis results for an item"""

    item_id: str = Field(..., description="Item/question identifier")

    # Basic statistics
    n_responses: int = Field(..., ge=0, description="Total responses")
    n_correct: int = Field(..., ge=0, description="Number correct")
    p_value: float = Field(..., ge=0.0, le=1.0, description="Proportion correct")

    # Discrimination
    point_biserial: Optional[float] = Field(None, description="Point-biserial correlation")
    discrimination_index: Optional[float] = Field(None, description="Upper-lower discrimination")

    # Distractor analysis
    distractor_stats: List[DistractorStats] = Field(default_factory=list)

    # Quality flags
    is_problematic: bool = Field(default=False, description="Whether item is problematic")
    issues: List[str] = Field(default_factory=list, description="List of issues found")

    # Recommendations
    recommendations: List[str] = Field(default_factory=list)

    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ItemAnalyst:
    """
    Analyzes test items using classical test theory statistics.
    """

    def __init__(
        self,
        difficulty_calibrator: Optional[DifficultyCalibrator] = None,
        min_p_value: float = 0.20,
        max_p_value: float = 0.80,
        min_discrimination: float = 0.30
    ):
        """
        Initialize Item Analyst.

        Args:
            difficulty_calibrator: DifficultyCalibrator for ability estimates
            min_p_value: Minimum acceptable p-value (default 0.20)
            max_p_value: Maximum acceptable p-value (default 0.80)
            min_discrimination: Minimum acceptable discrimination (default 0.30)
        """
        self.difficulty_calibrator = difficulty_calibrator
        self.min_p_value = min_p_value
        self.max_p_value = max_p_value
        self.min_discrimination = min_discrimination

        # Analysis history
        self.analysis_history = []

        logger.info(
            f"Initialized ItemAnalyst (p_range={min_p_value}-{max_p_value}, "
            f"min_disc={min_discrimination})"
        )

    def analyze_item(
        self,
        item_id: str,
        responses: List[Dict[str, Any]],
        correct_answer: str,
        distractors: Optional[List[str]] = None
    ) -> ItemStatistics:
        """
        Analyze an item based on response data.

        Args:
            item_id: Item identifier
            responses: List of response dicts with 'student_id', 'answer', 'ability' (optional)
            correct_answer: The correct answer
            distractors: List of distractor identifiers

        Returns:
            ItemStatistics with analysis results
        """
        try:
            if not responses:
                raise AprepError("No responses provided for analysis")

            n_responses = len(responses)

            # Calculate p-value (proportion correct)
            n_correct = sum(1 for r in responses if r.get("answer") == correct_answer)
            p_value = n_correct / n_responses

            # Calculate point-biserial correlation
            point_biserial = self._calculate_point_biserial(responses, correct_answer)

            # Calculate discrimination index if we have ability estimates
            discrimination_index = self._calculate_discrimination_index(
                responses, correct_answer
            )

            # Analyze distractors
            distractor_stats_list = []
            if distractors:
                distractor_stats_list = self._analyze_distractors(
                    responses, distractors, correct_answer
                )

            # Identify issues
            issues = []
            recommendations = []

            # Check p-value
            if p_value < self.min_p_value:
                issues.append(f"P-value too low ({p_value:.2f}): Item may be too difficult")
                recommendations.append("Consider revising item to reduce difficulty")
            elif p_value > self.max_p_value:
                issues.append(f"P-value too high ({p_value:.2f}): Item may be too easy")
                recommendations.append("Consider revising item to increase difficulty")

            # Check discrimination
            if point_biserial is not None and point_biserial < self.min_discrimination:
                issues.append(
                    f"Low discrimination ({point_biserial:.2f}): "
                    f"Item does not differentiate well between high/low performers"
                )
                recommendations.append("Review item for ambiguity or review distractors")

            if point_biserial is not None and point_biserial < 0:
                issues.append(
                    f"Negative discrimination ({point_biserial:.2f}): "
                    f"Low performers are answering correctly more than high performers"
                )
                recommendations.append("CRITICAL: Review item - may have wrong answer key")

            # Check for problematic distractors
            problematic_distractors = [d for d in distractor_stats_list if d.is_problematic]
            if problematic_distractors:
                issues.append(
                    f"{len(problematic_distractors)} problematic distractor(s) found"
                )
                recommendations.append("Review flagged distractors")

            is_problematic = len(issues) > 0

            stats = ItemStatistics(
                item_id=item_id,
                n_responses=n_responses,
                n_correct=n_correct,
                p_value=p_value,
                point_biserial=point_biserial,
                discrimination_index=discrimination_index,
                distractor_stats=distractor_stats_list,
                is_problematic=is_problematic,
                issues=issues,
                recommendations=recommendations,
                metadata={
                    "correct_answer": correct_answer,
                    "n_distractors": len(distractors) if distractors else 0
                }
            )

            # Record in history
            self.analysis_history.append({
                "item_id": item_id,
                "analyzed_at": stats.analyzed_at,
                "p_value": p_value,
                "point_biserial": point_biserial,
                "is_problematic": is_problematic
            })

            disc_str = f"{point_biserial:.2f}" if point_biserial is not None else "N/A"
            logger.info(
                f"Analyzed item {item_id}: p={p_value:.2f}, "
                f"disc={disc_str}, "
                f"problematic={is_problematic}"
            )

            return stats

        except Exception as e:
            logger.error(f"Item analysis failed: {e}")
            raise AprepError(f"Failed to analyze item: {e}")

    def _calculate_point_biserial(
        self,
        responses: List[Dict[str, Any]],
        correct_answer: str
    ) -> Optional[float]:
        """
        Calculate point-biserial correlation.

        This measures how well the item discriminates between high and low performers.
        """
        # Need ability scores for point-biserial
        abilities = [r.get("ability") for r in responses]

        if None in abilities:
            # Try to estimate abilities from difficulty calibrator
            if self.difficulty_calibrator:
                # For simplicity, use total score as proxy
                abilities = [r.get("total_score", 0.0) for r in responses]
            else:
                return None

        abilities = np.array(abilities, dtype=float)

        # Binary scores (1 = correct, 0 = incorrect)
        scores = np.array([
            1.0 if r.get("answer") == correct_answer else 0.0
            for r in responses
        ])

        # Calculate point-biserial correlation
        if len(np.unique(scores)) < 2:
            # All same answer, can't calculate
            return None

        # Point-biserial formula
        mean_correct = np.mean(abilities[scores == 1])
        mean_incorrect = np.mean(abilities[scores == 0])
        std_total = np.std(abilities, ddof=1)

        if std_total == 0:
            return None

        n_correct = np.sum(scores)
        n_total = len(scores)

        p = n_correct / n_total
        q = 1 - p

        rpb = ((mean_correct - mean_incorrect) / std_total) * math.sqrt(p * q)

        return float(rpb)

    def _calculate_discrimination_index(
        self,
        responses: List[Dict[str, Any]],
        correct_answer: str
    ) -> Optional[float]:
        """
        Calculate upper-lower discrimination index.

        Compares performance of top 27% vs bottom 27% of students.
        """
        # Need ability or total_score
        abilities = []
        for r in responses:
            ability = r.get("ability")
            if ability is None:
                ability = r.get("total_score")
            abilities.append(ability)

        if any(a is None for a in abilities) or len(responses) < 10:
            return None

        # Sort by ability
        sorted_responses = sorted(
            zip(responses, abilities),
            key=lambda x: x[1],
            reverse=True
        )

        # Top and bottom 27% (or at least 3 if small sample)
        n = len(sorted_responses)
        group_size = max(3, int(n * 0.27))

        upper_group = sorted_responses[:group_size]
        lower_group = sorted_responses[-group_size:]

        # Calculate proportion correct in each group
        p_upper = sum(
            1 for r, _ in upper_group if r.get("answer") == correct_answer
        ) / len(upper_group)

        p_lower = sum(
            1 for r, _ in lower_group if r.get("answer") == correct_answer
        ) / len(lower_group)

        discrimination = p_upper - p_lower

        return float(discrimination)

    def _analyze_distractors(
        self,
        responses: List[Dict[str, Any]],
        distractors: List[str],
        correct_answer: str
    ) -> List[DistractorStats]:
        """
        Analyze effectiveness of distractors.
        """
        distractor_stats_list = []
        n_responses = len(responses)

        # Get abilities if available
        abilities = np.array([
            r.get("ability") or r.get("total_score", 0.0)
            for r in responses
        ], dtype=float)

        for distractor in distractors:
            # Count selections
            selection_count = sum(1 for r in responses if r.get("answer") == distractor)
            selection_rate = selection_count / n_responses if n_responses > 0 else 0.0

            # Calculate point-biserial for distractor (should be negative)
            distractor_pb = None
            if selection_count > 0 and len(np.unique(abilities)) > 1:
                scores = np.array([
                    1.0 if r.get("answer") == distractor else 0.0
                    for r in responses
                ])

                if len(np.unique(scores)) == 2:
                    mean_selected = np.mean(abilities[scores == 1])
                    mean_not_selected = np.mean(abilities[scores == 0])
                    std_total = np.std(abilities, ddof=1)

                    if std_total > 0:
                        p = selection_count / n_responses
                        q = 1 - p
                        distractor_pb = ((mean_selected - mean_not_selected) / std_total) * math.sqrt(p * q)

            # Flag problematic distractors
            is_problematic = False
            issue_type = None

            # Dead distractor (selected by < 5%)
            if selection_rate < 0.05:
                is_problematic = True
                issue_type = "dead_distractor"

            # Distractor too attractive (selected by > 50% - more than correct!)
            elif selection_rate > 0.50:
                is_problematic = True
                issue_type = "too_attractive"

            # Positive discrimination (attracts high performers)
            elif distractor_pb is not None and distractor_pb > 0.10:
                is_problematic = True
                issue_type = "attracts_high_performers"

            distractor_stats_list.append(DistractorStats(
                distractor_id=distractor,
                selection_count=selection_count,
                selection_rate=selection_rate,
                point_biserial=distractor_pb,
                is_problematic=is_problematic,
                issue_type=issue_type
            ))

        return distractor_stats_list

    def analyze_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze multiple items in batch.

        Args:
            items: List of item dicts with 'item_id', 'responses', 'correct_answer', 'distractors'

        Returns:
            Batch analysis results
        """
        results = []

        for item in items:
            stats = self.analyze_item(
                item_id=item["item_id"],
                responses=item["responses"],
                correct_answer=item["correct_answer"],
                distractors=item.get("distractors")
            )
            results.append(stats)

        # Calculate batch statistics
        problematic_count = sum(1 for r in results if r.is_problematic)
        avg_p_value = sum(r.p_value for r in results) / len(results) if results else 0.0

        # Calculate average discrimination (handle all None case)
        valid_discriminations = [r.point_biserial for r in results if r.point_biserial is not None]
        avg_discrimination = (sum(valid_discriminations) / len(valid_discriminations)) if valid_discriminations else None

        return {
            "total_items": len(items),
            "problematic_items": problematic_count,
            "acceptable_items": len(items) - problematic_count,
            "avg_p_value": avg_p_value,
            "avg_discrimination": avg_discrimination,
            "results": [r.model_dump() for r in results]
        }

    def get_problematic_items(
        self,
        min_issues: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get items flagged as problematic from history.

        Args:
            min_issues: Minimum number of issues to include

        Returns:
            List of problematic item records
        """
        return [
            h for h in self.analysis_history
            if h.get("is_problematic", False)
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get analyst statistics.

        Returns:
            Statistics dictionary
        """
        if not self.analysis_history:
            return {
                "total_analyses": 0,
                "avg_p_value": 0.0,
                "avg_discrimination": None,
                "problematic_rate": 0.0
            }

        total = len(self.analysis_history)
        problematic = sum(1 for h in self.analysis_history if h.get("is_problematic"))

        p_values = [h["p_value"] for h in self.analysis_history]
        discriminations = [
            h["point_biserial"] for h in self.analysis_history
            if h.get("point_biserial") is not None
        ]

        return {
            "total_analyses": total,
            "problematic_count": problematic,
            "problematic_rate": problematic / total if total > 0 else 0.0,
            "avg_p_value": sum(p_values) / len(p_values) if p_values else 0.0,
            "avg_discrimination": (
                sum(discriminations) / len(discriminations) if discriminations else None
            ),
            "min_p_value": self.min_p_value,
            "max_p_value": self.max_p_value,
            "min_discrimination": self.min_discrimination
        }
