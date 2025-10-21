# Aprep AI Agent System

AP exam content generation system powered by AI agents.

## Overview

Aprep is a multi-agent system designed to generate high-quality AP exam questions aligned with College Board Course and Exam Descriptions (CEDs). The system uses specialized AI agents to handle different aspects of content generation, validation, and quality control.

## Architecture

### Core Agents (P0 - MVP Critical)

1. **CED Parser** - Parses Course and Exam Description documents
2. **Template Crafter** - Creates parametric question templates
3. **Parametric Generator** - Generates question variants
4. **Solution Verifier** - Validates mathematical correctness
5. **Master Orchestrator** - Coordinates agent workflows

## Getting Started

### Prerequisites

- Python 3.10+
- Anthropic API key

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run tests:
   ```bash
   pytest tests/
   ```

## Project Structure

```
backend/
├── src/
│   ├── agents/          # Agent implementations
│   ├── api/             # FastAPI endpoints
│   ├── core/            # Shared utilities
│   ├── models/          # Data models
│   └── utils/           # Helper functions
├── config/              # Configuration files
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
├── data/               # Data storage
│   ├── ced/           # CED documents
│   ├── templates/     # Question templates
│   └── misconceptions/# Misconception database
└── .claude/           # Agent specifications (markdown)
```

## Usage

### CED Parser Example

```python
from src.agents.ced_parser import CEDParser

parser = CEDParser()
parsed_data = parser.parse_ced({
    "course_id": "ap_calculus_bc",
    "course_name": "AP Calculus BC",
    "ced_document": {
        "local_path": "data/ced/calculus_bc.pdf"
    }
})
```

## Development

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_ced_parser.py

# With coverage
pytest --cov=src tests/
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
ruff check src/
```

## Agent Status

| Agent | Priority | Status | Lines of Code |
|-------|----------|--------|---------------|
| CED Parser | P0 | ✅ Implemented | 370+ |
| Template Crafter | P0 | ✅ Implemented | 340+ |
| Parametric Generator | P0 | ✅ Implemented | 480+ |
| Solution Verifier | P0 | ✅ Implemented | 650+ |
| Master Orchestrator | P0 | ✅ Implemented | 410+ |
| **Total** | | **5/5 Core Agents** | **2250+** |

### Additional Components
- ✅ Database Layer (Template & Variant storage)
- ✅ Data Models (Pydantic models)
- ✅ Core Utilities (Config, Logger, Exceptions)
- ✅ Unit Tests (CED Parser)
- ✅ Integration Tests (Full workflow)
- ✅ Example Scripts (Complete workflow demos)

## License

Proprietary - All Rights Reserved

## Contributors

- Mustafa Yildirim

## Support

For issues and questions, please contact the development team.
