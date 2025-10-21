"""PostgreSQL database layer using SQLAlchemy.

This module provides database operations for PostgreSQL, replacing the JSON-based storage.
"""

import logging
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy import create_engine, select, and_, or_, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from ..core.config import get_settings
from ..core.logger import setup_logger
from ..core.exceptions import DatabaseError, AprepError
from ..models.db_models import (
    Base,
    Course,
    Unit,
    Topic,
    LearningObjective,
    Template,
    TemplateParameter,
    DistractorRule,
    Variant,
    VerificationLog,
    VariantStatistics,
    TemplateStatistics,
    Workflow,
    AgentTask,
)
from ..models.template import Template as TemplateModel
from ..models.variant import Variant as VariantModel


class PostgreSQLDatabase:
    """PostgreSQL database operations using SQLAlchemy."""

    def __init__(self, connection_string: Optional[str] = None):
        """Initialize PostgreSQL connection.

        Args:
            connection_string: PostgreSQL connection URL
                             Format: postgresql://user:password@host:port/database
                             If None, will use DATABASE_URL from settings
        """
        self.logger = setup_logger(__name__)
        self.settings = get_settings()

        # Connection string
        self.connection_string = connection_string or getattr(
            self.settings, "database_url", None
        )

        if not self.connection_string:
            raise DatabaseError(
                "No database connection string provided. "
                "Set DATABASE_URL in environment or pass connection_string"
            )

        # Create engine
        self.engine = create_engine(
            self.connection_string,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL logging
        )

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

        self.logger.info("PostgreSQL database connection initialized")

    def create_tables(self):
        """Create all tables in the database."""
        try:
            Base.metadata.create_all(bind=self.engine)
            self.logger.info("Database tables created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create tables: {e}")
            raise DatabaseError(f"Table creation failed: {str(e)}") from e

    def drop_tables(self):
        """Drop all tables (use with caution!)."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            self.logger.warning("All database tables dropped")
        except Exception as e:
            self.logger.error(f"Failed to drop tables: {e}")
            raise DatabaseError(f"Table drop failed: {str(e)}") from e

    @contextmanager
    def get_session(self):
        """Get database session context manager.

        Yields:
            Session: SQLAlchemy session

        Example:
            with db.get_session() as session:
                template = session.query(Template).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def close(self):
        """Close database connection."""
        self.engine.dispose()
        self.logger.info("Database connection closed")


