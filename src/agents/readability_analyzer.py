"""
Readability Analyzer Agent

This agent analyzes the readability and linguistic complexity of questions to ensure
they are appropriate for the target audience (AP high school students). It calculates
multiple readability metrics and flags questions that may be too complex.

Responsibilities:
- Calculate Flesch-Kincaid Grade Level
- Calculate Flesch Reading Ease score
- Analyze sentence complexity
- Measure technical term density
- Identify overly complex vocabulary
- Generate readability reports
"""

import re
import string
from typing import Dict, List, Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError

# Try to import textstat for additional readability metrics
try:
    import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False
    logger.warning("textstat not available - some readability metrics will be unavailable")

logger = setup_logger(__name__)


class ReadabilityMetrics(BaseModel):
    """Readability metrics for a text"""

    # Primary indices (always calculated)
    flesch_kincaid_grade: float = Field(..., description="FK grade level (0-18+)")
    flesch_reading_ease: float = Field(..., description="FRE score (0-100)")

    # Additional readability indices (spec-aligned, calculated if textstat available)
    gunning_fog_index: Optional[float] = Field(None, description="Gunning Fog index")
    smog_index: Optional[float] = Field(None, description="SMOG index")
    coleman_liau_index: Optional[float] = Field(None, description="Coleman-Liau index")
    automated_readability_index: Optional[float] = Field(None, description="ARI")

    avg_sentence_length: float = Field(..., description="Average words per sentence")
    avg_syllables_per_word: float = Field(..., description="Average syllables per word")

    total_words: int = Field(..., description="Total word count")
    total_sentences: int = Field(..., description="Total sentence count")
    total_syllables: int = Field(..., description="Total syllable count")

    complex_word_count: int = Field(..., description="Words with 3+ syllables")
    complex_word_ratio: float = Field(..., description="Ratio of complex words")

    technical_term_count: int = Field(..., description="Count of technical terms")
    technical_term_density: float = Field(..., description="Technical terms per 100 words")

    # Spec-aligned: passive voice detection
    passive_voice_ratio: Optional[float] = Field(None, description="Ratio of passive voice (0.0-1.0)")

    # Spec-aligned: math notation adjustment
    math_density: Optional[float] = Field(None, description="Ratio of math notation (0.0-1.0)")
    math_adjustment_applied: bool = Field(default=False, description="Whether math adjustment was applied")

    readability_level: str = Field(..., description="very_easy, easy, moderate, difficult, very_difficult")


