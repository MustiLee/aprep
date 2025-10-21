"""Integration tests for full workflow."""

import pytest
from pathlib import Path
from src.agents.template_crafter import TemplateCrafter
from src.agents.parametric_generator import ParametricGenerator
from src.agents.solution_verifier import SolutionVerifier
from src.utils.database import TemplateDatabase, VariantDatabase
from src.models.template import Template


class TestFullWorkflow:
    """Test complete content generation workflow."""

    @pytest.fixture
    def template_db(self, tmp_path):
        """Create temporary template database."""
        return TemplateDatabase(base_path=tmp_path / "templates")

    @pytest.fixture
    def variant_db(self, tmp_path):
        """Create temporary variant database."""
        return VariantDatabase(base_path=tmp_path / "variants")

    @pytest.fixture
    def sample_template_input(self):
        """Sample input for template creation."""
        return {
            "task_id": "test_template_001",
            "course_id": "ap_calculus_bc",
            "unit_id": "u2_differentiation",
            "topic_id": "t3_chain_rule",
            "learning_objectives": [
                "Apply chain rule to composite functions",
            ],
            "difficulty_target": [0.4, 0.7],
            "calculator_policy": "No-Calc",
            "misconceptions": [
                "Omitting inner derivative",
                "Wrong trig derivative",
            ],
        }

    def test_template_creation_and_storage(
        self, template_db, sample_template_input
    ):
        """Test template creation and database storage."""
        # Create template
        crafter = TemplateCrafter()
        template_dict = crafter.create_template(sample_template_input)

        # Convert to model
        template = Template(**template_dict)

        # Save to database
        template_db.save(template)

        # Load from database
        loaded = template_db.load(
            template.template_id,
            course_id=template.course_id,
        )

        assert loaded.template_id == template.template_id
        assert loaded.course_id == template.course_id
        assert loaded.stem == template.stem

    def test_variant_generation_and_storage(self, template_db, variant_db):
        """Test variant generation and storage."""
        # Create simple template manually
        template = Template(
            template_id="test_template_v1",
            created_by="test",
            course_id="ap_calculus_bc",
            topic_id="test_topic",
            stem="What is {{a}} + {{b}}?",
            params={
                "a": {
                    "type": "enum",
                    "values": [1, 2, 3],
                },
                "b": {
                    "type": "enum",
                    "values": [4, 5, 6],
                },
            },
            solution_template="{{a}} + {{b}}",
            distractor_rules=[
                {
                    "rule_id": "wrong_add",
                    "description": "Wrong addition",
                    "generation": "{{a}} + {{b}} + 1",
                },
                {
                    "rule_id": "multiply",
                    "description": "Multiply instead",
                    "generation": "{{a}} * {{b}}",
                },
                {
                    "rule_id": "subtract",
                    "description": "Subtract instead",
                    "generation": "{{a}} - {{b}}",
                },
            ],
        )

        # Save template
        template_db.save(template)

        # Generate variants
        generator = ParametricGenerator()
        variants = generator.generate_batch(
            template.model_dump(),
            count=5,
            seed_start=0,
        )

        assert len(variants) == 5

        # Save variants
        variant_db.save_batch([v for v in variants])

        # Load variants
        loaded_variants = variant_db.list_variants(
            template_id=template.template_id,
            course_id=template.course_id,
        )

        assert len(loaded_variants) == 5

    def test_end_to_end_workflow(
        self, template_db, variant_db, sample_template_input
    ):
        """Test complete workflow from template to variants."""
        # Step 1: Create template
        crafter = TemplateCrafter()
        template_dict = crafter.create_template(sample_template_input)
        template = Template(**template_dict)
        template_db.save(template)

        # Step 2: Generate variants
        generator = ParametricGenerator()
        variants = generator.generate_batch(
            template.model_dump(),
            count=10,
            seed_start=42,
        )

        # Should generate most (allow some failures)
        assert len(variants) >= 8

        # Step 3: Store variants
        variant_db.save_batch(variants)

        # Step 4: Verify storage
        stored_variants = variant_db.list_variants(
            template_id=template.template_id
        )

        assert len(stored_variants) == len(variants)

        # Step 5: Validate variant properties
        for variant in variants:
            assert len(variant["options"]) == 4
            assert 0 <= variant["answer_index"] < 4
            assert variant["stimulus"]
            assert variant["solution"]

    def test_template_listing(self, template_db):
        """Test listing templates from database."""
        # Create multiple templates
        for i in range(3):
            template = Template(
                template_id=f"test_template_v{i}",
                created_by="test",
                course_id="ap_calculus_bc",
                topic_id=f"topic_{i}",
                stem="Test question {{x}}",
                params={"x": {"type": "enum", "values": [1, 2, 3]}},
            )
            template_db.save(template)

        # List all templates
        templates = template_db.list_templates()
        assert len(templates) == 3

        # List by course
        course_templates = template_db.list_templates(
            course_id="ap_calculus_bc"
        )
        assert len(course_templates) == 3

    def test_variant_uniqueness(self, variant_db):
        """Test that variants are unique."""
        # Create template with limited parameter space
        template = Template(
            template_id="small_space_template",
            created_by="test",
            course_id="ap_test",
            topic_id="test",
            stem="What is {{a}}?",
            params={
                "a": {
                    "type": "enum",
                    "values": [1, 2],  # Only 2 values
                }
            },
            solution_template="{{a}}",
            distractor_rules=[
                {"rule_id": "add1", "description": "Add 1", "generation": "{{a}} + 1"},
                {"rule_id": "add2", "description": "Add 2", "generation": "{{a}} + 2"},
                {"rule_id": "add3", "description": "Add 3", "generation": "{{a}} + 3"},
            ],
        )

        # Generate variants
        generator = ParametricGenerator()
        variants = generator.generate_batch(
            template.model_dump(),
            count=5,
            seed_start=0,
        )

        # Check uniqueness
        stems = [v["stimulus"] for v in variants]
        unique_stems = set(stems)

        # Should have unique stems
        assert len(unique_stems) >= 2  # At least 2 unique (from 2 param values)

    def test_workflow_with_verification(
        self, template_db, variant_db, sample_template_input
    ):
        """Test complete workflow including solution verification."""
        # Step 1: Create template
        crafter = TemplateCrafter()
        template_dict = crafter.create_template(sample_template_input)
        template = Template(**template_dict)
        template_db.save(template)

        # Step 2: Generate variants
        generator = ParametricGenerator()
        variants = generator.generate_batch(
            template.model_dump(), count=5, seed_start=42
        )

        assert len(variants) >= 3  # Allow some failures

        # Step 3: Verify variants
        verifier = SolutionVerifier()
        verification_results = []

        for variant in variants:
            result = verifier.verify_variant(variant)
            verification_results.append(result)

        # Step 4: Check verification results
        passed = [
            r for r in verification_results if r["verification_status"] == "PASS"
        ]
        failed = [
            r for r in verification_results if r["verification_status"] == "FAIL"
        ]

        # Most should pass (parametric generator should produce correct variants)
        assert len(passed) >= len(failed)

        # All passed variants should have high confidence
        for result in passed:
            assert result["consensus"]["confidence"] >= 0.8

        # Step 5: Store only verified variants
        verified_variants = [
            v
            for i, v in enumerate(variants)
            if verification_results[i]["verification_status"] == "PASS"
        ]
        variant_db.save_batch(verified_variants)

        # Verify storage
        stored = variant_db.list_variants(template_id=template.template_id)
        assert len(stored) == len(verified_variants)
