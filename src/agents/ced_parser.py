"""
CED Parser Agent - Parse AP Course and Exam Description documents.

This agent extracts and structures learning objectives, skills, topics,
and assessment specifications from College Board CED PDFs.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

from ..core.config import settings
from ..core.exceptions import CEDParseError
from ..core.logger import setup_logger

logger = setup_logger(__name__)


class CEDParser:
    """
    Parse AP Course and Exam Description (CED) documents.

    Extracts structured data from CED PDFs including:
    - Learning objectives
    - Skills and enduring understandings
    - Unit and topic structure
    - Exam format and timing
    - Formula sheets and sample questions
    """

    def __init__(self):
        """Initialize CED Parser."""
        self.logger = logger
        self.ced_schema_version = "1.0"

    def parse_ced(self, ced_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for CED parsing.

        Args:
            ced_info: Dictionary containing:
                - course_id: str
                - course_name: str
                - ced_document: dict with 'url' or 'local_path'
                - parsing_config: dict with extraction flags

        Returns:
            Structured CED data as dictionary

        Raises:
            CEDParseError: If parsing fails
        """
        self.logger.info(f"Starting CED parse for {ced_info.get('course_id')}")

        try:
            # Phase 1: Load document
            doc = self._load_ced_document(ced_info["ced_document"])
            self.logger.info(f"Loaded {len(doc['pages'])} pages")

            # Phase 2: Identify structure
            structure = self._identify_document_structure(doc["pages"])
            self.logger.info(f"Identified {len(structure['units'])} units")

            # Phase 3: Extract units
            units = []
            for unit_info in structure["units"]:
                unit = self._extract_unit(doc["pages"], unit_info)
                units.append(unit)

            # Phase 4: Extract appendices
            formula_sheet = self._extract_formula_sheet(doc["pages"], structure)

            # Phase 5: Assemble parsed data
            parsed_data = {
                "ced_id": f"{ced_info['course_id']}_{ced_info['ced_document'].get('version', '2024_2025')}",
                "course_id": ced_info["course_id"],
                "course_name": ced_info["course_name"],
                "version": ced_info["ced_document"].get("version", "2024-2025"),
                "parsed_at": datetime.now().isoformat(),
                "schema_version": self.ced_schema_version,
                "units": units,
                "appendices": {"formula_sheet": formula_sheet},
                "metadata": {
                    "total_units": len(units),
                    "total_pages": len(doc["pages"]),
                    "parsing_duration_sec": 0,  # TODO: Track actual duration
                    "extraction_confidence": 0.95,  # TODO: Calculate actual confidence
                },
            }

            # Phase 6: Validate
            validation = self._validate_parsed_ced(parsed_data)
            if not validation["schema_validation"] == "passed":
                raise CEDParseError(f"Validation failed: {validation}")

            self.logger.info("CED parsing completed successfully")
            return parsed_data

        except Exception as e:
            self.logger.error(f"CED parsing failed: {e}")
            raise CEDParseError(f"Failed to parse CED: {e}") from e

    def _load_ced_document(self, ced_document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load CED PDF and extract pages.

        Args:
            ced_document: Dict with 'url' or 'local_path'

        Returns:
            Dictionary with file_path and pages

        Raises:
            CEDParseError: If file cannot be loaded
        """
        # Get file path
        if "local_path" in ced_document:
            pdf_path = Path(ced_document["local_path"])
        elif "url" in ced_document:
            # TODO: Implement URL download
            raise CEDParseError("URL download not yet implemented")
        else:
            raise CEDParseError("No CED document source provided")

        if not pdf_path.exists():
            raise CEDParseError(f"CED file not found: {pdf_path}")

        # Extract text and tables using pdfplumber
        pages = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []

                    pages.append({
                        "page_number": page_num,
                        "text": text,
                        "tables": tables,
                        "width": page.width,
                        "height": page.height,
                    })
        except Exception as e:
            raise CEDParseError(f"Failed to read PDF: {e}") from e

        return {
            "file_path": str(pdf_path),
            "pages": pages,
            "total_pages": len(pages),
        }

    def _identify_document_structure(self, pages: List[Dict]) -> Dict[str, Any]:
        """
        Identify CED document structure (units, appendices, etc.).

        Args:
            pages: List of page dictionaries

        Returns:
            Structure dictionary with unit boundaries
        """
        structure = {
            "table_of_contents": None,
            "units": [],
            "appendices": [],
            "formula_sheet": None,
        }

        # Identify unit boundaries
        unit_pattern = r"Unit\s+(\d+)[:\s]+(.+?)(?:\n|$)"

        for page_num, page in enumerate(pages, start=1):
            text = page["text"]

            # Find units
            for match in re.finditer(unit_pattern, text, re.IGNORECASE):
                unit_number = int(match.group(1))
                unit_name = match.group(2).strip()

                structure["units"].append({
                    "unit_number": unit_number,
                    "name": unit_name,
                    "start_page": page_num,
                })

        # Find formula sheet
        for page_num, page in enumerate(pages, start=1):
            if "formula" in page["text"].lower() and "sheet" in page["text"].lower():
                structure["formula_sheet"] = {"page": page_num}
                break

        return structure

    def _extract_unit(self, pages: List[Dict], unit_info: Dict) -> Dict[str, Any]:
        """
        Extract learning objectives and topics from a unit.

        Args:
            pages: All pages
            unit_info: Unit metadata with start_page

        Returns:
            Unit dictionary with topics and learning objectives
        """
        # TODO: Implement full unit extraction
        # For now, return minimal structure
        return {
            "unit_id": f"u{unit_info['unit_number']}",
            "unit_number": unit_info["unit_number"],
            "name": unit_info["name"],
            "topics": [],  # Will be populated in full implementation
        }

    def _extract_learning_objectives(
        self, unit_pages: List[Dict], unit_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extract learning objectives from unit content.

        Args:
            unit_pages: Pages for this unit
            unit_id: Unit identifier

        Returns:
            List of learning objective dictionaries
        """
        learning_objectives = []
        lo_pattern = r"([A-Z]{3}-\d+\.[A-Z])"

        for page in unit_pages:
            text = page["text"]
            lo_ids = re.findall(lo_pattern, text)

            for lo_id in lo_ids:
                # Extract description (simplified)
                desc_match = re.search(
                    rf"{lo_id}\s*[:]\s*(.+?)(?=\n{lo_pattern}|\n\n|$)",
                    text,
                    re.DOTALL,
                )

                if desc_match:
                    description = desc_match.group(1).strip()

                    # HIGH PRIORITY: Extract essential knowledge
                    essential_knowledge = self._extract_essential_knowledge(text, lo_id)

                    # HIGH PRIORITY: Identify skills practiced
                    skills = self._identify_skills_practiced(text, lo_id)

                    # HIGH PRIORITY: Determine calculator policy
                    calculator = self._determine_calculator_policy(text, lo_id)

                    learning_objectives.append({
                        "lo_id": lo_id,
                        "description": description,
                        "enduring_understanding": lo_id.split(".")[0],
                        "essential_knowledge": essential_knowledge,
                        "skills_practiced": skills,
                        "calculator_policy": calculator,
                    })

        return learning_objectives

    def _extract_essential_knowledge(self, text: str, lo_id: str) -> List[str]:
        """
        Extract essential knowledge bullets for a learning objective.

        Essential knowledge IDs are typically LO_ID.1, LO_ID.2, etc.
        Example: LIM-1.A.1, LIM-1.A.2

        Args:
            text: Page text containing the LO
            lo_id: Learning objective ID (e.g., "LIM-1.A")

        Returns:
            List of essential knowledge strings
        """
        essential_knowledge = []

        # EK pattern: LO_ID.number followed by colon and description
        ek_pattern = rf"{re.escape(lo_id)}\.(\d+)\s*[:]\s*(.+?)(?={re.escape(lo_id)}\.\d+|\n\n|{re.escape(lo_id)[:-2]}\.[A-Z]|$)"

        matches = re.finditer(ek_pattern, text, re.DOTALL)

        for match in matches:
            ek_number = match.group(1)
            ek_text = match.group(2).strip()

            # Clean up the text (remove extra whitespace, newlines)
            ek_text = " ".join(ek_text.split())

            essential_knowledge.append(f"{lo_id}.{ek_number}: {ek_text}")

        return essential_knowledge

    def _identify_skills_practiced(self, text: str, lo_id: str) -> List[str]:
        """
        Identify which mathematical practices (skills) are practiced for this LO.

        Looks for MP1, MP2, MP3, MP4 references near the learning objective.

        Args:
            text: Page text containing the LO
            lo_id: Learning objective ID

        Returns:
            List of skill IDs (e.g., ["MP1", "MP2"])
        """
        # Find LO position in text
        lo_position = text.find(lo_id)
        if lo_position == -1:
            return []

        # Get text window around LO (±500 characters for context)
        window_start = max(0, lo_position - 500)
        window_end = min(len(text), lo_position + 500)
        window_text = text[window_start:window_end]

        # Find MP references (MP1, MP2, MP3, MP4)
        mp_pattern = r"MP(\d+)"
        mp_matches = re.findall(mp_pattern, window_text)

        # Return unique, sorted skill IDs
        skills = sorted(set(f"MP{mp}" for mp in mp_matches))

        return skills

    def _determine_calculator_policy(self, text: str, lo_id: str) -> str:
        """
        Determine calculator policy for a learning objective.

        Looks for keywords like "calculator", "no calculator", "graphing calculator"
        near the LO.

        Args:
            text: Page text containing the LO
            lo_id: Learning objective ID

        Returns:
            Calculator policy: "No-Calc", "Calc", or "No-Calc/Calc"
        """
        # Find LO position
        lo_position = text.find(lo_id)
        if lo_position == -1:
            return "No-Calc"  # Default

        # Get text window around LO
        window_start = max(0, lo_position - 300)
        window_end = min(len(text), lo_position + 300)
        window_text = text[window_start:window_end].lower()

        # Check for calculator keywords
        has_no_calc = any(phrase in window_text for phrase in [
            "no calculator", "without calculator", "no-calc"
        ])

        has_calc = any(phrase in window_text for phrase in [
            "calculator allowed", "with calculator", "graphing calculator"
        ])

        # Determine policy
        if has_no_calc and has_calc:
            return "No-Calc/Calc"
        elif has_calc:
            return "Calc"
        elif has_no_calc:
            return "No-Calc"
        else:
            return "No-Calc"  # Default to no calculator

    def _extract_formula_sheet(
        self, pages: List[Dict], structure: Dict
    ) -> Optional[Dict[str, List[str]]]:
        """
        Extract formulas from formula sheet appendix.

        Args:
            pages: All pages
            structure: Document structure with formula_sheet page

        Returns:
            Dictionary of formula categories or None
        """
        if not structure.get("formula_sheet"):
            return None

        page_num = structure["formula_sheet"]["page"]
        if page_num > len(pages):
            return None

        page = pages[page_num - 1]
        text = page["text"]

        # Simple extraction (TODO: Improve)
        formulas = {
            "derivatives": [],
            "integrals": [],
            "series": [],
            "other": [],
        }

        # Extract lines that look like formulas
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Categorize by keywords
            if "d/dx" in line.lower() or "derivative" in line.lower():
                formulas["derivatives"].append(line)
            elif "∫" in line or "integral" in line.lower():
                formulas["integrals"].append(line)
            elif "series" in line.lower() or "∑" in line:
                formulas["series"].append(line)
            elif any(c in line for c in ["=", "+", "-", "*", "/"]):
                formulas["other"].append(line)

        return formulas

    def _validate_parsed_ced(self, parsed_data: Dict) -> Dict[str, Any]:
        """
        Validate parsed CED data structure.

        Args:
            parsed_data: Parsed CED dictionary

        Returns:
            Validation results
        """
        validation = {
            "schema_validation": "pending",
            "completeness_check": "pending",
            "issues": [],
        }

        # Check required fields
        required_fields = ["ced_id", "course_id", "units", "metadata"]
        for field in required_fields:
            if field not in parsed_data:
                validation["issues"].append({
                    "type": "missing_field",
                    "field": field,
                })

        # Check units
        if not parsed_data.get("units"):
            validation["issues"].append({
                "type": "no_units",
                "message": "No units found in parsed data",
            })

        # Set validation status
        if not validation["issues"]:
            validation["schema_validation"] = "passed"
            validation["completeness_check"] = "passed"
        else:
            validation["schema_validation"] = "failed"

        return validation