class TemplateRepository:
    """Repository for Template operations."""

    def __init__(self, db: PostgreSQLDatabase):
        """Initialize repository.

        Args:
            db: PostgreSQL database instance
        """
        self.db = db
        self.logger = setup_logger(__name__)

    def save(self, template: TemplateModel) -> UUID:
        """Save template to database.

        Args:
            template: Template model (Pydantic)

        Returns:
            UUID of saved template
        """
        with self.db.get_session() as session:
            try:
                # Get or create course
                course = (
                    session.query(Course)
                    .filter(Course.course_id == template.course_id)
                    .first()
                )
                if not course:
                    course = Course(
                        course_id=template.course_id,
                        course_name=template.course_id.replace("_", " ").title(),
                    )
                    session.add(course)
                    session.flush()

                # Create template record
                db_template = Template(
                    template_id=template.template_id,
                    course_id=course.id,
                    created_by=template.created_by,
                    stem=template.stem,
                    solution_template=template.solution_template,
                    explanation_template=template.explanation_template,
                    difficulty_range=[template.difficulty_min, template.difficulty_max]
                    if hasattr(template, "difficulty_min")
                    else None,
                    calculator_policy=template.calculator_policy,
                    metadata={
                        "topic_id": template.topic_id,
                        "learning_objectives": template.learning_objectives,
                    },
                )
                session.add(db_template)
                session.flush()

                # Add parameters
                for param_name, param_def in template.params.items():
                    db_param = TemplateParameter(
                        template_id=db_template.id,
                        param_name=param_name,
                        param_type=param_def.get("type", "enum"),
                        definition=param_def,
                    )
                    session.add(db_param)

                # Add distractor rules
                for rule in template.distractor_rules:
                    db_rule = DistractorRule(
                        template_id=db_template.id,
                        rule_id=rule.get("rule_id", ""),
                        description=rule.get("description", ""),
                        generation_rule=rule.get("generation", ""),
                        misconception=rule.get("misconception", ""),
                    )
                    session.add(db_rule)

                # Initialize statistics
                stats = TemplateStatistics(
                    template_id=db_template.id, total_variants=0, verified_variants=0
                )
                session.add(stats)

                session.commit()

                self.logger.info(f"Template saved: {template.template_id}")
                return db_template.id

            except Exception as e:
                self.logger.error(f"Failed to save template: {e}")
                raise DatabaseError(f"Template save failed: {str(e)}") from e

    def load(self, template_id: str, course_id: Optional[str] = None) -> TemplateModel:
        """Load template from database.

        Args:
            template_id: Template ID
            course_id: Optional course ID filter

        Returns:
            Template model (Pydantic)
        """
        with self.db.get_session() as session:
            try:
                query = session.query(Template).filter(
                    Template.template_id == template_id
                )

                if course_id:
                    course = (
                        session.query(Course)
                        .filter(Course.course_id == course_id)
                        .first()
                    )
                    if course:
                        query = query.filter(Template.course_id == course.id)

                db_template = query.first()

                if not db_template:
                    raise DatabaseError(f"Template not found: {template_id}")

                # Convert to Pydantic model
                params = {
                    p.param_name: p.definition for p in db_template.parameters
                }

                distractor_rules = [
                    {
                        "rule_id": r.rule_id,
                        "description": r.description,
                        "generation": r.generation_rule,
                        "misconception": r.misconception,
                    }
                    for r in db_template.distractor_rules
                ]

                course_name = db_template.course.course_id if db_template.course else ""

                return TemplateModel(
                    template_id=db_template.template_id,
                    created_by=db_template.created_by,
                    course_id=course_name,
                    topic_id=db_template.metadata.get("topic_id", ""),
                    stem=db_template.stem,
                    params=params,
                    solution_template=db_template.solution_template or "",
                    explanation_template=db_template.explanation_template or "",
                    distractor_rules=distractor_rules,
                    calculator_policy=db_template.calculator_policy or "",
                    learning_objectives=db_template.metadata.get(
                        "learning_objectives", []
                    ),
                )

            except Exception as e:
                self.logger.error(f"Failed to load template: {e}")
                raise DatabaseError(f"Template load failed: {str(e)}") from e

    def list_templates(
        self,
        course_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        status: str = "active",
        limit: int = 100,
        offset: int = 0,
    ) -> List[TemplateModel]:
        """List templates with optional filters.

        Args:
            course_id: Optional course ID filter
            topic_id: Optional topic ID filter
            status: Template status ('active', 'deprecated', 'archived')
            limit: Max number of results
            offset: Offset for pagination

        Returns:
            List of Template models
        """
        with self.db.get_session() as session:
            try:
                query = session.query(Template).filter(Template.status == status)

                if course_id:
                    course = (
                        session.query(Course)
                        .filter(Course.course_id == course_id)
                        .first()
                    )
                    if course:
                        query = query.filter(Template.course_id == course.id)

                if topic_id:
                    query = query.filter(
                        Template.metadata["topic_id"].astext == topic_id
                    )

                db_templates = query.offset(offset).limit(limit).all()

                return [self._db_to_pydantic(t) for t in db_templates]

            except Exception as e:
                self.logger.error(f"Failed to list templates: {e}")
                raise DatabaseError(f"Template listing failed: {str(e)}") from e

    def _db_to_pydantic(self, db_template: Template) -> TemplateModel:
        """Convert database template to Pydantic model."""
        params = {p.param_name: p.definition for p in db_template.parameters}

        distractor_rules = [
            {
                "rule_id": r.rule_id,
                "description": r.description,
                "generation": r.generation_rule,
                "misconception": r.misconception,
            }
            for r in db_template.distractor_rules
        ]

        course_name = db_template.course.course_id if db_template.course else ""

        return TemplateModel(
            template_id=db_template.template_id,
            created_by=db_template.created_by,
            course_id=course_name,
            topic_id=db_template.metadata.get("topic_id", ""),
            stem=db_template.stem,
            params=params,
            solution_template=db_template.solution_template or "",
            explanation_template=db_template.explanation_template or "",
            distractor_rules=distractor_rules,
            calculator_policy=db_template.calculator_policy or "",
            learning_objectives=db_template.metadata.get("learning_objectives", []),
        )


