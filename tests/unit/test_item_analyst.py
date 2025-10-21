"""Unit tests for Item Analyst agent"""

import pytest
import numpy as np
from src.agents.item_analyst import (
    ItemAnalyst,
    ItemStatistics,
    DistractorStats
)


@pytest.fixture
def analyst():
    """Create item analyst"""
    return ItemAnalyst(
        min_p_value=0.20,
        max_p_value=0.80,
        min_discrimination=0.30
    )


@pytest.fixture
def good_responses():
    """Create response data for a good item"""
    # High performers mostly correct, low performers mostly incorrect
    responses = []
    for i in range(50):
        ability = i / 50.0  # 0.0 to 0.98
        # High ability -> more likely correct
        if ability > 0.6:
            answer = "A" if np.random.random() < 0.8 else "B"
        else:
            answer = "B" if np.random.random() < 0.7 else "A"

        responses.append({
            "student_id": f"s{i}",
            "answer": answer,
            "ability": ability,
            "total_score": ability * 100
        })

    return responses


class TestItemAnalyst:
    """Test Item Analyst functionality"""

    def test_initialization(self, analyst):
        """Test analyst initialization"""
        assert analyst is not None
        assert analyst.min_p_value == 0.20
        assert analyst.max_p_value == 0.80
        assert analyst.min_discrimination == 0.30

    def test_analyze_item_basic(self, analyst):
        """Test basic item analysis"""
        responses = [
            {"student_id": "s1", "answer": "A", "ability": 0.8},
            {"student_id": "s2", "answer": "A", "ability": 0.7},
            {"student_id": "s3", "answer": "B", "ability": 0.3},
            {"student_id": "s4", "answer": "A", "ability": 0.9},
            {"student_id": "s5", "answer": "B", "ability": 0.2},
        ]

        stats = analyst.analyze_item(
            item_id="q001",
            responses=responses,
            correct_answer="A",
            distractors=["B", "C", "D"]
        )

        assert isinstance(stats, ItemStatistics)
        assert stats.item_id == "q001"
        assert stats.n_responses == 5
        assert stats.n_correct == 3
        assert stats.p_value == 0.6

    def test_p_value_calculation(self, analyst):
        """Test p-value calculation"""
        # All correct
        responses = [{"student_id": f"s{i}", "answer": "A", "ability": 0.5} for i in range(10)]
        stats = analyst.analyze_item("q001", responses, "A")
        assert stats.p_value == 1.0

        # Half correct
        responses = [
            *[{"student_id": f"s{i}", "answer": "A", "ability": 0.5} for i in range(5)],
            *[{"student_id": f"s{i}", "answer": "B", "ability": 0.5} for i in range(5, 10)]
        ]
        stats = analyst.analyze_item("q002", responses, "A")
        assert stats.p_value == 0.5

        # None correct
        responses = [{"student_id": f"s{i}", "answer": "B", "ability": 0.5} for i in range(10)]
        stats = analyst.analyze_item("q003", responses, "A")
        assert stats.p_value == 0.0

    def test_point_biserial_correlation(self, analyst, good_responses):
        """Test point-biserial correlation calculation"""
        stats = analyst.analyze_item(
            item_id="q001",
            responses=good_responses,
            correct_answer="A"
        )

        assert stats.point_biserial is not None
        # Should have positive discrimination for good item
        assert stats.point_biserial > 0.0

    def test_item_too_easy(self, analyst):
        """Test flagging item that's too easy"""
        # 90% correct
        responses = [
            *[{"student_id": f"s{i}", "answer": "A", "ability": 0.5} for i in range(9)],
            {"student_id": "s10", "answer": "B", "ability": 0.5}
        ]

        stats = analyst.analyze_item("q001", responses, "A")

        assert stats.p_value > analyst.max_p_value
        assert stats.is_problematic is True
        assert any("too easy" in issue.lower() for issue in stats.issues)

    def test_item_too_difficult(self, analyst):
        """Test flagging item that's too difficult"""
        # 10% correct
        responses = [
            {"student_id": "s1", "answer": "A", "ability": 0.5},
            *[{"student_id": f"s{i}", "answer": "B", "ability": 0.5} for i in range(2, 11)]
        ]

        stats = analyst.analyze_item("q001", responses, "A")

        assert stats.p_value < analyst.min_p_value
        assert stats.is_problematic is True
        assert any("too difficult" in issue.lower() for issue in stats.issues)

    def test_low_discrimination(self, analyst):
        """Test flagging low discrimination"""
        # Random answers (no discrimination)
        responses = []
        for i in range(20):
            responses.append({
                "student_id": f"s{i}",
                "answer": "A" if i % 2 == 0 else "B",
                "ability": float(i) / 20
            })

        stats = analyst.analyze_item("q001", responses, "A")

        # Point-biserial should be close to 0 (low discrimination)
        if stats.point_biserial is not None:
            assert abs(stats.point_biserial) < analyst.min_discrimination

    def test_distractor_analysis(self, analyst):
        """Test distractor analysis"""
        responses = [
            {"student_id": "s1", "answer": "A", "ability": 0.8},
            {"student_id": "s2", "answer": "A", "ability": 0.7},
            {"student_id": "s3", "answer": "B", "ability": 0.3},
            {"student_id": "s4", "answer": "B", "ability": 0.4},
            {"student_id": "s5", "answer": "C", "ability": 0.2},
            {"student_id": "s6", "answer": "A", "ability": 0.9},
        ]

        stats = analyst.analyze_item(
            item_id="q001",
            responses=responses,
            correct_answer="A",
            distractors=["B", "C", "D"]
        )

        assert len(stats.distractor_stats) == 3
        # Check B was selected
        b_stats = next(d for d in stats.distractor_stats if d.distractor_id == "B")
        assert b_stats.selection_count == 2
        assert b_stats.selection_rate == pytest.approx(2/6)

    def test_dead_distractor_detection(self, analyst):
        """Test detection of dead distractors"""
        # Distractor D never selected
        responses = [
            {"student_id": f"s{i}", "answer": "A" if i < 5 else "B", "ability": 0.5}
            for i in range(10)
        ]

        stats = analyst.analyze_item(
            item_id="q001",
            responses=responses,
            correct_answer="A",
            distractors=["B", "C", "D"]
        )

        # D should be flagged as dead distractor
        d_stats = next(d for d in stats.distractor_stats if d.distractor_id == "D")
        assert d_stats.selection_count == 0
        assert d_stats.is_problematic is True
        assert d_stats.issue_type == "dead_distractor"

    def test_analyze_batch(self, analyst):
        """Test batch analysis"""
        items = [
            {
                "item_id": "q001",
                "responses": [
                    {"student_id": f"s{i}", "answer": "A", "ability": 0.5}
                    for i in range(5)
                ],
                "correct_answer": "A",
                "distractors": ["B", "C", "D"]
            },
            {
                "item_id": "q002",
                "responses": [
                    {"student_id": f"s{i}", "answer": "B" if i % 2 == 0 else "A", "ability": 0.5}
                    for i in range(10)
                ],
                "correct_answer": "A",
                "distractors": ["B", "C", "D"]
            }
        ]

        batch_result = analyst.analyze_batch(items)

        assert batch_result["total_items"] == 2
        assert len(batch_result["results"]) == 2
        assert "avg_p_value" in batch_result

    def test_get_statistics(self, analyst):
        """Test statistics tracking"""
        # Analyze some items
        responses1 = [{"student_id": f"s{i}", "answer": "A", "ability": 0.5} for i in range(10)]
        analyst.analyze_item("q001", responses1, "A")

        responses2 = [{"student_id": f"s{i}", "answer": "B", "ability": 0.5} for i in range(10)]
        analyst.analyze_item("q002", responses2, "A")  # All wrong

        stats = analyst.get_statistics()

        assert stats["total_analyses"] == 2
        assert stats["problematic_count"] >= 1  # q002 should be problematic

    def test_recommendations_generated(self, analyst):
        """Test that recommendations are generated for problematic items"""
        # Too easy item
        responses = [{"student_id": f"s{i}", "answer": "A", "ability": 0.5} for i in range(10)]
        stats = analyst.analyze_item("q001", responses, "A")

        assert stats.is_problematic is True
        assert len(stats.recommendations) > 0

    def test_empty_responses_error(self, analyst):
        """Test error handling for empty responses"""
        with pytest.raises(Exception):
            analyst.analyze_item("q001", [], "A")

    def test_discrimination_index_calculation(self, analyst):
        """Test upper-lower discrimination index"""
        # Create responses with clear discrimination
        responses = []
        for i in range(30):
            ability = i / 30.0
            # Upper group (high ability) mostly correct
            if ability > 0.73:  # Top 27%
                answer = "A"
            # Lower group (low ability) mostly incorrect
            elif ability < 0.27:  # Bottom 27%
                answer = "B"
            else:
                answer = "A" if i % 2 == 0 else "B"

            responses.append({
                "student_id": f"s{i}",
                "answer": answer,
                "ability": ability
            })

        stats = analyst.analyze_item("q001", responses, "A")

        # Should have positive discrimination index
        assert stats.discrimination_index is not None
        assert stats.discrimination_index > 0.0


class TestDistractorStats:
    """Test DistractorStats model"""

    def test_distractor_stats_creation(self):
        """Test creating distractor statistics"""
        stats = DistractorStats(
            distractor_id="B",
            selection_count=10,
            selection_rate=0.25,
            point_biserial=-0.15
        )

        assert stats.distractor_id == "B"
        assert stats.selection_count == 10
        assert stats.selection_rate == 0.25


class TestIntegration:
    """Integration tests"""

    def test_end_to_end_analysis_workflow(self, analyst, good_responses):
        """Test complete analysis workflow"""
        # Analyze item
        stats = analyst.analyze_item(
            item_id="q001",
            responses=good_responses,
            correct_answer="A",
            distractors=["B", "C", "D"]
        )

        # Should have all key metrics
        assert stats.p_value is not None
        assert stats.point_biserial is not None
        assert len(stats.distractor_stats) == 3

        # Check statistics tracked
        analyst_stats = analyst.get_statistics()
        assert analyst_stats["total_analyses"] == 1
