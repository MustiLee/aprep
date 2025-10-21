"""
Taxonomy Manager Agent

This agent manages the hierarchical taxonomy of courses, units, topics, and learning objectives.
It integrates with the CED Parser to organize curriculum standards and provides mappings
for content generation and validation.

Responsibilities:
- Maintain Course → Unit → Topic → LO hierarchy
- Tag and map learning objectives
- Assign difficulty levels to content
- Cross-reference with CED Parser output
- Provide search and navigation through taxonomy
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.core.logger import setup_logger
from src.core.exceptions import AprepError
from src.agents.ced_parser import CEDParser

logger = setup_logger(__name__)


class LearningObjective(BaseModel):
    """A learning objective within the taxonomy"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    code: str = Field(..., description="Official LO code (e.g., CHA-4.A)")
    description: str = Field(..., description="LO description")

    skills: List[str] = Field(default_factory=list, description="Mathematical practices/skills")
    bloom_level: Optional[str] = Field(None, description="Bloom's taxonomy level")
    difficulty_level: int = Field(default=2, ge=1, le=5)

    keywords: List[str] = Field(default_factory=list)
    related_los: List[str] = Field(default_factory=list, description="Related LO codes")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class Topic(BaseModel):
    """A topic within a unit"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    code: str = Field(..., description="Topic code (e.g., 2.1)")
    title: str = Field(..., description="Topic title")
    description: Optional[str] = Field(None)

    learning_objectives: List[LearningObjective] = Field(default_factory=list)

    difficulty_level: int = Field(default=2, ge=1, le=5)
    estimated_hours: Optional[float] = Field(None, description="Learning time estimate")

    keywords: List[str] = Field(default_factory=list)

    # Relationship mapping (Critical Blocker #2)
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisite topic codes or LO codes")
    related_topics: List[str] = Field(default_factory=list, description="Related topic codes for cross-referencing")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class Unit(BaseModel):
    """A unit within a course"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    code: str = Field(..., description="Unit number (e.g., Unit 2)")
    title: str = Field(..., description="Unit title")
    description: Optional[str] = Field(None)

    topics: List[Topic] = Field(default_factory=list)

    weight_percentage: Optional[float] = Field(None, description="Weight in exam")
    estimated_hours: Optional[float] = Field(None)

    metadata: Dict[str, Any] = Field(default_factory=dict)


