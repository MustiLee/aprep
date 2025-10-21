"""
Bias Detector Agent

Detects and flags potential biases in question content to ensure fairness,
inclusivity, and cultural sensitivity.

Spec: .claude/agents/bias-detector.md
Version: 1.0 - Basic Implementation
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BiasFlag:
    """Represents a detected bias"""
    category: str  # gender, racial, socioeconomic, disability, age, geographic
    severity: str  # low, medium, high, critical
    confidence: float  # 0-1
    location: str  # stimulus, stem, option_a, etc.
    issue: str  # Description of the bias
    evidence: str  # Specific text that triggered the flag
    suggestion: str  # Recommended fix


@dataclass
class BiasReport:
    """Complete bias detection report"""
    item_id: str
    analyzed_at: str
    overall_risk: str  # acceptable, review_recommended, reject_recommended
    bias_score: float  # 0-1 (0=no bias, 1=severe bias)
    flags: List[BiasFlag]
    passed: bool
    recommendations: List[str]
    diversity_score: float  # 0-1 (representation diversity)


class BiasDetector:
    """
    Bias Detector Agent

    Detects potential biases in educational content using pattern matching
    and heuristic rules.
    """

    def __init__(self, sensitivity: str = "medium", flag_threshold: float = 0.60):
        """
        Initialize Bias Detector.

        Args:
            sensitivity: Detection sensitivity (low, medium, high)
            flag_threshold: Minimum confidence to flag (0-1)
        """
        self.sensitivity = sensitivity
        self.flag_threshold = flag_threshold

        # Bias detection patterns
        self._init_patterns()

        logger.info(f"BiasDetector initialized (sensitivity={sensitivity}, threshold={flag_threshold})")

    def _init_patterns(self):
        """Initialize bias detection patterns"""

        # Gender bias patterns
        self.gender_patterns = {
            "gendered_pronouns_default": re.compile(r'\b(he|him|his)\b(?!.*\b(she|her|they|them)\b)', re.IGNORECASE),
            "gendered_occupations": re.compile(r'\b(fireman|policeman|chairman|mankind|manpower)\b', re.IGNORECASE),
            "stereotypical_roles": [
                (r'\bnurse.*\b(she|her)\b', "Stereotyping nurses as female"),
                (r'\bengineer.*\b(he|him)\b', "Stereotyping engineers as male"),
                (r'\bsecretary.*\b(she|her)\b', "Stereotyping secretaries as female"),
            ]
        }

        # Socioeconomic bias patterns
        self.socioeconomic_patterns = {
            "luxury_assumptions": re.compile(r'\b(yacht|mansion|country club|private jet|vacation home)\b', re.IGNORECASE),
            "class_stereotypes": [
                (r'\bpoor (people|families).*don\'t', "Negative stereotype about low-income"),
                (r'\bwealthy (people|individuals).*always', "Overgeneralization about wealthy"),
            ]
        }

        # Ableist language
        self.ableist_patterns = {
            "ableist_terms": re.compile(r'\b(crazy|insane|lame|dumb|stupid|retarded|blind|deaf)\b(?! to)', re.IGNORECASE),
            "ability_assumptions": re.compile(r'\b(stand up|look at|listen to)\b', re.IGNORECASE)
        }

        # Geographic bias
        self.geographic_patterns = {
            "us_centric": re.compile(r'\b(Thanksgiving|Fourth of July|Super Bowl|Fahrenheit)\b', re.IGNORECASE),
            "western_bias": [
                (r'\b(Christmas|Easter|Halloween)\b', "Western holiday assumption"),
            ]
        }

        # Inclusive name diversity
        self.diverse_names = {
            "western": ["John", "Mary", "David", "Sarah", "Michael", "Emily"],
            "hispanic": ["Carlos", "Maria", "Jose", "Ana", "Miguel", "Sofia"],
            "asian": ["Wei", "Mei", "Ravi", "Priya", "Yuki", "Aiko"],
            "african": ["Kwame", "Amina", "Kofi", "Zuri", "Jabari", "Nia"],
            "middle_eastern": ["Omar", "Fatima", "Ali", "Layla", "Hassan", "Amira"]
        }

    def analyze(
        self,
        item_id: str,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> BiasReport:
        """
        Analyze content for potential biases.

        Args:
            item_id: Unique identifier for the item
            content: Dict with 'stimulus', 'stem', 'options', etc.
            metadata: Optional metadata about the item

        Returns:
            BiasReport with detected biases and recommendations
        """
        flags = []

        # Extract all text
        all_text = self._extract_text(content)

        # Check gender bias
        flags.extend(self._check_gender_bias(all_text, content))

        # Check socioeconomic bias
        flags.extend(self._check_socioeconomic_bias(all_text, content))

        # Check ableist language
        flags.extend(self._check_ableist_language(all_text, content))

        # Check geographic bias
        flags.extend(self._check_geographic_bias(all_text, content))

        # Check name diversity
        diversity_score = self._check_name_diversity(all_text)

        # Filter by threshold
        flags = [f for f in flags if f.confidence >= self.flag_threshold]

        # Calculate overall bias score
        bias_score = self._calculate_bias_score(flags)

        # Determine risk level
        overall_risk = self._assess_risk(bias_score, flags)

        # Generate recommendations
        recommendations = self._generate_recommendations(flags, diversity_score)

        # Determine pass/fail
        passed = overall_risk == "acceptable"

        return BiasReport(
            item_id=item_id,
            analyzed_at=datetime.now().isoformat(),
            overall_risk=overall_risk,
            bias_score=bias_score,
            flags=flags,
            passed=passed,
            recommendations=recommendations,
            diversity_score=diversity_score
        )

    def _extract_text(self, content: Dict[str, Any]) -> Dict[str, str]:
        """Extract all text from content"""
        text = {}

        if "stimulus" in content:
            text["stimulus"] = content["stimulus"]

        if "stem" in content:
            text["stem"] = content["stem"]

        if "options" in content:
            for key, value in content["options"].items():
                text[f"option_{key.lower()}"] = value

        return text

    def _check_gender_bias(self, text_dict: Dict[str, str], content: Dict) -> List[BiasFlag]:
        """Check for gender bias"""
        flags = []

        for location, text in text_dict.items():
            # Check default male pronouns
            if self.gender_patterns["gendered_pronouns_default"].search(text):
                flags.append(BiasFlag(
                    category="gender",
                    severity="medium",
                    confidence=0.70,
                    location=location,
                    issue="Default use of male pronouns without balance",
                    evidence=text[:100],
                    suggestion="Use gender-neutral pronouns (they/them) or balance with female pronouns"
                ))

            # Check gendered occupations
            match = self.gender_patterns["gendered_occupations"].search(text)
            if match:
                flags.append(BiasFlag(
                    category="gender",
                    severity="medium",
                    confidence=0.85,
                    location=location,
                    issue=f"Gendered occupation term: {match.group()}",
                    evidence=match.group(),
                    suggestion=f"Replace with neutral term (firefighter, police officer, chairperson)"
                ))

            # Check stereotypical roles
            for pattern, issue in self.gender_patterns["stereotypical_roles"]:
                if re.search(pattern, text, re.IGNORECASE):
                    flags.append(BiasFlag(
                        category="gender",
                        severity="high",
                        confidence=0.75,
                        location=location,
                        issue=issue,
                        evidence=text[:100],
                        suggestion="Use gender-neutral language or balance examples"
                    ))

        return flags

    def _check_socioeconomic_bias(self, text_dict: Dict[str, str], content: Dict) -> List[BiasFlag]:
        """Check for socioeconomic bias"""
        flags = []

        for location, text in text_dict.items():
            # Check luxury item assumptions
            match = self.socioeconomic_patterns["luxury_assumptions"].search(text)
            if match:
                flags.append(BiasFlag(
                    category="socioeconomic",
                    severity="medium",
                    confidence=0.65,
                    location=location,
                    issue=f"Assumes access to luxury items: {match.group()}",
                    evidence=match.group(),
                    suggestion="Use more universally accessible examples"
                ))

            # Check class stereotypes
            for pattern, issue in self.socioeconomic_patterns["class_stereotypes"]:
                if re.search(pattern, text, re.IGNORECASE):
                    flags.append(BiasFlag(
                        category="socioeconomic",
                        severity="high",
                        confidence=0.80,
                        location=location,
                        issue=issue,
                        evidence=text[:100],
                        suggestion="Avoid stereotyping based on economic status"
                    ))

        return flags

    def _check_ableist_language(self, text_dict: Dict[str, str], content: Dict) -> List[BiasFlag]:
        """Check for ableist language"""
        flags = []

        for location, text in text_dict.items():
            # Check ableist terms
            match = self.ableist_patterns["ableist_terms"].search(text)
            if match:
                term = match.group()
                # Some terms are acceptable in mathematical context
                if term.lower() not in ["blind", "deaf"] or "study" not in text.lower():
                    flags.append(BiasFlag(
                        category="disability",
                        severity="high",
                        confidence=0.75,
                        location=location,
                        issue=f"Potentially ableist language: {term}",
                        evidence=term,
                        suggestion="Use neutral descriptive language"
                    ))

        return flags

    def _check_geographic_bias(self, text_dict: Dict[str, str], content: Dict) -> List[BiasFlag]:
        """Check for geographic/cultural bias"""
        flags = []

        for location, text in text_dict.items():
            # Check US-centric content
            match = self.geographic_patterns["us_centric"].search(text)
            if match:
                flags.append(BiasFlag(
                    category="geographic",
                    severity="low",
                    confidence=0.60,
                    location=location,
                    issue=f"US-centric reference: {match.group()}",
                    evidence=match.group(),
                    suggestion="Consider using internationally recognizable examples"
                ))

            # Check Western holiday bias
            for pattern, issue in self.geographic_patterns["western_bias"]:
                if re.search(pattern, text, re.IGNORECASE):
                    flags.append(BiasFlag(
                        category="geographic",
                        severity="low",
                        confidence=0.55,
                        location=location,
                        issue=issue,
                        evidence=text[:100],
                        suggestion="Balance with diverse cultural references"
                    ))

        return flags

    def _check_name_diversity(self, text_dict: Dict[str, str]) -> float:
        """Check diversity of names used in examples"""
        all_text = " ".join(text_dict.values())

        found_cultures = set()
        total_names = 0

        for culture, names in self.diverse_names.items():
            for name in names:
                if re.search(r'\b' + name + r'\b', all_text, re.IGNORECASE):
                    found_cultures.add(culture)
                    total_names += 1

        if total_names == 0:
            return 1.0  # No names = no bias

        # Diversity score = number of different cultures represented / total possible
        diversity = len(found_cultures) / len(self.diverse_names)

        return diversity

    def _calculate_bias_score(self, flags: List[BiasFlag]) -> float:
        """Calculate overall bias score (0=no bias, 1=severe)"""
        if not flags:
            return 0.0

        # Weight by severity
        severity_weights = {
            "low": 0.25,
            "medium": 0.50,
            "high": 0.75,
            "critical": 1.0
        }

        total_score = sum(severity_weights[f.severity] * f.confidence for f in flags)
        max_score = len(flags)

        return min(total_score / max_score, 1.0) if max_score > 0 else 0.0

    def _assess_risk(self, bias_score: float, flags: List[BiasFlag]) -> str:
        """Assess overall risk level"""
        # Check for critical flags
        critical_flags = [f for f in flags if f.severity == "critical"]
        if critical_flags:
            return "reject_recommended"

        # Check for high severity flags
        high_severity_flags = [f for f in flags if f.severity == "high"]
        if len(high_severity_flags) >= 2:
            return "review_recommended"

        # Check bias score
        if bias_score >= 0.70:
            return "reject_recommended"
        elif bias_score >= 0.40 or high_severity_flags:
            return "review_recommended"
        else:
            return "acceptable"

    def _generate_recommendations(self, flags: List[BiasFlag], diversity_score: float) -> List[str]:
        """Generate recommendations based on findings"""
        recommendations = []

        if not flags and diversity_score >= 0.5:
            recommendations.append("Content appears bias-free and inclusive")
            return recommendations

        # Group by category
        by_category = {}
        for flag in flags:
            by_category.setdefault(flag.category, []).append(flag)

        for category, cat_flags in by_category.items():
            if category == "gender":
                recommendations.append("Review gender representation and use inclusive language")
            elif category == "socioeconomic":
                recommendations.append("Consider using more economically accessible examples")
            elif category == "disability":
                recommendations.append("Remove ableist language and check accessibility")
            elif category == "geographic":
                recommendations.append("Balance cultural references for international audience")

        if diversity_score < 0.3:
            recommendations.append("Increase name diversity to represent multiple cultures")

        return recommendations


# Convenience function
def detect_bias(
    item_id: str,
    content: Dict[str, Any],
    sensitivity: str = "medium"
) -> BiasReport:
    """
    Convenience function to detect bias in content.

    Args:
        item_id: Item identifier
        content: Content dict with text to analyze
        sensitivity: Detection sensitivity level

    Returns:
        BiasReport
    """
    detector = BiasDetector(sensitivity=sensitivity)
    return detector.analyze(item_id, content)
