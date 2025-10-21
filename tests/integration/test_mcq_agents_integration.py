"""
Integration test for MCQ Agents
Tests the integration of:
- Misconception Database Manager
- Taxonomy Manager
- Difficulty Calibrator
"""

import pytest
from src.agents.misconception_database_manager import MisconceptionDatabaseManager
from src.agents.taxonomy_manager import TaxonomyManager, Course, Unit, Topic, LearningObjective
from src.agents.difficulty_calibrator import DifficultyCalibrator


def test_agent_integration_workflow(tmp_path):
    """Test complete workflow of 3 MCQ agents working together"""

    # Initialize agents
    misconception_mgr = MisconceptionDatabaseManager(
        data_dir=str(tmp_path / "misconceptions"),
        enable_duplicate_detection=False
    )
    taxonomy_mgr = TaxonomyManager(data_dir=str(tmp_path / "taxonomy"))
    difficulty_calibrator = DifficultyCalibrator(data_dir=str(tmp_path / "calibrator"))

    # Step 1: Create course taxonomy using Pydantic models
    lo = LearningObjective(
        code="FUN-3.A",
        description="Calculate derivatives using chain rule"
    )

    topic = Topic(
        code="2.3",
        title="Chain Rule",
        description="Application of chain rule in differentiation",
        learning_objectives=[lo]
    )

    unit = Unit(
        code="Unit 2",
        title="Differentiation",
        description="Fundamental concepts of differentiation",
        topics=[topic]
    )

    course = Course(
        id="ap_calculus_bc",
        title="AP Calculus BC",
        code="CALC_BC",
        description="Advanced Placement Calculus BC",
        units=[unit]
    )

    taxonomy_mgr.save_course(course)
    loaded_course = taxonomy_mgr.load_course("ap_calculus_bc")
    assert loaded_course is not None
    print("✓ Taxonomy created for AP Calculus BC")

    # Step 2: Add misconceptions for this topic
    misc_id = misconception_mgr.add_misconception(
        classification={
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.3",
            "category": "procedural_error"
        },
        description={
            "short": "Forget chain rule inner derivative",
            "detailed": "Students correctly differentiate the outer function but forget to multiply by the derivative of the inner function, leading to incomplete application."
        },
        frequency={"overall": "high"},
        mathematical_examples=[
            {
                "correct": "d/dx[sin(2x)] = 2cos(2x)",
                "misconception": "d/dx[sin(2x)] = cos(2x)",
                "error_type": "omission",
                "difficulty": "medium"
            }
        ],
        distractor_generation={
            "transformation_rule": "REMOVE_INNER_DERIVATIVE",
            "template": "{{outer_derivative}}({{inner_function}})",
            "plausibility_score": 8.5,
            "recommended_questions": ["chain_rule"]
        }
    )

    misconception = misconception_mgr.get_misconception(misc_id)
    assert misconception is not None
    print(f"✓ Misconception added: {misc_id}")

    # Step 3: Search misconceptions by topic
    results = misconception_mgr.search_misconceptions(
        course_id="ap_calculus_bc",
        topic_id="t2.3"
    )
    assert len(results) >= 1
    print(f"✓ Found {len(results)} misconception(s) for chain rule")

    # Step 4: Get taxonomy info for the topic
    topic_retrieved = taxonomy_mgr.get_topic("ap_calculus_bc", "2.3")
    assert topic_retrieved is not None
    assert topic_retrieved.title == "Chain Rule"
    print(f"✓ Retrieved topic from taxonomy: {topic_retrieved.title}")

    # Step 5: Estimate difficulty for a question
    variant = {
        "variant_id": "calc_bc_chain_001_v1",
        "template_id": "chain_rule_trig",
        "topic_id": "2.3",
        "stimulus": "Find the derivative of sin(2x²)",
        "num_steps": 2,
        "concepts_required": ["chain_rule", "trig_derivatives"]
    }

    irt_params = difficulty_calibrator.estimate_initial_difficulty(variant)
    initial_difficulty = irt_params.b  # Get difficulty parameter
    assert -3.0 <= initial_difficulty <= 3.0  # IRT scale
    print(f"✓ Estimated initial difficulty (IRT b-parameter): {initial_difficulty:.2f}")

    # Step 6: Get statistics from all agents
    misc_stats = misconception_mgr.get_database_statistics()
    assert misc_stats.total_misconceptions >= 1
    print(f"✓ Misconception DB stats: {misc_stats.total_misconceptions} total")

    course_stats = taxonomy_mgr.get_course_statistics("ap_calculus_bc")
    assert course_stats["total_units"] >= 1
    print(f"✓ Taxonomy stats: {course_stats['total_units']} units, {course_stats['total_topics']} topics")

    calibrator_stats = difficulty_calibrator.get_statistics()
    print(f"✓ Calibrator stats: {calibrator_stats}")

    print("\n✅ All integration tests passed!")
    print("=" * 60)
    print("SUMMARY:")
    print(f"  - Taxonomy: {course_stats['total_topics']} topics in {course_stats['total_units']} units")
    print(f"  - Misconceptions: {misc_stats.total_misconceptions} documented")
    print(f"  - Difficulty estimates: Initial b={initial_difficulty:.2f}")
    print(f"  - All 3 agents working together successfully!")
    print("=" * 60)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_agent_integration_workflow(tmp)