class ReadabilityReport(BaseModel):
    """Report of readability analysis"""

    question_id: str = Field(..., description="Question ID")
    question_text: str = Field(..., description="Question text")

    metrics: ReadabilityMetrics = Field(..., description="Readability metrics")

    is_appropriate: bool = Field(..., description="Whether readability is appropriate")
    flagged: bool = Field(default=False, description="Whether flagged for review")
    flag_reasons: List[str] = Field(default_factory=list, description="Reasons for flagging")

    recommendations: List[str] = Field(default_factory=list, description="Improvement suggestions")

    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadabilityAnalyzer:
    """
    Analyzes readability of questions using established metrics.
    """

    # Common mathematical/scientific terms for AP Calculus
    TECHNICAL_TERMS = {
        "derivative", "integral", "limit", "continuity", "differentiable",
        "antiderivative", "differential", "function", "theorem", "slope",
        "tangent", "normal", "asymptote", "concavity", "inflection",
        "logarithm", "exponential", "trigonometric", "polynomial", "rational",
        "parametric", "polar", "vector", "series", "sequence", "convergence"
    }

    def __init__(
        self,
        target_grade_level: float = 11.0,  # AP students are typically 11th-12th grade
        max_acceptable_grade: float = 13.0,
        min_acceptable_grade: float = 9.0
    ):
        """
        Initialize the Readability Analyzer.

        Args:
            target_grade_level: Target Flesch-Kincaid grade level
            max_acceptable_grade: Maximum acceptable grade level
            min_acceptable_grade: Minimum acceptable grade level
        """
        self.target_grade_level = target_grade_level
        self.max_acceptable_grade = max_acceptable_grade
        self.min_acceptable_grade = min_acceptable_grade

        # Performance tracking
        self.total_analyses = 0
        self.total_flagged = 0
        self.analysis_history = []

        logger.info(
            f"Initialized ReadabilityAnalyzer (target grade: {target_grade_level}, "
            f"range: {min_acceptable_grade}-{max_acceptable_grade})"
        )

    def analyze_question(
        self,
        question_text: str,
        question_id: Optional[str] = None
    ) -> ReadabilityReport:
        """
        Analyze readability of a question.

        Args:
            question_text: The question text to analyze
            question_id: Optional question ID

        Returns:
            ReadabilityReport with analysis results
        """
        try:
            self.total_analyses += 1
            logger.info(f"Analyzing readability for question: {question_id or 'unknown'}")

            # Calculate metrics
            metrics = self._calculate_metrics(question_text)

            # Determine if appropriate
            is_appropriate = (
                self.min_acceptable_grade <= metrics.flesch_kincaid_grade <= self.max_acceptable_grade
            )

            # Flagging logic
            flagged = False
            flag_reasons = []

            if metrics.flesch_kincaid_grade > self.max_acceptable_grade:
                flagged = True
                flag_reasons.append(
                    f"Grade level ({metrics.flesch_kincaid_grade:.1f}) exceeds maximum ({self.max_acceptable_grade})"
                )

            if metrics.flesch_kincaid_grade < self.min_acceptable_grade:
                flagged = True
                flag_reasons.append(
                    f"Grade level ({metrics.flesch_kincaid_grade:.1f}) below minimum ({self.min_acceptable_grade})"
                )

            if metrics.complex_word_ratio > 0.40:
                flagged = True
                flag_reasons.append(
                    f"High complex word ratio ({metrics.complex_word_ratio:.1%})"
                )

            if metrics.avg_sentence_length > 30:
                flagged = True
                flag_reasons.append(
                    f"Long average sentence length ({metrics.avg_sentence_length:.1f} words)"
                )

            if metrics.technical_term_density > 25:
                flagged = True
                flag_reasons.append(
                    f"High technical term density ({metrics.technical_term_density:.1f} per 100 words)"
                )

            # Generate recommendations
            recommendations = self._generate_recommendations(metrics, flag_reasons)

            # Track flagged
            if flagged:
                self.total_flagged += 1

            # Create report
            report = ReadabilityReport(
                question_id=question_id or "unknown",
                question_text=question_text,
                metrics=metrics,
                is_appropriate=is_appropriate,
                flagged=flagged,
                flag_reasons=flag_reasons,
                recommendations=recommendations,
                metadata={
                    "target_grade": self.target_grade_level,
                    "grade_range": f"{self.min_acceptable_grade}-{self.max_acceptable_grade}"
                }
            )

            # Record in history
            self._record_analysis(report)

            logger.info(
                f"Readability analysis complete: grade={metrics.flesch_kincaid_grade:.1f}, "
                f"appropriate={is_appropriate}, flagged={flagged}"
            )

            return report

        except Exception as e:
            logger.error(f"Readability analysis failed: {e}")
            raise AprepError(f"Failed to analyze readability: {e}")

    def analyze_batch(
        self,
        questions: List[Dict[str, Any]]
    ) -> List[ReadabilityReport]:
        """
        Analyze multiple questions for readability.

        Args:
            questions: List of question dicts with 'id' and 'text' keys

        Returns:
            List of ReadabilityReport objects
        """
        reports = []
        for question in questions:
            report = self.analyze_question(
                question_text=question.get("text", ""),
                question_id=question.get("id")
            )
            reports.append(report)

        logger.info(
            f"Batch analysis complete: {len(reports)} questions, "
            f"{sum(1 for r in reports if r.flagged)} flagged"
        )

        return reports

    def _calculate_metrics(self, text: str) -> ReadabilityMetrics:
        """Calculate all readability metrics for text."""
        # Detect and strip math notation for readability calculation
        math_density = self._calculate_math_density(text)
        text_for_analysis = self._strip_math_notation(text)

        # Count basic elements
        total_words = self._count_words(text_for_analysis)
        total_sentences = self._count_sentences(text_for_analysis)
        total_syllables = self._count_syllables(text_for_analysis)

        # Avoid division by zero
        if total_words == 0:
            total_words = 1
        if total_sentences == 0:
            total_sentences = 1

        # Calculate averages
        avg_sentence_length = total_words / total_sentences
        avg_syllables_per_word = total_syllables / total_words

        # Flesch-Kincaid Grade Level
        # Formula: 0.39 * (total words / total sentences) + 11.8 * (total syllables / total words) - 15.59
        fk_grade = (
            0.39 * avg_sentence_length +
            11.8 * avg_syllables_per_word -
            15.59
        )
        fk_grade = max(0.0, min(18.0, fk_grade))  # Clamp to 0-18

        # Flesch Reading Ease
        # Formula: 206.835 - 1.015 * (total words / total sentences) - 84.6 * (total syllables / total words)
        fre_score = (
            206.835 -
            1.015 * avg_sentence_length -
            84.6 * avg_syllables_per_word
        )
        fre_score = max(0.0, min(100.0, fre_score))  # Clamp to 0-100

        # Additional readability indices using textstat if available
        gunning_fog = None
        smog = None
        coleman_liau = None
        ari = None

        if TEXTSTAT_AVAILABLE:
            try:
                gunning_fog = round(textstat.gunning_fog(text_for_analysis), 2)
                smog = round(textstat.smog_index(text_for_analysis), 2)
                coleman_liau = round(textstat.coleman_liau_index(text_for_analysis), 2)
                ari = round(textstat.automated_readability_index(text_for_analysis), 2)
            except Exception as e:
                logger.warning(f"Error calculating additional readability indices: {e}")

        # Complex words (3+ syllables)
        words = self._tokenize(text_for_analysis)
        complex_word_count = sum(1 for word in words if self._count_syllables_in_word(word) >= 3)
        complex_word_ratio = complex_word_count / total_words if total_words > 0 else 0.0

        # Technical terms
        technical_term_count = self._count_technical_terms(text_for_analysis)
        technical_term_density = (technical_term_count / total_words) * 100 if total_words > 0 else 0.0

        # Passive voice detection
        passive_voice_ratio = self._detect_passive_voice_ratio(text_for_analysis)

        # Apply math adjustment if math-heavy (spec: >30% math content)
        math_adjustment_applied = False
        if math_density > 0.30:
            # Relax grade level by 10% as per spec
            fk_grade *= 0.9
            math_adjustment_applied = True
            logger.debug(f"Applied math adjustment: {math_density:.1%} math density")

        # Readability level categorization
        if fk_grade <= 6:
            readability_level = "very_easy"
        elif fk_grade <= 9:
            readability_level = "easy"
        elif fk_grade <= 12:
            readability_level = "moderate"
        elif fk_grade <= 16:
            readability_level = "difficult"
        else:
            readability_level = "very_difficult"

        return ReadabilityMetrics(
            flesch_kincaid_grade=round(fk_grade, 2),
            flesch_reading_ease=round(fre_score, 2),
            gunning_fog_index=gunning_fog,
            smog_index=smog,
            coleman_liau_index=coleman_liau,
            automated_readability_index=ari,
            avg_sentence_length=round(avg_sentence_length, 2),
            avg_syllables_per_word=round(avg_syllables_per_word, 2),
            total_words=total_words,
            total_sentences=total_sentences,
            total_syllables=total_syllables,
            complex_word_count=complex_word_count,
            complex_word_ratio=round(complex_word_ratio, 3),
            technical_term_count=technical_term_count,
            technical_term_density=round(technical_term_density, 2),
            passive_voice_ratio=passive_voice_ratio,
            math_density=round(math_density, 3) if math_density > 0 else None,
            math_adjustment_applied=math_adjustment_applied,
            readability_level=readability_level
        )

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        words = self._tokenize(text)
        return len(words)

    def _count_sentences(self, text: str) -> int:
        """Count sentences in text."""
        # Split on sentence-ending punctuation
        sentences = re.split(r'[.!?]+', text)
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        return max(1, len(sentences))  # At least 1 sentence

    def _count_syllables(self, text: str) -> int:
        """Count total syllables in text."""
        words = self._tokenize(text)
        return sum(self._count_syllables_in_word(word) for word in words)

    def _count_syllables_in_word(self, word: str) -> int:
        """
        Count syllables in a single word.

        Uses simple heuristic based on vowel groups.
        """
        word = word.lower().strip(string.punctuation)

        # Handle edge cases
        if len(word) <= 1:
            return 1

        # Count vowel groups
        vowels = "aeiouy"
        syllable_count = 0
        previous_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel

        # Adjust for silent 'e' at end
        if word.endswith('e'):
            syllable_count -= 1

        # Adjust for 'le' ending
        if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
            syllable_count += 1

        # Ensure at least 1 syllable
        return max(1, syllable_count)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Remove punctuation except hyphens (for compound words)
        text = re.sub(r'[^\w\s-]', ' ', text)
        # Split on whitespace
        words = text.split()
        # Filter out empty strings
        words = [w for w in words if w.strip()]
        return words

    def _count_technical_terms(self, text: str) -> int:
        """Count technical/mathematical terms in text."""
        words = self._tokenize(text)
        # Convert to lowercase for matching
        words_lower = [w.lower() for w in words]

        count = 0
        for word in words_lower:
            if word in self.TECHNICAL_TERMS:
                count += 1

        return count

    def _generate_recommendations(
        self,
        metrics: ReadabilityMetrics,
        flag_reasons: List[str]
    ) -> List[str]:
        """Generate recommendations based on metrics and flag reasons."""
        recommendations = []

        if metrics.flesch_kincaid_grade > self.max_acceptable_grade:
            recommendations.append(
                "Simplify sentence structure by breaking long sentences into shorter ones"
            )
            recommendations.append(
                "Replace complex vocabulary with simpler alternatives where possible"
            )

        if metrics.avg_sentence_length > 25:
            recommendations.append(
                f"Reduce average sentence length (currently {metrics.avg_sentence_length:.1f} words)"
            )

        if metrics.complex_word_ratio > 0.35:
            recommendations.append(
                "Reduce use of complex words (3+ syllables) where possible"
            )

        if metrics.technical_term_density > 20:
            recommendations.append(
                "Consider reducing technical term density or providing definitions"
            )

        if metrics.flesch_kincaid_grade < self.min_acceptable_grade:
            recommendations.append(
                "Question may be too simple for AP level students"
            )

        # If no specific recommendations, provide general advice
        if not recommendations:
            if metrics.flesch_kincaid_grade > self.target_grade_level:
                recommendations.append("Question is slightly above target reading level")
            elif metrics.flesch_kincaid_grade < self.target_grade_level:
                recommendations.append("Question is slightly below target reading level")

        return recommendations

    def _calculate_math_density(self, text: str) -> float:
        """
        Calculate density of mathematical notation in text.

        Returns:
            Float between 0.0 and 1.0 representing ratio of math content
        """
        # Count math-related patterns
        math_patterns = [
            r'\d+',  # Numbers
            r'[+\-*/=<>]',  # Math operators
            r'\^',  # Exponents
            r'[∫∑∏√]',  # Math symbols
            r'\\[a-z]+',  # LaTeX commands
            r'f\([a-z]\)',  # Function notation
            r'[a-z]\^[0-9]',  # Variables with exponents
        ]

        total_chars = len(text)
        if total_chars == 0:
            return 0.0

        math_char_count = 0
        for pattern in math_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            math_char_count += sum(len(match) for match in matches)

        # Return ratio, capped at 1.0
        return min(1.0, math_char_count / total_chars)

    def _strip_math_notation(self, text: str) -> str:
        """
        Strip mathematical notation for readability analysis.

        Replaces math notation with placeholder words to avoid
        artificially inflating complexity scores.
        """
        # Remove LaTeX commands
        text = re.sub(r'\\[a-z]+\{[^}]*\}', 'MATH', text)
        text = re.sub(r'\\[a-z]+', 'MATH', text)

        # Replace math symbols
        text = re.sub(r'[∫∑∏√]', 'MATH', text)

        # Replace function notation with simple word
        text = re.sub(r'f\([a-z]\)', 'function', text)

        # Replace exponents
        text = re.sub(r'\^[0-9]+', '', text)

        return text

    def _detect_passive_voice_ratio(self, text: str) -> Optional[float]:
        """
        Detect ratio of passive voice in text.

        Uses simple heuristic: looks for "to be" verb + past participle.

        Returns:
            Float between 0.0 and 1.0, or None if cannot calculate
        """
        try:
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]

            if len(sentences) == 0:
                return None

            # Simple passive voice indicators
            passive_indicators = [
                r'\b(is|are|was|were|be|been|being)\s+\w+ed\b',  # is/was + past participle
                r'\b(is|are|was|were|be|been|being)\s+\w+en\b',  # is/was + irregular past
            ]

            passive_count = 0
            for sentence in sentences:
                for pattern in passive_indicators:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        passive_count += 1
                        break  # Count each sentence only once

            ratio = passive_count / len(sentences)
            return round(ratio, 3)

        except Exception as e:
            logger.warning(f"Error detecting passive voice: {e}")
            return None

    def _record_analysis(self, report: ReadabilityReport) -> None:
        """Record analysis in history."""
        history_entry = {
            "timestamp": report.analyzed_at,
            "question_id": report.question_id,
            "grade_level": report.metrics.flesch_kincaid_grade,
            "reading_ease": report.metrics.flesch_reading_ease,
            "is_appropriate": report.is_appropriate,
            "flagged": report.flagged,
            "readability_level": report.metrics.readability_level
        }

        self.analysis_history.append(history_entry)

        # Keep only last 100 entries
        if len(self.analysis_history) > 100:
            self.analysis_history = self.analysis_history[-100:]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get readability analysis statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_analyses": self.total_analyses,
            "total_flagged": self.total_flagged,
            "flag_rate": (
                self.total_flagged / self.total_analyses
                if self.total_analyses > 0 else 0.0
            ),
            "target_grade_level": self.target_grade_level,
            "grade_range": f"{self.min_acceptable_grade}-{self.max_acceptable_grade}",
            "recent_analyses": len(self.analysis_history)
        }

        if self.analysis_history:
            grade_levels = [h["grade_level"] for h in self.analysis_history]
            stats["avg_grade_level"] = sum(grade_levels) / len(grade_levels)

            reading_ease_scores = [h["reading_ease"] for h in self.analysis_history]
            stats["avg_reading_ease"] = sum(reading_ease_scores) / len(reading_ease_scores)

        return stats

    def get_analysis_history(
        self,
        limit: Optional[int] = None,
        flagged_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get analysis history.

        Args:
            limit: Maximum number of history entries to return
            flagged_only: Only return flagged analyses

        Returns:
            List of history entries
        """
        history = self.analysis_history

        # Filter if flagged_only
        if flagged_only:
            history = [h for h in history if h.get("flagged", False)]

        # Apply limit
        if limit:
            history = history[-limit:]

        return history
