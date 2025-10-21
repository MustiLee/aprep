"""
Unit tests for Taxonomy Manager
"""

import pytest
import json
from pathlib import Path

from src.agents.taxonomy_manager import (
    TaxonomyManager,
    Course,
    Unit,
    Topic,
    LearningObjective
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory"""
    data_dir = tmp_path / "taxonomy"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir)


@pytest.fixture
def manager(temp_data_dir):
    """Create manager instance with temp directory"""
    return TaxonomyManager(data_dir=temp_data_dir)


@pytest.fixture
def sample_course():
    """Create a sample course for testing"""
    # Create learning objectives
    lo1 = LearningObjective(
        code="CHA-4.A",
        description="Calculate derivatives using power rule",
        skills=["Mathematical Procedures"],
        difficulty_level=2
    )

    lo2 = LearningObjective(
        code="CHA-4.B",
        description="Apply chain rule for composite functions",
        skills=["Mathematical Procedures", "Connecting Concepts"],
        difficulty_level=3
    )

    # Create topics
    topic1 = Topic(
        code="2.1",
        title="Power Rule",
        description="Derivatives using power rule",
        learning_objectives=[lo1],
        difficulty_level=2
    )

    topic2 = Topic(
        code="2.2",
        title="Chain Rule",
        description="Derivatives of composite functions",
        learning_objectives=[lo2],
        difficulty_level=3
    )

    # Create unit
    unit = Unit(
        code="Unit 2",
        title="Differentiation: Definition and Fundamental Properties",
        topics=[topic1, topic2],
        weight_percentage=10.0
    )

    # Create course
    course = Course(
        id="ap_calculus_bc",
        title="AP Calculus BC",
        code="AP-CALC-BC",
        units=[unit]
    )

    return course


def test_initialization(manager, temp_data_dir):
    """Test manager initialization"""
    assert manager.data_dir == Path(temp_data_dir)
    assert manager.ced_parser is not None


def test_save_and_load_course(manager, sample_course):
    """Test saving and loading a course"""
    # Save
    manager.save_course(sample_course)

    # Load
    loaded = manager.load_course("ap_calculus_bc")

    assert loaded is not None
    assert loaded.id == "ap_calculus_bc"
    assert loaded.title == "AP Calculus BC"
    assert len(loaded.units) == 1
    assert len(loaded.units[0].topics) == 2


def test_load_nonexistent_course(manager):
    """Test loading nonexistent course"""
    result = manager.load_course("nonexistent_course")
    assert result is None


def test_get_unit(manager, sample_course):
    """Test getting a specific unit"""
    # Save course first
    manager.save_course(sample_course)

    # Get unit
    unit = manager.get_unit("ap_calculus_bc", "Unit 2")

    assert unit is not None
    assert unit.code == "Unit 2"
    assert unit.title == "Differentiation: Definition and Fundamental Properties"


def test_get_topic(manager, sample_course):
    """Test getting a specific topic"""
    # Save course first
    manager.save_course(sample_course)

    # Get topic
    topic = manager.get_topic("ap_calculus_bc", "2.1")

    assert topic is not None
    assert topic.code == "2.1"
    assert topic.title == "Power Rule"
    assert len(topic.learning_objectives) == 1


def test_get_learning_objective(manager, sample_course):
    """Test getting a specific learning objective"""
    # Save course first
    manager.save_course(sample_course)

    # Get LO
    lo = manager.get_learning_objective("ap_calculus_bc", "CHA-4.A")

    assert lo is not None
    assert lo.code == "CHA-4.A"
    assert "power rule" in lo.description.lower()


def test_search_learning_objectives_by_keywords(manager, sample_course):
    """Test searching LOs by keywords"""
    # Save course first
    manager.save_course(sample_course)

    # Search
    results = manager.search_learning_objectives(
        course_id="ap_calculus_bc",
        keywords=["power rule"]
    )

    assert len(results) == 1
    assert results[0]["learning_objective"]["code"] == "CHA-4.A"
    assert results[0]["topic_code"] == "2.1"


def test_search_learning_objectives_by_difficulty(manager, sample_course):
    """Test searching LOs by difficulty"""
    # Save course first
    manager.save_course(sample_course)

    # Search for difficulty 3
    results = manager.search_learning_objectives(
        course_id="ap_calculus_bc",
        difficulty_level=3
    )

    assert len(results) == 1
    assert results[0]["learning_objective"]["code"] == "CHA-4.B"


def test_get_topic_los(manager, sample_course):
    """Test getting all LOs for a topic"""
    # Save course first
    manager.save_course(sample_course)

    # Get topic LOs
    los = manager.get_topic_los("ap_calculus_bc", "2.1")

    assert len(los) == 1
    assert los[0].code == "CHA-4.A"


def test_get_unit_los(manager, sample_course):
    """Test getting all LOs for a unit"""
    # Save course first
    manager.save_course(sample_course)

    # Get unit LOs
    los = manager.get_unit_los("ap_calculus_bc", "Unit 2")

    assert len(los) == 2
    assert any(lo.code == "CHA-4.A" for lo in los)
    assert any(lo.code == "CHA-4.B" for lo in los)


def test_assign_difficulty_to_topic(manager, sample_course):
    """Test assigning difficulty level to a topic"""
    # Save course first
    manager.save_course(sample_course)

    # Assign difficulty
    result = manager.assign_difficulty_level(
        course_id="ap_calculus_bc",
        target_type="topic",
        target_code="2.1",
        difficulty_level=4
    )

    assert result is True

    # Verify
    topic = manager.get_topic("ap_calculus_bc", "2.1")
    assert topic.difficulty_level == 4


def test_assign_difficulty_to_lo(manager, sample_course):
    """Test assigning difficulty level to a learning objective"""
    # Save course first
    manager.save_course(sample_course)

    # Assign difficulty
    result = manager.assign_difficulty_level(
        course_id="ap_calculus_bc",
        target_type="lo",
        target_code="CHA-4.A",
        difficulty_level=5
    )

    assert result is True

    # Verify
    lo = manager.get_learning_objective("ap_calculus_bc", "CHA-4.A")
    assert lo.difficulty_level == 5


def test_get_course_statistics(manager, sample_course):
    """Test getting course statistics"""
    # Save course first
    manager.save_course(sample_course)

    # Get stats
    stats = manager.get_course_statistics("ap_calculus_bc")

    assert stats["course_id"] == "ap_calculus_bc"
    assert stats["total_units"] == 1
    assert stats["total_topics"] == 2
    assert stats["total_learning_objectives"] == 2
    assert stats["avg_los_per_topic"] == 1.0
    assert "difficulty_distribution" in stats


def test_list_courses(manager, sample_course):
    """Test listing all courses"""
    # Save multiple courses
    manager.save_course(sample_course)

    # Create another course
    course2 = Course(
        id="ap_calculus_ab",
        title="AP Calculus AB",
        code="AP-CALC-AB",
        units=[]
    )
    manager.save_course(course2)

    # List courses
    courses = manager.list_courses()

    assert len(courses) == 2
    assert "ap_calculus_bc" in courses
    assert "ap_calculus_ab" in courses


def test_export_flat_lo_list(manager, sample_course, tmp_path):
    """Test exporting flat LO list"""
    # Save course first
    manager.save_course(sample_course)

    # Export
    output_file = tmp_path / "los_export.json"
    flat_list = manager.export_flat_lo_list(
        course_id="ap_calculus_bc",
        output_file=str(output_file)
    )

    # Verify in-memory result
    assert len(flat_list) == 2
    assert all("course_id" in item for item in flat_list)
    assert all("lo_code" in item for item in flat_list)

    # Verify file was created
    assert output_file.exists()

    # Load and verify
    with open(output_file, 'r') as f:
        loaded = json.load(f)

    assert len(loaded) == 2


def test_learning_objective_validation():
    """Test LearningObjective Pydantic validation"""
    # Valid LO
    lo = LearningObjective(
        code="TEST-1.A",
        description="Test description",
        difficulty_level=3
    )

    assert lo.code == "TEST-1.A"
    assert lo.difficulty_level == 3

    # Invalid difficulty (out of range)
    with pytest.raises(Exception):  # Pydantic ValidationError
        LearningObjective(
            code="TEST-1.A",
            description="Test",
            difficulty_level=10  # Invalid: should be 1-5
        )


def test_topic_structure():
    """Test Topic structure"""
    lo = LearningObjective(
        code="TEST-1.A",
        description="Test LO"
    )

    topic = Topic(
        code="1.1",
        title="Test Topic",
        learning_objectives=[lo],
        keywords=["test", "topic"]
    )

    assert len(topic.learning_objectives) == 1
    assert topic.learning_objectives[0].code == "TEST-1.A"
    assert "test" in topic.keywords


def test_unit_structure():
    """Test Unit structure"""
    lo = LearningObjective(code="TEST-1.A", description="Test")
    topic = Topic(code="1.1", title="Test Topic", learning_objectives=[lo])

    unit = Unit(
        code="Unit 1",
        title="Test Unit",
        topics=[topic],
        weight_percentage=15.0
    )

    assert len(unit.topics) == 1
    assert unit.weight_percentage == 15.0


def test_course_version_tracking(manager):
    """Test course version tracking"""
    course = Course(
        id="test_course",
        title="Test Course",
        code="TEST",
        version="2.0.0"
    )

    manager.save_course(course)

    loaded = manager.load_course("test_course")
    assert loaded.version == "2.0.0"


def test_course_metadata(manager):
    """Test course metadata storage"""
    course = Course(
        id="test_course",
        title="Test Course",
        code="TEST",
        metadata={
            "source": "CED",
            "year": 2024,
            "custom_field": "custom_value"
        }
    )

    manager.save_course(course)

    loaded = manager.load_course("test_course")
    assert loaded.metadata["source"] == "CED"
    assert loaded.metadata["year"] == 2024


def test_topic_prerequisites(manager, sample_course):
    """Test topic prerequisites"""
    # Add prerequisite to second topic
    sample_course.units[0].topics[1].prerequisites = ["2.1"]

    manager.save_course(sample_course)

    # Load and verify
    loaded = manager.load_course("ap_calculus_bc")
    chain_rule_topic = loaded.units[0].topics[1]

    assert "2.1" in chain_rule_topic.prerequisites


def test_persistence_across_instances(temp_data_dir, sample_course):
    """Test data persistence across manager instances"""
    # Create first manager and save data
    manager1 = TaxonomyManager(data_dir=temp_data_dir)
    manager1.save_course(sample_course)

    # Create second manager instance
    manager2 = TaxonomyManager(data_dir=temp_data_dir)

    # Verify data persisted
    loaded = manager2.load_course("ap_calculus_bc")
    assert loaded is not None
    assert loaded.id == "ap_calculus_bc"
    assert len(loaded.units) == 1


def test_search_multiple_keywords(manager, sample_course):
    """Test searching with multiple keywords"""
    # Save course
    manager.save_course(sample_course)

    # Search with multiple keywords
    results = manager.search_learning_objectives(
        course_id="ap_calculus_bc",
        keywords=["derivatives", "rule"]
    )

    # Should match both LOs
    assert len(results) >= 1


def test_empty_course_statistics(manager):
    """Test statistics for course with no content"""
    empty_course = Course(
        id="empty_course",
        title="Empty Course",
        code="EMPTY",
        units=[]
    )

    manager.save_course(empty_course)

    stats = manager.get_course_statistics("empty_course")

    assert stats["total_units"] == 0
    assert stats["total_topics"] == 0
    assert stats["total_learning_objectives"] == 0


def test_add_prerequisite(manager, sample_course):
    """Test adding prerequisite relationship"""
    manager.save_course(sample_course)

    # Add prerequisite: Chain Rule depends on Power Rule
    result = manager.add_prerequisite(
        course_id="ap_calculus_bc",
        topic_code="2.2",
        prerequisite_code="2.1"
    )

    assert result is True

    # Verify prerequisite was added
    topic = manager.get_topic("ap_calculus_bc", "2.2")
    assert "2.1" in topic.prerequisites


def test_add_related_topic(manager, sample_course):
    """Test adding related topic relationship"""
    manager.save_course(sample_course)

    # Add related topics
    result = manager.add_related_topic(
        course_id="ap_calculus_bc",
        topic_code="2.1",
        related_topic_code="2.2"
    )

    assert result is True

    # Verify related topic was added
    topic = manager.get_topic("ap_calculus_bc", "2.1")
    assert "2.2" in topic.related_topics


def test_get_topic_prerequisites(manager, sample_course):
    """Test getting prerequisite topics"""
    # Add prerequisite relationship
    sample_course.units[0].topics[1].prerequisites = ["2.1"]
    manager.save_course(sample_course)

    # Get prerequisites
    prerequisites = manager.get_topic_prerequisites(
        course_id="ap_calculus_bc",
        topic_code="2.2"
    )

    assert len(prerequisites) == 1
    assert prerequisites[0].code == "2.1"
    assert prerequisites[0].title == "Power Rule"


def test_get_related_topics(manager, sample_course):
    """Test getting related topics"""
    # Add related topic relationship
    sample_course.units[0].topics[0].related_topics = ["2.2"]
    manager.save_course(sample_course)

    # Get related topics
    related = manager.get_related_topics(
        course_id="ap_calculus_bc",
        topic_code="2.1"
    )

    assert len(related) == 1
    assert related[0].code == "2.2"
    assert related[0].title == "Chain Rule"


def test_get_relationship_graph(manager, sample_course):
    """Test getting complete relationship graph"""
    # Add relationships
    sample_course.units[0].topics[1].prerequisites = ["2.1"]
    sample_course.units[0].topics[0].related_topics = ["2.2"]
    manager.save_course(sample_course)

    # Get graph
    graph = manager.get_relationship_graph("ap_calculus_bc")

    assert graph["course_id"] == "ap_calculus_bc"
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 2

    # Check for prerequisite edge
    prereq_edge = next((e for e in graph["edges"] if e["type"] == "prerequisite"), None)
    assert prereq_edge is not None
    assert prereq_edge["from"] == "2.1"
    assert prereq_edge["to"] == "2.2"

    # Check for related edge
    related_edge = next((e for e in graph["edges"] if e["type"] == "related"), None)
    assert related_edge is not None


def test_related_topics_field(manager):
    """Test that related_topics field exists and persists"""
    topic = Topic(
        code="test_topic",
        title="Test Topic",
        prerequisites=["prereq_1"],
        related_topics=["related_1", "related_2"]
    )

    course = Course(
        id="test_course",
        title="Test",
        code="TEST",
        units=[Unit(code="U1", title="Unit 1", topics=[topic])]
    )

    manager.save_course(course)

    # Load and verify both fields persist
    loaded = manager.load_course("test_course")
    loaded_topic = loaded.units[0].topics[0]

    assert loaded_topic.prerequisites == ["prereq_1"]
    assert loaded_topic.related_topics == ["related_1", "related_2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