class VariantRepository:
    """Repository for Variant operations."""

    def __init__(self, db: PostgreSQLDatabase):
        """Initialize repository.

        Args:
            db: PostgreSQL database instance
        """
        self.db = db
        self.logger = setup_logger(__name__)

    def save(self, variant: VariantModel) -> UUID:
        """Save variant to database.

        Args:
            variant: Variant model (Pydantic)

        Returns:
            UUID of saved variant
        """
        with self.db.get_session() as session:
            try:
                # Get template
                db_template = (
                    session.query(Template)
                    .filter(Template.template_id == variant.template_id)
                    .first()
                )

                if not db_template:
                    raise DatabaseError(
                        f"Template not found: {variant.template_id}"
                    )

                # Create variant record
                db_variant = Variant(
                    variant_id=variant.id,
                    template_id=db_template.id,
                    stimulus=variant.stimulus,
                    options=variant.options,
                    answer_index=variant.answer_index,
                    solution=variant.solution,
                    explanation=variant.explanation,
                    parameter_values=variant.parameter_values,
                    seed=variant.seed,
                )
                session.add(db_variant)
                session.flush()

                # Initialize statistics
                stats = VariantStatistics(
                    variant_id=db_variant.id, times_administered=0
                )
                session.add(stats)

                # Update template statistics
                db_template.statistics.total_variants += 1

                session.commit()

                self.logger.info(f"Variant saved: {variant.id}")
                return db_variant.id

            except Exception as e:
                self.logger.error(f"Failed to save variant: {e}")
                raise DatabaseError(f"Variant save failed: {str(e)}") from e

    def save_batch(self, variants: List[VariantModel]) -> List[UUID]:
        """Save multiple variants in batch.

        Args:
            variants: List of Variant models

        Returns:
            List of UUIDs of saved variants
        """
        uuids = []
        with self.db.get_session() as session:
            try:
                for variant in variants:
                    # Get template
                    db_template = (
                        session.query(Template)
                        .filter(Template.template_id == variant.template_id)
                        .first()
                    )

                    if not db_template:
                        self.logger.warning(
                            f"Template not found for variant: {variant.id}"
                        )
                        continue

                    # Create variant
                    db_variant = Variant(
                        variant_id=variant.id,
                        template_id=db_template.id,
                        stimulus=variant.stimulus,
                        options=variant.options,
                        answer_index=variant.answer_index,
                        solution=variant.solution,
                        explanation=variant.explanation,
                        parameter_values=variant.parameter_values,
                        seed=variant.seed,
                    )
                    session.add(db_variant)
                    session.flush()

                    uuids.append(db_variant.id)

                    # Initialize statistics
                    stats = VariantStatistics(
                        variant_id=db_variant.id, times_administered=0
                    )
                    session.add(stats)

                    # Update template statistics
                    if db_template.statistics:
                        db_template.statistics.total_variants += 1

                session.commit()

                self.logger.info(f"Saved {len(uuids)} variants in batch")
                return uuids

            except Exception as e:
                self.logger.error(f"Batch save failed: {e}")
                raise DatabaseError(f"Batch save failed: {str(e)}") from e

    def list_variants(
        self,
        template_id: Optional[str] = None,
        course_id: Optional[str] = None,
        verification_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List variants with optional filters.

        Args:
            template_id: Optional template ID filter
            course_id: Optional course ID filter
            verification_status: Optional verification status filter
            limit: Max number of results
            offset: Offset for pagination

        Returns:
            List of variant dictionaries
        """
        with self.db.get_session() as session:
            try:
                query = session.query(Variant)

                if template_id:
                    db_template = (
                        session.query(Template)
                        .filter(Template.template_id == template_id)
                        .first()
                    )
                    if db_template:
                        query = query.filter(Variant.template_id == db_template.id)

                if course_id:
                    course = (
                        session.query(Course)
                        .filter(Course.course_id == course_id)
                        .first()
                    )
                    if course:
                        query = query.join(Template).filter(
                            Template.course_id == course.id
                        )

                if verification_status:
                    query = query.filter(
                        Variant.verification_status == verification_status
                    )

                db_variants = query.offset(offset).limit(limit).all()

                return [self._db_to_dict(v) for v in db_variants]

            except Exception as e:
                self.logger.error(f"Failed to list variants: {e}")
                raise DatabaseError(f"Variant listing failed: {str(e)}") from e

    def _db_to_dict(self, db_variant: Variant) -> Dict[str, Any]:
        """Convert database variant to dictionary."""
        return {
            "id": db_variant.variant_id,
            "template_id": db_variant.template.template_id,
            "stimulus": db_variant.stimulus,
            "options": db_variant.options,
            "answer_index": db_variant.answer_index,
            "solution": db_variant.solution,
            "explanation": db_variant.explanation,
            "parameter_values": db_variant.parameter_values,
            "seed": db_variant.seed,
            "verification_status": db_variant.verification_status,
            "created_at": db_variant.created_at.isoformat()
            if db_variant.created_at
            else None,
        }


class VerificationRepository:
    """Repository for Verification operations."""

    def __init__(self, db: PostgreSQLDatabase):
        """Initialize repository.

        Args:
            db: PostgreSQL database instance
        """
        self.db = db
        self.logger = setup_logger(__name__)

    def save_verification_log(
        self, variant_id: str, verification_result: Dict[str, Any]
    ) -> UUID:
        """Save verification log to database.

        Args:
            variant_id: Variant ID
            verification_result: Verification result from SolutionVerifier

        Returns:
            UUID of saved log
        """
        with self.db.get_session() as session:
            try:
                # Get variant
                db_variant = (
                    session.query(Variant)
                    .filter(Variant.variant_id == variant_id)
                    .first()
                )

                if not db_variant:
                    raise DatabaseError(f"Variant not found: {variant_id}")

                # Create log
                log = VerificationLog(
                    variant_id=db_variant.id,
                    verification_status=verification_result["verification_status"],
                    symbolic_result=verification_result["methods_used"].get(
                        "symbolic"
                    ),
                    numerical_result=verification_result["methods_used"].get(
                        "numerical"
                    ),
                    claude_result=verification_result["methods_used"].get(
                        "claude_reasoning"
                    ),
                    consensus=verification_result["consensus"],
                    distractor_analysis=verification_result.get(
                        "distractor_analysis"
                    ),
                    issues=verification_result.get("issues"),
                    warnings=verification_result.get("warnings"),
                    duration_ms=verification_result["performance"]["duration_ms"],
                    cost_usd=verification_result["performance"]["cost_usd"],
                )
                session.add(log)

                # Update variant
                db_variant.verification_status = verification_result[
                    "verification_status"
                ]
                db_variant.verification_confidence = verification_result["consensus"][
                    "confidence"
                ]
                db_variant.verification_timestamp = datetime.utcnow()
                db_variant.verification_result = verification_result

                # Update template statistics if variant passed
                if verification_result["verification_status"] == "PASS":
                    template = db_variant.template
                    if template and template.statistics:
                        template.statistics.verified_variants += 1

                session.commit()

                self.logger.info(f"Verification log saved for variant: {variant_id}")
                return log.id

            except Exception as e:
                self.logger.error(f"Failed to save verification log: {e}")
                raise DatabaseError(f"Verification log save failed: {str(e)}") from e
