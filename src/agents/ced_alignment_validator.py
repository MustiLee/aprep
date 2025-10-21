"""
CED Alignment Validator Agent

This agent validates that generated questions and content align with the
College Board's Course and Exam Description (CED) standards. It ensures
curriculum compliance, learning objective mapping, and content appropriateness.

Responsibilities:
- Validate LO mapping accuracy
- Check curriculum coverage
- Calculate alignment scores (target ≥0.90)
- Flag off-topic or misaligned content
- Integrate with Taxonomy Manager and Template Crafter
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError
from src.agents.taxonomy_manager import TaxonomyManager, LearningObjective

logger = setup_logger(__name__)


class AlignmentIssue(BaseModel):
    """An alignment issue found during validation"""

    issue_type: str = Field(..., description="Type: missing_lo, wrong_topic, off_topic, weak_alignment")
    severity: str = Field(..., description="Severity: critical, warning, info")
    description: str = Field(..., description="Issue description")

    suggested_fix: Optional[str] = Field(None, description="Suggested fix")
    affected_field: Optional[str] = Field(None, description="Affected field name")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlignmentResult(BaseModel):
    """Result of CED alignment validation"""

    is_aligned: bool = Field(..., description="Whether content is aligned")
    alignment_score: float = Field(..., ge=0.0, le=1.0, description="Alignment score 0.0-1.0")

    # Validation details
    lo_matched: bool = Field(..., description="LO successfully matched")
    topic_matched: bool = Field(..., description="Topic successfully matched")
    unit_matched: bool = Field(..., description="Unit successfully matched")

    # Matched entities
    matched_lo_code: Optional[str] = Field(None, description="Matched LO code")
    matched_topic_code: Optional[str] = Field(None, description="Matched topic code")
    matched_unit_code: Optional[str] = Field(None, description="Matched unit code")

    # Issues
    issues: List[AlignmentIssue] = Field(default_factory=list)

    # Coverage tracking
    curriculum_coverage: Optional[Dict[str, Any]] = Field(None)

    validated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CEDAlignmentValidator:
    """
    Validates content alignment with CED standards using Taxonomy Manager.
    """

    def __init__(
        self,
        taxonomy_manager: Optional[TaxonomyManager] = None,
        min_alignment_score: float = 0.90
    ):
        """
        Initialize CED Alignment Validator.

        Args:
            taxonomy_manager: TaxonomyManager instance
            min_alignment_score: Minimum alignment score threshold (default 0.90)
        """
        self.taxonomy_manager = taxonomy_manager or TaxonomyManager()
        self.min_alignment_score = min_alignment_score

        # Validation statistics
        self.total_validations = 0
        self.total_aligned = 0
        self.total_misaligned = 0

        logger.info(f"Initialized CEDAlignmentValidator (min_score={min_alignment_score})")

    def validate_question(
        self,
        question_content: Dict[str, Any],
        course_id: str
    ) -> AlignmentResult:
        """
        Validate a question's alignment with CED standards.

        Args:
            question_content: Question dict with 'lo_code', 'topic_id', 'text', etc.
            course_id: Course identifier

        Returns:
            AlignmentResult with validation details
        """
        try:
            self.total_validations += 1

            issues = []

            # Extract question metadata
            lo_code = question_content.get("lo_code")
            topic_id = question_content.get("topic_id")
            unit_id = question_content.get("unit_id")
            question_text = question_content.get("text", "")

            # Validate LO
            lo_matched = False
            matched_lo = None

            if lo_code:
                matched_lo = self.taxonomy_manager.get_learning_objective(course_id, lo_code)
                if matched_lo:
                    lo_matched = True
                else:
                    issues.append(AlignmentIssue(
                        issue_type="missing_lo",
                        severity="critical",
                        description=f"LO code '{lo_code}' not found in course taxonomy",
                        suggested_fix="Verify LO code against CED",
                        affected_field="lo_code"
                    ))
            else:
                issues.append(AlignmentIssue(
                    issue_type="missing_lo",
                    severity="critical",
                    description="No LO code provided",
                    suggested_fix="Add valid LO code from CED",
                    affected_field="lo_code"
                ))

            # Validate Topic
            topic_matched = False
            matched_topic = None

            if topic_id:
                matched_topic = self.taxonomy_manager.get_topic(course_id, topic_id)
                if matched_topic:
                    topic_matched = True

                    # Verify LO is in this topic
                    if lo_matched and matched_lo:
                        topic_los = [lo.code for lo in matched_topic.learning_objectives]
                        if lo_code not in topic_los:
                            issues.append(AlignmentIssue(
                                issue_type="wrong_topic",
                                severity="warning",
                                description=f"LO '{lo_code}' not in topic '{topic_id}'",
                                suggested_fix=f"Move to correct topic or update LO",
                                affected_field="topic_id"
                            ))
                else:
                    issues.append(AlignmentIssue(
                        issue_type="missing_topic",
                        severity="critical",
                        description=f"Topic '{topic_id}' not found in course",
                        suggested_fix="Use valid topic from course taxonomy",
                        affected_field="topic_id"
                    ))

            # Validate Unit
            unit_matched = False
            matched_unit = None

            if unit_id:
                matched_unit = self.taxonomy_manager.get_unit(course_id, unit_id)
                if matched_unit:
                    unit_matched = True
                else:
                    issues.append(AlignmentIssue(
                        issue_type="missing_unit",
                        severity="warning",
                        description=f"Unit '{unit_id}' not found",
                        suggested_fix="Use valid unit code",
                        affected_field="unit_id"
                    ))

            # Content alignment check (keyword matching)
            content_aligned = True
            if lo_matched and matched_lo:
                content_score = self._check_content_alignment(
                    question_text, matched_lo
                )
                if content_score < 0.5:
                    content_aligned = False
                    issues.append(AlignmentIssue(
                        issue_type="weak_alignment",
                        severity="warning",
                        description=f"Question content weakly aligned with LO (score: {content_score:.2f})",
                        suggested_fix="Revise question to better match LO description",
                        affected_field="text"
                    ))

            # Calculate overall alignment score
            alignment_score = self._calculate_alignment_score(
                lo_matched=lo_matched,
                topic_matched=topic_matched,
                unit_matched=unit_matched,
                content_aligned=content_aligned,
                issue_count=len(issues)
            )

            # Determine if aligned
            # Must have LO and topic matched, no critical issues, and meet min score
            critical_issues = [i for i in issues if i.severity == "critical"]
            is_aligned = (
                alignment_score >= self.min_alignment_score and
                lo_matched and
                topic_matched and
                len(critical_issues) == 0
            )

            if is_aligned:
                self.total_aligned += 1
            else:
                self.total_misaligned += 1

            result = AlignmentResult(
                is_aligned=is_aligned,
                alignment_score=alignment_score,
                lo_matched=lo_matched,
                topic_matched=topic_matched,
                unit_matched=unit_matched,
                matched_lo_code=lo_code if lo_matched else None,
                matched_topic_code=topic_id if topic_matched else None,
                matched_unit_code=unit_id if unit_matched else None,
                issues=issues,
                metadata={
                    "question_id": question_content.get("question_id"),
                    "course_id": course_id,
                    "critical_issues": len([i for i in issues if i.severity == "critical"]),
                    "warning_issues": len([i for i in issues if i.severity == "warning"])
                }
            )

            logger.info(
                f"Validation result: aligned={is_aligned}, score={alignment_score:.2f}, "
                f"issues={len(issues)}"
            )

            return result

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise AprepError(f"Alignment validation failed: {e}")

    def _check_content_alignment(
        self,
        question_text: str,
        learning_objective: LearningObjective
    ) -> float:
        """
        Check how well question content aligns with LO.

        Returns:
            Alignment score 0.0-1.0
        """
        if not question_text:
            return 0.0

        # Extract keywords from LO
        lo_keywords = set(learning_objective.keywords)
        lo_desc_words = set(learning_objective.description.lower().split())
        all_lo_terms = lo_keywords.union(lo_desc_words)

        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        all_lo_terms = {t.lower() for t in all_lo_terms if t.lower() not in stop_words}

        # Extract words from question
        question_words = set(question_text.lower().split())
        question_words = {w for w in question_words if w not in stop_words}

        # Calculate overlap
        if not all_lo_terms:
            return 0.5  # Default if no LO keywords

        overlap = len(all_lo_terms.intersection(question_words))
        score = overlap / len(all_lo_terms)

        return min(1.0, score)

    def _calculate_alignment_score(
        self,
        lo_matched: bool,
        topic_matched: bool,
        unit_matched: bool,
        content_aligned: bool,
        issue_count: int
    ) -> float:
        """
        Calculate overall alignment score.

        Returns:
            Score 0.0-1.0
        """
        # Base score from matching
        score = 0.0

        if lo_matched:
            score += 0.4  # LO match is most important

        if topic_matched:
            score += 0.3  # Topic match

        if unit_matched:
            score += 0.1  # Unit match

        if content_aligned:
            score += 0.2  # Content alignment

        # Penalize for issues
        penalty = min(0.3, issue_count * 0.05)
        score = max(0.0, score - penalty)

        return score

    def validate_batch(
        self,
        questions: List[Dict[str, Any]],
        course_id: str
    ) -> Dict[str, Any]:
        """
        Validate multiple questions in batch.

        Args:
            questions: List of question dicts
            course_id: Course identifier

        Returns:
            Dictionary with batch validation results
        """
        results = []

        for question in questions:
            result = self.validate_question(question, course_id)
            results.append({
                "question_id": question.get("question_id"),
                "is_aligned": result.is_aligned,
                "alignment_score": result.alignment_score,
                "issues": [i.model_dump() for i in result.issues]
            })

        # Calculate batch statistics
        aligned_count = sum(1 for r in results if r["is_aligned"])
        avg_score = sum(r["alignment_score"] for r in results) / len(results) if results else 0.0

        return {
            "total_questions": len(questions),
            "aligned_count": aligned_count,
            "misaligned_count": len(questions) - aligned_count,
            "alignment_rate": aligned_count / len(questions) if questions else 0.0,
            "avg_alignment_score": avg_score,
            "results": results
        }

    def check_curriculum_coverage(
        self,
        questions: List[Dict[str, Any]],
        course_id: str
    ) -> Dict[str, Any]:
        """
        Check curriculum coverage for a set of questions.

        Args:
            questions: List of validated questions
            course_id: Course identifier

        Returns:
            Coverage statistics
        """
        # Get all LOs from course
        course = self.taxonomy_manager.load_course(course_id)

        if not course:
            return {}

        all_lo_codes = set()
        for unit in course.units:
            for topic in unit.topics:
                for lo in topic.learning_objectives:
                    all_lo_codes.add(lo.code)

        # Get covered LOs from questions
        covered_lo_codes = set()
        for question in questions:
            lo_code = question.get("lo_code")
            if lo_code:
                covered_lo_codes.add(lo_code)

        # Calculate coverage
        coverage_ratio = len(covered_lo_codes) / len(all_lo_codes) if all_lo_codes else 0.0

        uncovered = all_lo_codes - covered_lo_codes

        return {
            "course_id": course_id,
            "total_los": len(all_lo_codes),
            "covered_los": len(covered_lo_codes),
            "uncovered_los": len(uncovered),
            "coverage_ratio": coverage_ratio,
            "uncovered_lo_codes": sorted(list(uncovered))
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get validator statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_validations": self.total_validations,
            "total_aligned": self.total_aligned,
            "total_misaligned": self.total_misaligned,
            "alignment_rate": (
                self.total_aligned / self.total_validations
                if self.total_validations > 0 else 0.0
            ),
            "min_alignment_score": self.min_alignment_score
        }
