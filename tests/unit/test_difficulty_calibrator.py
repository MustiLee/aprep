"""
Unit tests for Difficulty Calibrator
"""

import pytest
import json
import numpy as np
from pathlib import Path

from src.agents.difficulty_calibrator import (
    DifficultyCalibrator,
    IRTParameters,
    AnchorItem,
    ResponseData
)


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories"""
    data_dir = tmp_path / "irt"
    models_dir = tmp_path / "models/irt"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir), str(models_dir)


@pytest.fixture
def calibrator(temp_dirs):
    """Create calibrator instance with temp directories"""
    data_dir, models_dir = temp_dirs
    return DifficultyCalibrator(data_dir=data_dir, models_dir=models_dir)


@pytest.fixture
def sample_variant():
    """Create a sample variant for testing"""
    return {
        "id": "variant_001",
        "template_id": "template_001",
        "stimulus": "Calculate the derivative of f(x) = x^3",
        "solution": "f'(x) = 3x^2",
        "metadata": {
            "topic_id": "derivatives",
            "course_id": "ap_calculus_bc"
        }
    }


@pytest.fixture
def sample_responses():
    """Create sample response data"""
    responses = []

    # Simulate responses from students at different ability levels
    # High ability students (theta ~ 1.5)
    for i in range(5):
        responses.append(ResponseData(
            student_id=f"student_high_{i}",
            item_id="item_001",
            correct=True
        ))

    # Medium ability students (theta ~ 0)
    for i in range(5):
        correct = i < 3  # 60% correct
        responses.append(ResponseData(
            student_id=f"student_med_{i}",
            item_id="item_001",
            correct=correct
        ))

    # Low ability students (theta ~ -1.5)
    for i in range(5):
        correct = i < 1  # 20% correct
        responses.append(ResponseData(
            student_id=f"student_low_{i}",
            item_id="item_001",
            correct=correct
        ))

    return responses


def test_initialization(calibrator, temp_dirs):
    """Test calibrator initialization"""
    data_dir, models_dir = temp_dirs

    assert calibrator.data_dir == Path(data_dir)
    assert calibrator.models_dir == Path(models_dir)
    assert calibrator.item_params_file.exists()
    assert calibrator.anchors_file.exists()


def test_irt_2pl_model(calibrator):
    """Test IRT 2PL probability calculation"""
    # Test at different ability levels
    a = 1.0
    b = 0.0

    # At ability = difficulty, probability should be 0.5
    prob = calibrator._irt_2pl(theta=0.0, a=a, b=b)
    assert abs(prob - 0.5) < 0.01

    # At ability > difficulty, probability should be > 0.5
    prob = calibrator._irt_2pl(theta=1.0, a=a, b=b)
    assert prob > 0.5

    # At ability < difficulty, probability should be < 0.5
    prob = calibrator._irt_2pl(theta=-1.0, a=a, b=b)
    assert prob < 0.5


def test_irt_2pl_with_discrimination(calibrator):
    """Test IRT 2PL with different discrimination values"""
    theta = 0.5
    b = 0.0

    # Low discrimination
    prob_low = calibrator._irt_2pl(theta, a=0.5, b=b)

    # High discrimination
    prob_high = calibrator._irt_2pl(theta, a=2.0, b=b)

    # High discrimination should give more extreme probabilities
    assert abs(prob_high - 0.5) > abs(prob_low - 0.5)


def test_estimate_initial_difficulty_default(calibrator, sample_variant):
    """Test initial difficulty estimation with defaults"""
    params = calibrator.estimate_initial_difficulty(sample_variant)

    assert params.item_id == "variant_001"
    assert 0.1 <= params.a <= 3.0  # Reasonable discrimination
    assert -4.0 <= params.b <= 4.0  # Reasonable difficulty
    assert params.n_responses == 0


def test_estimate_initial_difficulty_with_anchors(calibrator, sample_variant):
    """Test initial difficulty estimation using anchor items"""
    # Create anchor item
    anchor_params = IRTParameters(
        item_id="anchor_001",
        a=1.2,
        b=0.5,
        n_responses=100
    )

    anchor = AnchorItem(
        item_id="anchor_001",
        topic_id="derivatives",
        course_id="ap_calculus_bc",
        irt_params=anchor_params,
        is_validated=True
    )

    # Add anchor
    calibrator.anchor_items["ap_calculus_bc:derivatives"] = [anchor]

    # Estimate with context
    context = {
        "topic_id": "derivatives",
        "course_id": "ap_calculus_bc"
    }

    params = calibrator.estimate_initial_difficulty(sample_variant, context=context)

    # Should use anchor-based estimation
    assert abs(params.b - 0.5) < 1.0  # Close to anchor difficulty
    assert params.metadata.get("estimation_method") == "anchor_based"


def test_calibrate_from_responses(calibrator, sample_responses):
    """Test calibrating item parameters from responses"""
    # Calibrate
    params = calibrator.calibrate_from_responses(
        item_id="item_001",
        responses=sample_responses
    )

    assert params.item_id == "item_001"
    assert params.a > 0
    assert params.n_responses == len(sample_responses)

    # Difficulty should be moderate (around 0) given the response pattern
    assert -2.0 <= params.b <= 2.0


def test_calibrate_from_responses_with_abilities(calibrator, sample_responses):
    """Test calibration with known student abilities"""
    # Create student abilities matching the response pattern
    student_abilities = {}

    # High ability students
    for i in range(5):
        student_abilities[f"student_high_{i}"] = 1.5

    # Medium ability students
    for i in range(5):
        student_abilities[f"student_med_{i}"] = 0.0

    # Low ability students
    for i in range(5):
        student_abilities[f"student_low_{i}"] = -1.5

    # Calibrate
    params = calibrator.calibrate_from_responses(
        item_id="item_001",
        responses=sample_responses,
        student_abilities=student_abilities
    )

    assert params.item_id == "item_001"
    assert params.a > 0
    assert params.n_responses == len(sample_responses)


def test_update_difficulty_online(calibrator):
    """Test online difficulty update"""
    # Initial parameters
    initial_params = IRTParameters(
        item_id="item_001",
        a=1.0,
        b=0.0,
        n_responses=10
    )

    calibrator.item_params["item_001"] = initial_params
    initial_b = initial_params.b

    # Simulate a correct response from high-ability student
    response = ResponseData(
        student_id="student_001",
        item_id="item_001",
        correct=True
    )

    updated_params = calibrator.update_difficulty_online(
        item_id="item_001",
        response=response,
        student_ability=2.0,  # High ability
        learning_rate=0.1
    )

    # Difficulty should decrease (item was easier than expected)
    assert updated_params.b < initial_b
    assert updated_params.n_responses == 11


def test_add_anchor_item(calibrator):
    """Test adding an anchor item"""
    params = IRTParameters(
        item_id="anchor_001",
        a=1.2,
        b=0.5,
        n_responses=100
    )

    anchor = calibrator.add_anchor_item(
        item_id="anchor_001",
        topic_id="derivatives",
        course_id="ap_calculus_bc",
        irt_params=params
    )

    assert anchor.item_id == "anchor_001"
    assert anchor.topic_id == "derivatives"
    assert anchor.irt_params.b == 0.5


def test_get_topic_anchors(calibrator):
    """Test retrieving topic anchors"""
    # Add multiple anchors
    for i in range(3):
        params = IRTParameters(
            item_id=f"anchor_{i}",
            a=1.0,
            b=float(i),
            n_responses=100
        )

        calibrator.add_anchor_item(
            item_id=f"anchor_{i}",
            topic_id="derivatives",
            course_id="ap_calculus_bc",
            irt_params=params
        )

    # Get anchors
    anchors = calibrator.get_topic_anchors("derivatives", course_id="ap_calculus_bc")

    assert len(anchors) == 3


def test_get_item_probability(calibrator):
    """Test getting item probability for student"""
    # Set up item parameters
    params = IRTParameters(
        item_id="item_001",
        a=1.0,
        b=0.0,
        n_responses=50
    )

    calibrator.item_params["item_001"] = params

    # Get probability for different abilities
    prob_low = calibrator.get_item_probability("item_001", student_ability=-1.0)
    prob_med = calibrator.get_item_probability("item_001", student_ability=0.0)
    prob_high = calibrator.get_item_probability("item_001", student_ability=1.0)

    assert prob_low < prob_med < prob_high
    assert abs(prob_med - 0.5) < 0.01  # At difficulty level


def test_recommend_items_by_difficulty(calibrator):
    """Test recommending items by difficulty"""
    # Add items with various difficulties
    for i in range(10):
        params = IRTParameters(
            item_id=f"item_{i}",
            a=1.0,
            b=float(i - 5),  # Difficulties from -5 to 4
            n_responses=50
        )
        calibrator.item_params[f"item_{i}"] = params

    # Recommend items around difficulty 0
    recommendations = calibrator.recommend_items_by_difficulty(
        target_difficulty=0.0,
        count=3,
        tolerance=1.0
    )

    assert len(recommendations) <= 3
    # All should be within tolerance
    for item_id, params in recommendations:
        assert abs(params.b - 0.0) <= 1.0


def test_get_statistics(calibrator):
    """Test getting calibration statistics"""
    # Add some calibrated items
    for i in range(10):
        params = IRTParameters(
            item_id=f"item_{i}",
            a=1.0 + i * 0.1,
            b=float(i - 5),
            n_responses=50
        )
        calibrator.item_params[f"item_{i}"] = params

    stats = calibrator.get_statistics()

    assert stats["total_items"] == 10
    assert stats["calibrated_items"] == 10  # All have >= 10 responses
    assert "difficulty_mean" in stats
    assert "difficulty_std" in stats
    assert "discrimination_mean" in stats


def test_estimate_student_abilities(calibrator):
    """Test estimating student abilities from responses"""
    responses = [
        # High-performing student
        ResponseData(student_id="student_001", item_id="item_1", correct=True),
        ResponseData(student_id="student_001", item_id="item_2", correct=True),
        ResponseData(student_id="student_001", item_id="item_3", correct=True),

        # Low-performing student
        ResponseData(student_id="student_002", item_id="item_1", correct=False),
        ResponseData(student_id="student_002", item_id="item_2", correct=False),
        ResponseData(student_id="student_002", item_id="item_3", correct=False),
    ]

    abilities = calibrator._estimate_student_abilities(responses)

    assert "student_001" in abilities
    assert "student_002" in abilities

    # High performer should have positive ability
    assert abilities["student_001"] > 0

    # Low performer should have negative ability
    assert abilities["student_002"] < 0


def test_estimate_complexity(calibrator, sample_variant):
    """Test complexity estimation"""
    complexity = calibrator._estimate_complexity(sample_variant)

    assert 0.0 <= complexity <= 1.0


def test_persistence(temp_dirs):
    """Test data persistence across calibrator instances"""
    data_dir, models_dir = temp_dirs

    # Create first calibrator and add data
    calibrator1 = DifficultyCalibrator(data_dir=data_dir, models_dir=models_dir)

    params = IRTParameters(
        item_id="item_persist",
        a=1.5,
        b=0.75,
        n_responses=50
    )

    calibrator1.item_params["item_persist"] = params
    calibrator1._save_item_params()

    # Create second calibrator instance
    calibrator2 = DifficultyCalibrator(data_dir=data_dir, models_dir=models_dir)

    # Verify data persisted
    assert "item_persist" in calibrator2.item_params
    assert calibrator2.item_params["item_persist"].a == 1.5
    assert calibrator2.item_params["item_persist"].b == 0.75


def test_anchor_persistence(temp_dirs):
    """Test anchor persistence across instances"""
    data_dir, models_dir = temp_dirs

    # Create first calibrator and add anchor
    calibrator1 = DifficultyCalibrator(data_dir=data_dir, models_dir=models_dir)

    params = IRTParameters(
        item_id="anchor_persist",
        a=1.0,
        b=0.5,
        n_responses=100
    )

    calibrator1.add_anchor_item(
        item_id="anchor_persist",
        topic_id="test_topic",
        course_id="test_course",
        irt_params=params
    )

    # Create second calibrator instance
    calibrator2 = DifficultyCalibrator(data_dir=data_dir, models_dir=models_dir)

    # Verify anchor persisted
    anchors = calibrator2.get_topic_anchors("test_topic", course_id="test_course")
    assert len(anchors) == 1
    assert anchors[0].item_id == "anchor_persist"


def test_insufficient_responses_warning(calibrator):
    """Test warning for insufficient responses"""
    # Create very few responses
    responses = [
        ResponseData(student_id="s1", item_id="item_001", correct=True),
        ResponseData(student_id="s2", item_id="item_001", correct=False),
    ]

    # Should still return parameters but with warning logged
    params = calibrator.calibrate_from_responses("item_001", responses)

    assert params is not None
    assert params.item_id == "item_001"


def test_irt_numpy_vectorization(calibrator):
    """Test IRT calculation with numpy arrays"""
    # Test vectorized calculation
    theta_array = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    a = 1.0
    b = 0.0

    probs = calibrator._irt_2pl(theta_array, a, b)

    assert len(probs) == 5
    assert all(0 <= p <= 1 for p in probs)

    # Should be increasing
    for i in range(len(probs) - 1):
        assert probs[i] < probs[i + 1]


def test_parameter_bounds(calibrator, sample_responses):
    """Test that calibrated parameters stay within bounds"""
    params = calibrator.calibrate_from_responses("item_001", sample_responses)

    # Check bounds
    assert 0.1 <= params.a <= 3.0
    assert -4.0 <= params.b <= 4.0


def test_online_update_clipping(calibrator):
    """Test that online updates clip to reasonable ranges"""
    # Start with extreme parameters
    initial_params = IRTParameters(
        item_id="item_001",
        a=1.0,
        b=3.5,  # Near upper bound
        n_responses=10
    )

    calibrator.item_params["item_001"] = initial_params

    # Multiple updates that would push beyond bounds
    for i in range(10):
        response = ResponseData(
            student_id=f"student_{i}",
            item_id="item_001",
            correct=False  # All wrong, would increase difficulty
        )

        params = calibrator.update_difficulty_online(
            item_id="item_001",
            response=response,
            student_ability=2.0,
            learning_rate=0.5  # High learning rate
        )

    # Should be clipped to bounds
    assert -4.0 <= params.b <= 4.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
