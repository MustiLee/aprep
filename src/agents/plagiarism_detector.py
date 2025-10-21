"""
Plagiarism Detector Agent

This agent detects potential plagiarism in generated questions by comparing them
against an existing question bank. It uses both lexical (TF-IDF) and semantic
(embedding-based) similarity measures to identify questions that are too similar
to existing content.

Responsibilities:
- Calculate lexical similarity using TF-IDF vectors
- Calculate semantic similarity using embeddings
- Compare new questions against question bank
- Generate originality reports
- Flag questions that exceed similarity thresholds
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import Counter
import math

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError

logger = setup_logger(__name__)


class SimilarityMatch(BaseModel):
    """A similarity match between two questions"""

    question_id: str = Field(..., description="ID of matching question")
    lexical_similarity: float = Field(..., ge=0.0, le=1.0, description="TF-IDF similarity")
    semantic_similarity: float = Field(..., ge=0.0, le=1.0, description="Embedding similarity")
    combined_similarity: float = Field(..., ge=0.0, le=1.0, description="Weighted average")

    matched_text: str = Field(..., description="Text of matching question")
    match_type: str = Field(..., description="exact, high, moderate, low")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlagiarismReport(BaseModel):
    """Report of plagiarism check results"""

    question_id: str = Field(..., description="ID of checked question")
    question_text: str = Field(..., description="Text of checked question")

    is_original: bool = Field(..., description="Whether question is original")
    max_similarity: float = Field(..., description="Maximum similarity found")
    matches: List[SimilarityMatch] = Field(default_factory=list, description="Similar questions")

    flagged: bool = Field(default=False, description="Whether flagged for review")
    flag_reason: Optional[str] = Field(None, description="Reason for flagging")

    checked_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlagiarismDetector:
    """
    Detects plagiarism in generated questions using TF-IDF and semantic similarity.
    """

    def __init__(
        self,
        question_bank_path: Optional[str] = None,
        similarity_threshold: float = 0.80,
        lexical_weight: float = 0.6,
        semantic_weight: float = 0.4
    ):
        """
        Initialize the Plagiarism Detector.

        Args:
            question_bank_path: Path to question bank JSON file
            similarity_threshold: Threshold for flagging (default 0.80)
            lexical_weight: Weight for lexical similarity (default 0.6)
            semantic_weight: Weight for semantic similarity (default 0.4)
        """
        self.question_bank_path = Path(question_bank_path) if question_bank_path else None
        self.similarity_threshold = similarity_threshold
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight

        # Load question bank
        self.question_bank = self._load_question_bank()

        # Build TF-IDF index
        self.tfidf_index = self._build_tfidf_index()

        # Performance tracking
        self.total_checks = 0
        self.total_flagged = 0
        self.check_history = []

        logger.info(
            f"Initialized PlagiarismDetector with {len(self.question_bank)} questions "
            f"in bank (threshold: {similarity_threshold})"
        )

    def check_question(
        self,
        question_text: str,
        question_id: Optional[str] = None,
        return_top_n: int = 5
    ) -> PlagiarismReport:
        """
        Check a question for plagiarism against the question bank.

        Args:
            question_text: The question text to check
            question_id: Optional ID for the question
            return_top_n: Number of top matches to return (default 5)

        Returns:
            PlagiarismReport with results
        """
        try:
            self.total_checks += 1
            logger.info(f"Checking question for plagiarism: {question_id or 'unknown'}")

            # Normalize question text
            normalized_text = self._normalize_text(question_text)

            # Find similar questions
            matches = []
            for bank_question in self.question_bank:
                # Calculate lexical similarity (TF-IDF)
                lexical_sim = self._calculate_lexical_similarity(
                    normalized_text,
                    self._normalize_text(bank_question["text"])
                )

                # Calculate semantic similarity (simple for now)
                semantic_sim = self._calculate_semantic_similarity(
                    normalized_text,
                    self._normalize_text(bank_question["text"])
                )

                # Combined similarity
                combined_sim = (
                    self.lexical_weight * lexical_sim +
                    self.semantic_weight * semantic_sim
                )

                # Determine match type
                if combined_sim >= 0.95:
                    match_type = "exact"
                elif combined_sim >= 0.80:
                    match_type = "high"
                elif combined_sim >= 0.60:
                    match_type = "moderate"
                else:
                    match_type = "low"

                # Only include matches above threshold
                if combined_sim >= 0.50:  # Lower threshold for reporting
                    match = SimilarityMatch(
                        question_id=bank_question["id"],
                        lexical_similarity=round(lexical_sim, 3),
                        semantic_similarity=round(semantic_sim, 3),
                        combined_similarity=round(combined_sim, 3),
                        matched_text=bank_question["text"],
                        match_type=match_type,
                        metadata=bank_question.get("metadata", {})
                    )
                    matches.append(match)

            # Sort by combined similarity
            matches.sort(key=lambda m: m.combined_similarity, reverse=True)
            top_matches = matches[:return_top_n]

            # Determine if original
            max_similarity = top_matches[0].combined_similarity if top_matches else 0.0
            is_original = max_similarity < self.similarity_threshold

            # Flagging logic
            flagged = False
            flag_reason = None

            if max_similarity >= 0.95:
                flagged = True
                flag_reason = "Exact or near-exact match found"
            elif max_similarity >= self.similarity_threshold:
                flagged = True
                flag_reason = f"High similarity ({max_similarity:.2%}) exceeds threshold"

            # Track flagged questions
            if flagged:
                self.total_flagged += 1

            # Create report
            report = PlagiarismReport(
                question_id=question_id or "unknown",
                question_text=question_text,
                is_original=is_original,
                max_similarity=max_similarity,
                matches=top_matches,
                flagged=flagged,
                flag_reason=flag_reason,
                metadata={
                    "total_matches_found": len(matches),
                    "bank_size": len(self.question_bank)
                }
            )

            # Record in history
            self._record_check(report)

            logger.info(
                f"Plagiarism check complete: is_original={is_original}, "
                f"max_similarity={max_similarity:.2%}, flagged={flagged}"
            )

            return report

        except Exception as e:
            logger.error(f"Plagiarism check failed: {e}")
            raise AprepError(f"Failed to check plagiarism: {e}")

    def check_batch(
        self,
        questions: List[Dict[str, Any]],
        return_top_n: int = 3
    ) -> List[PlagiarismReport]:
        """
        Check multiple questions for plagiarism.

        Args:
            questions: List of question dicts with 'id' and 'text' keys
            return_top_n: Number of top matches per question

        Returns:
            List of PlagiarismReport objects
        """
        reports = []
        for question in questions:
            report = self.check_question(
                question_text=question.get("text", ""),
                question_id=question.get("id"),
                return_top_n=return_top_n
            )
            reports.append(report)

        logger.info(
            f"Batch check complete: {len(reports)} questions, "
            f"{sum(1 for r in reports if r.flagged)} flagged"
        )

        return reports

    def add_to_question_bank(
        self,
        question_id: str,
        question_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a question to the question bank.

        Args:
            question_id: Question ID
            question_text: Question text
            metadata: Optional metadata
        """
        question = {
            "id": question_id,
            "text": question_text,
            "metadata": metadata or {},
            "added_at": datetime.now().isoformat()
        }

        self.question_bank.append(question)

        # Rebuild TF-IDF index
        self.tfidf_index = self._build_tfidf_index()

        # Save to file if path provided
        if self.question_bank_path:
            self._save_question_bank()

        logger.info(f"Added question {question_id} to bank (total: {len(self.question_bank)})")

    def remove_from_question_bank(self, question_id: str) -> bool:
        """
        Remove a question from the question bank.

        Args:
            question_id: Question ID to remove

        Returns:
            True if removed, False if not found
        """
        initial_count = len(self.question_bank)
        self.question_bank = [q for q in self.question_bank if q["id"] != question_id]

        if len(self.question_bank) < initial_count:
            # Rebuild TF-IDF index
            self.tfidf_index = self._build_tfidf_index()

            # Save to file if path provided
            if self.question_bank_path:
                self._save_question_bank()

            logger.info(f"Removed question {question_id} from bank")
            return True

        return False

    def _load_question_bank(self) -> List[Dict[str, Any]]:
        """Load question bank from file."""
        if not self.question_bank_path or not self.question_bank_path.exists():
            logger.info("No question bank found, starting with empty bank")
            return []

        try:
            with open(self.question_bank_path, 'r') as f:
                bank = json.load(f)
            logger.info(f"Loaded {len(bank)} questions from bank")
            return bank
        except Exception as e:
            logger.error(f"Failed to load question bank: {e}")
            return []

    def _save_question_bank(self) -> None:
        """Save question bank to file."""
        if not self.question_bank_path:
            return

        try:
            self.question_bank_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.question_bank_path, 'w') as f:
                json.dump(self.question_bank, f, indent=2)

            logger.debug(f"Saved question bank to {self.question_bank_path}")
        except Exception as e:
            logger.error(f"Failed to save question bank: {e}")

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.

        - Lowercase
        - Remove extra whitespace
        - Remove punctuation (except necessary math symbols)
        """
        # Lowercase
        text = text.lower()

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove common punctuation (but keep math symbols)
        text = re.sub(r'[,;:.!?"]', '', text)

        return text.strip()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Simple word tokenization
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _calculate_lexical_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate lexical similarity using TF-IDF-like approach.

        Uses cosine similarity between token frequency vectors.
        """
        tokens1 = self._tokenize(text1)
        tokens2 = self._tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        # Build frequency vectors
        freq1 = Counter(tokens1)
        freq2 = Counter(tokens2)

        # Get all unique tokens
        all_tokens = set(freq1.keys()) | set(freq2.keys())

        # Build vectors
        vec1 = [freq1.get(token, 0) for token in all_tokens]
        vec2 = [freq2.get(token, 0) for token in all_tokens]

        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity.

        For now, uses simple token overlap (Jaccard similarity).
        In production, would use embedding-based similarity (e.g., sentence transformers).
        """
        tokens1 = set(self._tokenize(text1))
        tokens2 = set(self._tokenize(text2))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        if union == 0:
            return 0.0

        return intersection / union

    def _build_tfidf_index(self) -> Dict[str, Any]:
        """
        Build TF-IDF index for question bank.

        Returns:
            Dictionary with IDF values and document frequencies
        """
        if not self.question_bank:
            return {"idf": {}, "doc_count": 0}

        # Calculate document frequencies
        doc_frequencies = Counter()
        total_docs = len(self.question_bank)

        for question in self.question_bank:
            tokens = set(self._tokenize(self._normalize_text(question["text"])))
            doc_frequencies.update(tokens)

        # Calculate IDF (inverse document frequency)
        idf = {}
        for token, df in doc_frequencies.items():
            idf[token] = math.log(total_docs / (1 + df))

        return {
            "idf": idf,
            "doc_count": total_docs
        }

    def _record_check(self, report: PlagiarismReport) -> None:
        """Record plagiarism check in history."""
        history_entry = {
            "timestamp": report.checked_at,
            "question_id": report.question_id,
            "is_original": report.is_original,
            "max_similarity": report.max_similarity,
            "flagged": report.flagged,
            "matches_count": len(report.matches)
        }

        self.check_history.append(history_entry)

        # Keep only last 100 entries
        if len(self.check_history) > 100:
            self.check_history = self.check_history[-100:]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get plagiarism detection statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_checks": self.total_checks,
            "total_flagged": self.total_flagged,
            "flag_rate": (
                self.total_flagged / self.total_checks
                if self.total_checks > 0 else 0.0
            ),
            "question_bank_size": len(self.question_bank),
            "similarity_threshold": self.similarity_threshold,
            "recent_checks": len(self.check_history)
        }

        if self.check_history:
            recent_similarities = [h["max_similarity"] for h in self.check_history]
            stats["avg_max_similarity"] = sum(recent_similarities) / len(recent_similarities)

        return stats

    def get_check_history(
        self,
        limit: Optional[int] = None,
        flagged_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get plagiarism check history.

        Args:
            limit: Maximum number of history entries to return
            flagged_only: Only return flagged checks

        Returns:
            List of history entries
        """
        history = self.check_history

        # Filter if flagged_only
        if flagged_only:
            history = [h for h in history if h.get("flagged", False)]

        # Apply limit
        if limit:
            history = history[-limit:]

        return history
