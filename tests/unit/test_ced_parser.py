"""Unit tests for CED Parser agent."""

import pytest
from pathlib import Path
from src.agents.ced_parser import CEDParser
from src.core.exceptions import CEDParseError


class TestCEDParser:
    """Test suite for CED Parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return CEDParser()

    @pytest.fixture
    def sample_ced_info(self):
        """Sample CED info for testing."""
        return {
            "course_id": "ap_calculus_bc",
            "course_name": "AP Calculus BC",
            "ced_document": {
                "local_path": "data/ced/sample_ced.pdf",
                "version": "2024-2025",
            },
            "parsing_config": {
                "extract_learning_objectives": True,
                "extract_skills": True,
            },
        }

    def test_parser_initialization(self, parser):
        """Test parser can be initialized."""
        assert parser is not None
        assert parser.ced_schema_version == "1.0"

    def test_identify_document_structure(self, parser):
        """Test document structure identification."""
        sample_pages = [
            {
                "page_number": 1,
                "text": "Unit 1: Limits and Continuity\nSome content here",
                "tables": [],
            },
            {
                "page_number": 2,
                "text": "Unit 2: Differentiation\nMore content",
                "tables": [],
            },
        ]

        structure = parser._identify_document_structure(sample_pages)

        assert "units" in structure
        assert len(structure["units"]) == 2
        assert structure["units"][0]["unit_number"] == 1
        assert "Limits and Continuity" in structure["units"][0]["name"]

    def test_extract_learning_objectives(self, parser):
        """Test learning objective extraction."""
        sample_pages = [
            {
                "page_number": 1,
                "text": """
                LIM-1.A: Calculate limits of functions
                LIM-1.A.1: A limit can be expressed using notation

                LIM-1.B: Represent limits analytically
                """,
                "tables": [],
            }
        ]

        los = parser._extract_learning_objectives(sample_pages, "u1")

        assert len(los) >= 1
        assert any(lo["lo_id"] == "LIM-1.A" for lo in los)

    def test_extract_formula_sheet(self, parser):
        """Test formula sheet extraction."""
        sample_pages = [
            {
                "page_number": 1,
                "text": """
                Formula Sheet
                d/dx[x^n] = nx^(n-1)
                d/dx[sin x] = cos x
                ∫x^n dx = x^(n+1)/(n+1) + C
                """,
                "tables": [],
            }
        ]

        structure = {"formula_sheet": {"page": 1}}
        formulas = parser._extract_formula_sheet(sample_pages, structure)

        assert formulas is not None
        assert "derivatives" in formulas
        assert len(formulas["derivatives"]) > 0

    def test_validation_with_valid_data(self, parser):
        """Test validation with valid parsed data."""
        parsed_data = {
            "ced_id": "ap_calc_bc_2024",
            "course_id": "ap_calculus_bc",
            "units": [{"unit_id": "u1", "name": "Limits"}],
            "metadata": {"total_units": 1},
        }

        validation = parser._validate_parsed_ced(parsed_data)

        assert validation["schema_validation"] == "passed"
        assert len(validation["issues"]) == 0

    def test_validation_with_missing_fields(self, parser):
        """Test validation catches missing required fields."""
        parsed_data = {
            "course_id": "ap_calculus_bc",
            # Missing: ced_id, units, metadata
        }

        validation = parser._validate_parsed_ced(parsed_data)

        assert validation["schema_validation"] == "failed"
        assert len(validation["issues"]) > 0

    def test_parse_ced_missing_file(self, parser, sample_ced_info):
        """Test parsing fails gracefully with missing file."""
        sample_ced_info["ced_document"]["local_path"] = "nonexistent.pdf"

        with pytest.raises(CEDParseError):
            parser.parse_ced(sample_ced_info)

    def test_extract_unit_structure(self, parser):
        """Test unit extraction."""
        unit_info = {"unit_number": 1, "name": "Limits", "start_page": 5}

        unit = parser._extract_unit([], unit_info)

        assert unit["unit_id"] == "u1"
        assert unit["unit_number"] == 1
        assert unit["name"] == "Limits"
        assert "topics" in unit

    def test_extract_essential_knowledge(self, parser):
        """Test essential knowledge extraction (HIGH PRIORITY feature)."""
        text = """
        LIM-1.A: Calculate limits of functions
        LIM-1.A.1: A limit can be expressed symbolically using notation such as lim[x→a] f(x) = L
        LIM-1.A.2: When the limit of f(x) as x approaches a from the left is equal to the limit as x approaches a from the right
        """

        ek_items = parser._extract_essential_knowledge(text, "LIM-1.A")

        assert len(ek_items) == 2
        assert "LIM-1.A.1:" in ek_items[0]
        assert "notation" in ek_items[0]
        assert "LIM-1.A.2:" in ek_items[1]

    def test_identify_skills_practiced(self, parser):
        """Test skills identification (HIGH PRIORITY feature)."""
        text = """
        LIM-1.A: Calculate limits of functions
        This learning objective practices MP1 and MP2 skills.
        Students will use MP1 to implement procedures.
        """

        skills = parser._identify_skills_practiced(text, "LIM-1.A")

        assert "MP1" in skills
        assert "MP2" in skills
        assert len(skills) == 2

    def test_identify_skills_no_matches(self, parser):
        """Test skills identification when no skills found."""
        text = "LIM-1.A: Calculate limits with no skill references"

        skills = parser._identify_skills_practiced(text, "LIM-1.A")

        assert skills == []

    def test_determine_calculator_policy_no_calc(self, parser):
        """Test calculator policy detection - No Calculator (HIGH PRIORITY feature)."""
        text = """
        LIM-1.A: Calculate limits of functions
        This topic is assessed without calculator.
        No calculator for this section.
        """

        policy = parser._determine_calculator_policy(text, "LIM-1.A")

        assert policy == "No-Calc"

    def test_determine_calculator_policy_calc_allowed(self, parser):
        """Test calculator policy detection - Calculator Allowed."""
        text = """
        CHA-2.A: Calculate average rates of change
        Students may use a graphing calculator for this problem.
        Calculator allowed.
        """

        policy = parser._determine_calculator_policy(text, "CHA-2.A")

        assert policy == "Calc"

    def test_determine_calculator_policy_both(self, parser):
        """Test calculator policy detection - Both contexts."""
        text = """
        FUN-3.A: Determine derivatives
        No calculator for part A, calculator allowed for part B.
        """

        policy = parser._determine_calculator_policy(text, "FUN-3.A")

        assert policy == "No-Calc/Calc"

    def test_learning_objectives_with_all_features(self, parser):
        """Test LO extraction includes all new HIGH PRIORITY features."""
        sample_pages = [
            {
                "page_number": 1,
                "text": """
                LIM-1.A: Calculate limits of functions
                LIM-1.A.1: A limit can be expressed using notation
                LIM-1.A.2: Limits describe behavior as x approaches a value
                This learning objective practices MP1 and MP2.
                No calculator for this section.
                """,
                "tables": [],
            }
        ]

        los = parser._extract_learning_objectives(sample_pages, "u1")

        assert len(los) >= 1
        lo = next((lo for lo in los if lo["lo_id"] == "LIM-1.A"), None)

        assert lo is not None
        # Check essential knowledge
        assert len(lo["essential_knowledge"]) == 2
        assert "LIM-1.A.1:" in lo["essential_knowledge"][0]
        # Check skills
        assert "MP1" in lo["skills_practiced"]
        assert "MP2" in lo["skills_practiced"]
        # Check calculator policy
        assert lo["calculator_policy"] == "No-Calc"