class Course(BaseModel):
    """A complete course taxonomy"""

    id: str = Field(..., description="Course ID (e.g., ap_calculus_bc)")
    title: str = Field(..., description="Course title")
    code: str = Field(..., description="Official course code")
    description: Optional[str] = Field(None)

    units: List[Unit] = Field(default_factory=list)

    version: str = Field(default="1.0.0")
    effective_date: Optional[str] = Field(None, description="CED effective date")

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaxonomyManager:
    """
    Manages the course taxonomy hierarchy and provides navigation/search capabilities.
    """

    def __init__(self, data_dir: str = "data/taxonomy"):
        """
        Initialize the Taxonomy Manager.

        Args:
            data_dir: Directory to store taxonomy data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.ced_parser = CEDParser()

        logger.info(f"Initialized TaxonomyManager with data_dir={data_dir}")

    def create_course_from_ced(
        self,
        course_id: str,
        ced_path: str,
        title: Optional[str] = None
    ) -> Course:
        """
        Create course taxonomy from CED document using CED Parser.

        Args:
            course_id: Course identifier
            ced_path: Path to CED PDF
            title: Optional course title override

        Returns:
            Course object with full taxonomy

        Raises:
            AprepError: If parsing fails
        """
        try:
            logger.info(f"Creating course taxonomy from CED: {ced_path}")

            # Parse CED document
            ced_result = self.ced_parser.parse_document(ced_path)

            # Extract structure
            structure = ced_result.get("structure", {})
            learning_objectives = ced_result.get("learning_objectives", [])

            # Create course
            course = Course(
                id=course_id,
                title=title or structure.get("course_name", "Unknown Course"),
                code=course_id.upper().replace("_", " "),
                description=structure.get("description"),
                effective_date=ced_result.get("metadata", {}).get("effective_date"),
                metadata=ced_result.get("metadata", {})
            )

            # Build units from structure
            units_data = structure.get("units", [])

            for unit_data in units_data:
                unit = Unit(
                    code=unit_data.get("unit_number", ""),
                    title=unit_data.get("unit_title", ""),
                    description=unit_data.get("description"),
                    weight_percentage=unit_data.get("weight_percentage")
                )

                # Build topics
                topics_data = unit_data.get("topics", [])

                for topic_data in topics_data:
                    topic = Topic(
                        code=topic_data.get("topic_code", ""),
                        title=topic_data.get("topic_title", ""),
                        description=topic_data.get("description"),
                        keywords=topic_data.get("keywords", [])
                    )

                    # Add learning objectives for this topic
                    topic_los = [
                        lo for lo in learning_objectives
                        if lo.get("topic_code") == topic.code
                    ]

                    for lo_data in topic_los:
                        lo = LearningObjective(
                            code=lo_data.get("lo_code", ""),
                            description=lo_data.get("description", ""),
                            skills=lo_data.get("skills", []),
                            keywords=lo_data.get("keywords", []),
                            metadata=lo_data.get("metadata", {})
                        )
                        topic.learning_objectives.append(lo)

                    unit.topics.append(topic)

                course.units.append(unit)

            # Save course taxonomy
            self.save_course(course)

            logger.info(f"Created course taxonomy: {course_id} with {len(course.units)} units")
            return course

        except Exception as e:
            logger.error(f"Failed to create course from CED: {e}")
            raise AprepError(f"Course creation failed: {e}")

    def save_course(self, course: Course) -> None:
        """
        Save course taxonomy to file.

        Args:
            course: Course object to save
        """
        try:
            file_path = self.data_dir / f"{course.id}.json"

            course.updated_at = datetime.now().isoformat()

            with open(file_path, 'w') as f:
                json.dump(course.model_dump(), f, indent=2)

            logger.info(f"Saved course taxonomy: {course.id}")

        except Exception as e:
            logger.error(f"Failed to save course {course.id}: {e}")
            raise AprepError(f"Course save failed: {e}")

    def load_course(self, course_id: str) -> Optional[Course]:
        """
        Load course taxonomy from file.

        Args:
            course_id: Course identifier

        Returns:
            Course object or None if not found
        """
        try:
            file_path = self.data_dir / f"{course_id}.json"

            if not file_path.exists():
                logger.warning(f"Course not found: {course_id}")
                return None

            with open(file_path, 'r') as f:
                data = json.load(f)

            return Course(**data)

        except Exception as e:
            logger.error(f"Failed to load course {course_id}: {e}")
            return None

    def get_unit(self, course_id: str, unit_code: str) -> Optional[Unit]:
        """Get a specific unit from a course"""
        course = self.load_course(course_id)

        if not course:
            return None

        for unit in course.units:
            if unit.code == unit_code:
                return unit

        return None

    def get_topic(self, course_id: str, topic_code: str) -> Optional[Topic]:
        """Get a specific topic from a course"""
        course = self.load_course(course_id)

        if not course:
            return None

        for unit in course.units:
            for topic in unit.topics:
                if topic.code == topic_code:
                    return topic

        return None

    def get_learning_objective(self, course_id: str, lo_code: str) -> Optional[LearningObjective]:
        """Get a specific learning objective from a course"""
        course = self.load_course(course_id)

        if not course:
            return None

        for unit in course.units:
            for topic in unit.topics:
                for lo in topic.learning_objectives:
                    if lo.code == lo_code:
                        return lo

        return None

    def search_learning_objectives(
        self,
        course_id: str,
        keywords: Optional[List[str]] = None,
        difficulty_level: Optional[int] = None,
        bloom_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for learning objectives with filters.

        Args:
            course_id: Course to search
            keywords: Keywords to match
            difficulty_level: Filter by difficulty
            bloom_level: Filter by Bloom's level

        Returns:
            List of matching LOs with context (unit, topic)
        """
        course = self.load_course(course_id)

        if not course:
            return []

        results = []

        for unit in course.units:
            for topic in unit.topics:
                for lo in topic.learning_objectives:
                    # Apply filters
                    if difficulty_level and lo.difficulty_level != difficulty_level:
                        continue

                    if bloom_level and lo.bloom_level != bloom_level:
                        continue

                    if keywords:
                        # Check if any keyword matches
                        lo_text = f"{lo.code} {lo.description} {' '.join(lo.keywords)}".lower()
                        if not any(kw.lower() in lo_text for kw in keywords):
                            continue

                    # Add with context
                    results.append({
                        "learning_objective": lo.model_dump(),
                        "topic_code": topic.code,
                        "topic_title": topic.title,
                        "unit_code": unit.code,
                        "unit_title": unit.title
                    })

        logger.info(f"Search returned {len(results)} learning objectives")
        return results

    def get_topic_los(self, course_id: str, topic_code: str) -> List[LearningObjective]:
        """Get all learning objectives for a topic"""
        topic = self.get_topic(course_id, topic_code)

        if not topic:
            return []

        return topic.learning_objectives

    def get_unit_los(self, course_id: str, unit_code: str) -> List[LearningObjective]:
        """Get all learning objectives for a unit"""
        unit = self.get_unit(course_id, unit_code)

        if not unit:
            return []

        all_los = []
        for topic in unit.topics:
            all_los.extend(topic.learning_objectives)

        return all_los

    def assign_difficulty_level(
        self,
        course_id: str,
        target_type: str,  # "topic" or "lo"
        target_code: str,
        difficulty_level: int
    ) -> bool:
        """
        Assign difficulty level to a topic or learning objective.

        Args:
            course_id: Course identifier
            target_type: "topic" or "lo"
            target_code: Topic code or LO code
            difficulty_level: Difficulty 1-5

        Returns:
            True if successful
        """
        try:
            course = self.load_course(course_id)

            if not course:
                return False

            modified = False

            for unit in course.units:
                for topic in unit.topics:
                    if target_type == "topic" and topic.code == target_code:
                        topic.difficulty_level = difficulty_level
                        modified = True
                        break

                    if target_type == "lo":
                        for lo in topic.learning_objectives:
                            if lo.code == target_code:
                                lo.difficulty_level = difficulty_level
                                modified = True
                                break

            if modified:
                self.save_course(course)
                logger.info(f"Assigned difficulty {difficulty_level} to {target_type} {target_code}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to assign difficulty: {e}")
            return False

    def get_course_statistics(self, course_id: str) -> Dict[str, Any]:
        """
        Get statistics about a course taxonomy.

        Returns:
            Dictionary with statistics
        """
        course = self.load_course(course_id)

        if not course:
            return {}

        total_los = 0
        total_topics = 0
        difficulty_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for unit in course.units:
            for topic in unit.topics:
                total_topics += 1
                total_los += len(topic.learning_objectives)

                for lo in topic.learning_objectives:
                    difficulty_distribution[lo.difficulty_level] = (
                        difficulty_distribution.get(lo.difficulty_level, 0) + 1
                    )

        return {
            "course_id": course.id,
            "course_title": course.title,
            "total_units": len(course.units),
            "total_topics": total_topics,
            "total_learning_objectives": total_los,
            "difficulty_distribution": difficulty_distribution,
            "avg_los_per_topic": total_los / total_topics if total_topics > 0 else 0,
            "version": course.version,
            "last_updated": course.updated_at
        }

    def list_courses(self) -> List[str]:
        """List all available course IDs"""
        course_files = self.data_dir.glob("*.json")
        return [f.stem for f in course_files]

    def export_flat_lo_list(self, course_id: str, output_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export flat list of all LOs with context for easy reference.

        Args:
            course_id: Course identifier
            output_file: Optional file to save JSON export

        Returns:
            List of LO dictionaries with context
        """
        course = self.load_course(course_id)

        if not course:
            return []

        flat_list = []

        for unit in course.units:
            for topic in unit.topics:
                for lo in topic.learning_objectives:
                    flat_list.append({
                        "course_id": course.id,
                        "course_title": course.title,
                        "unit_code": unit.code,
                        "unit_title": unit.title,
                        "topic_code": topic.code,
                        "topic_title": topic.title,
                        "lo_code": lo.code,
                        "lo_description": lo.description,
                        "difficulty_level": lo.difficulty_level,
                        "bloom_level": lo.bloom_level,
                        "skills": lo.skills,
                        "keywords": lo.keywords
                    })

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(flat_list, f, indent=2)
            logger.info(f"Exported {len(flat_list)} LOs to {output_file}")

        return flat_list

    def add_prerequisite(
        self,
        course_id: str,
        topic_code: str,
        prerequisite_code: str
    ) -> bool:
        """
        Add a prerequisite relationship to a topic.

        Args:
            course_id: Course identifier
            topic_code: Topic code to add prerequisite to
            prerequisite_code: Prerequisite topic/LO code

        Returns:
            True if successful
        """
        try:
            course = self.load_course(course_id)

            if not course:
                return False

            for unit in course.units:
                for topic in unit.topics:
                    if topic.code == topic_code:
                        if prerequisite_code not in topic.prerequisites:
                            topic.prerequisites.append(prerequisite_code)
                            self.save_course(course)
                            logger.info(f"Added prerequisite {prerequisite_code} to topic {topic_code}")
                            return True

            return False

        except Exception as e:
            logger.error(f"Failed to add prerequisite: {e}")
            return False

    def add_related_topic(
        self,
        course_id: str,
        topic_code: str,
        related_topic_code: str
    ) -> bool:
        """
        Add a related topic relationship.

        Args:
            course_id: Course identifier
            topic_code: Topic code
            related_topic_code: Related topic code

        Returns:
            True if successful
        """
        try:
            course = self.load_course(course_id)

            if not course:
                return False

            for unit in course.units:
                for topic in unit.topics:
                    if topic.code == topic_code:
                        if related_topic_code not in topic.related_topics:
                            topic.related_topics.append(related_topic_code)
                            self.save_course(course)
                            logger.info(f"Added related topic {related_topic_code} to topic {topic_code}")
                            return True

            return False

        except Exception as e:
            logger.error(f"Failed to add related topic: {e}")
            return False

    def get_topic_prerequisites(
        self,
        course_id: str,
        topic_code: str
    ) -> List[Topic]:
        """
        Get all prerequisite topics for a given topic.

        Args:
            course_id: Course identifier
            topic_code: Topic code

        Returns:
            List of prerequisite Topic objects
        """
        topic = self.get_topic(course_id, topic_code)

        if not topic or not topic.prerequisites:
            return []

        prerequisites = []
        for prereq_code in topic.prerequisites:
            prereq_topic = self.get_topic(course_id, prereq_code)
            if prereq_topic:
                prerequisites.append(prereq_topic)

        return prerequisites

    def get_related_topics(
        self,
        course_id: str,
        topic_code: str
    ) -> List[Topic]:
        """
        Get all related topics for a given topic.

        Args:
            course_id: Course identifier
            topic_code: Topic code

        Returns:
            List of related Topic objects
        """
        topic = self.get_topic(course_id, topic_code)

        if not topic or not topic.related_topics:
            return []

        related = []
        for related_code in topic.related_topics:
            related_topic = self.get_topic(course_id, related_code)
            if related_topic:
                related.append(related_topic)

        return related

    def get_relationship_graph(self, course_id: str) -> Dict[str, Any]:
        """
        Get the complete relationship graph for a course.

        Args:
            course_id: Course identifier

        Returns:
            Dictionary with nodes (topics) and edges (relationships)
        """
        course = self.load_course(course_id)

        if not course:
            return {"nodes": [], "edges": []}

        nodes = []
        edges = []

        for unit in course.units:
            for topic in unit.topics:
                nodes.append({
                    "code": topic.code,
                    "title": topic.title,
                    "unit_code": unit.code,
                    "difficulty_level": topic.difficulty_level
                })

                # Add prerequisite edges
                for prereq in topic.prerequisites:
                    edges.append({
                        "from": prereq,
                        "to": topic.code,
                        "type": "prerequisite"
                    })

                # Add related topic edges
                for related in topic.related_topics:
                    edges.append({
                        "from": topic.code,
                        "to": related,
                        "type": "related"
                    })

        return {
            "course_id": course_id,
            "nodes": nodes,
            "edges": edges
        }


# Example usage for creating AP Calculus BC taxonomy
def create_ap_calculus_bc_taxonomy(manager: TaxonomyManager, ced_path: str) -> Course:
    """Create AP Calculus BC course taxonomy from CED"""

    logger.info("Creating AP Calculus BC taxonomy...")

    course = manager.create_course_from_ced(
        course_id="ap_calculus_bc",
        ced_path=ced_path,
        title="AP Calculus BC"
    )

    logger.info(f"Created taxonomy with {len(course.units)} units")
    return course
