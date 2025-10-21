"""
Database utilities for template and variant storage.

Simple JSON-based storage for MVP. Can be replaced with proper DB later.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings
from ..core.exceptions import AprepError
from ..core.logger import setup_logger
from ..models.template import Template
from ..models.variant import Variant

logger = setup_logger(__name__)


class TemplateDatabase:
    """
    Template storage and retrieval.

    Uses JSON files for simplicity. Each template is stored as:
    {templates_path}/{course_id}/{template_id}.json
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize template database.

        Args:
            base_path: Base path for storage (default from settings)
        """
        self.base_path = base_path or settings.templates_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def save(self, template: Template) -> None:
        """
        Save template to storage.

        Args:
            template: Template to save
        """
        # Create course directory
        course_dir = self.base_path / template.course_id
        course_dir.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        file_path = course_dir / f"{template.template_id}.json"

        try:
            with open(file_path, "w") as f:
                json.dump(template.model_dump(), f, indent=2, default=str)

            self.logger.info(f"Saved template: {template.template_id}")

        except Exception as e:
            self.logger.error(f"Failed to save template {template.template_id}: {e}")
            raise AprepError(f"Template save failed: {e}") from e

    def load(self, template_id: str, course_id: Optional[str] = None) -> Template:
        """
        Load template from storage.

        Args:
            template_id: Template identifier
            course_id: Course identifier (if known)

        Returns:
            Template object

        Raises:
            AprepError: If template not found
        """
        # If course_id provided, check that path first
        if course_id:
            file_path = self.base_path / course_id / f"{template_id}.json"
            if file_path.exists():
                return self._load_from_file(file_path)

        # Otherwise search all courses
        for course_dir in self.base_path.iterdir():
            if not course_dir.is_dir():
                continue

            file_path = course_dir / f"{template_id}.json"
            if file_path.exists():
                return self._load_from_file(file_path)

        raise AprepError(f"Template not found: {template_id}")

    def _load_from_file(self, file_path: Path) -> Template:
        """Load template from JSON file."""
        try:
            with open(file_path) as f:
                data = json.load(f)
            return Template(**data)
        except Exception as e:
            raise AprepError(f"Failed to load template from {file_path}: {e}") from e

    def list_templates(self, course_id: Optional[str] = None) -> List[Template]:
        """
        List all templates (optionally filtered by course).

        Args:
            course_id: Optional course filter

        Returns:
            List of templates
        """
        templates = []

        if course_id:
            course_dir = self.base_path / course_id
            if course_dir.exists():
                for file_path in course_dir.glob("*.json"):
                    try:
                        templates.append(self._load_from_file(file_path))
                    except Exception as e:
                        self.logger.warning(f"Failed to load {file_path}: {e}")
        else:
            # Load from all courses
            for course_dir in self.base_path.iterdir():
                if not course_dir.is_dir():
                    continue

                for file_path in course_dir.glob("*.json"):
                    try:
                        templates.append(self._load_from_file(file_path))
                    except Exception as e:
                        self.logger.warning(f"Failed to load {file_path}: {e}")

        return templates

    def delete(self, template_id: str, course_id: Optional[str] = None) -> None:
        """
        Delete template from storage.

        Args:
            template_id: Template to delete
            course_id: Course identifier
        """
        if course_id:
            file_path = self.base_path / course_id / f"{template_id}.json"
            if file_path.exists():
                file_path.unlink()
                self.logger.info(f"Deleted template: {template_id}")
                return

        # Search all courses
        for course_dir in self.base_path.iterdir():
            if not course_dir.is_dir():
                continue

            file_path = course_dir / f"{template_id}.json"
            if file_path.exists():
                file_path.unlink()
                self.logger.info(f"Deleted template: {template_id}")
                return

        self.logger.warning(f"Template not found for deletion: {template_id}")


class VariantDatabase:
    """
    Variant storage and retrieval.

    Structure: {base_path}/{course_id}/{template_id}/{variant_id}.json
    """

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize variant database."""
        self.base_path = base_path or (settings.templates_path / "variants")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def save(self, variant: Variant) -> None:
        """Save variant to storage."""
        # Create nested directory structure
        if variant.course_id and variant.template_id:
            variant_dir = self.base_path / variant.course_id / variant.template_id
        elif variant.template_id:
            variant_dir = self.base_path / "unknown_course" / variant.template_id
        else:
            variant_dir = self.base_path / "unknown"

        variant_dir.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        file_path = variant_dir / f"{variant.id}.json"

        try:
            with open(file_path, "w") as f:
                json.dump(variant.model_dump(), f, indent=2, default=str)

            self.logger.debug(f"Saved variant: {variant.id}")

        except Exception as e:
            self.logger.error(f"Failed to save variant {variant.id}: {e}")
            raise AprepError(f"Variant save failed: {e}") from e

    def save_batch(self, variants: List[Variant]) -> None:
        """Save multiple variants."""
        for variant in variants:
            self.save(variant)

        self.logger.info(f"Saved {len(variants)} variants")

    def load(self, variant_id: str) -> Variant:
        """Load variant by ID."""
        # Search all directories
        for file_path in self.base_path.rglob(f"{variant_id}.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                return Variant(**data)
            except Exception as e:
                self.logger.warning(f"Failed to load {file_path}: {e}")

        raise AprepError(f"Variant not found: {variant_id}")

    def list_variants(
        self,
        template_id: Optional[str] = None,
        course_id: Optional[str] = None,
    ) -> List[Variant]:
        """
        List variants with optional filters.

        Args:
            template_id: Filter by template
            course_id: Filter by course

        Returns:
            List of variants
        """
        variants = []

        # Build search path
        if course_id and template_id:
            search_path = self.base_path / course_id / template_id
            pattern = "*.json"
        elif course_id:
            search_path = self.base_path / course_id
            pattern = "**/*.json"
        elif template_id:
            search_path = self.base_path
            pattern = f"**/{template_id}/*.json"
        else:
            search_path = self.base_path
            pattern = "**/*.json"

        if not search_path.exists():
            return []

        # Load variants
        for file_path in search_path.glob(pattern):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                variants.append(Variant(**data))
            except Exception as e:
                self.logger.warning(f"Failed to load {file_path}: {e}")

        return variants
