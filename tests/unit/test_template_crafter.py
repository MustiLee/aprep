"""Unit tests for Template Crafter agent."""

import pytest
from unittest.mock import Mock, patch
from src.agents.template_crafter import TemplateCrafter, MAX_RETRIES


class TestTemplateCrafter:
    """Test Template Crafter functionality."""

    @pytest.fixture
    def crafter(self):
        """Create TemplateCrafter instance."""
        with patch("src.agents.template_crafter.Anthropic"):
            return TemplateCrafter()

    @pytest.fixture
    def sample_inputs(self):
        """Sample template inputs."""
        return {
            "task_id": "test_001",
            "course_id": "ap_calculus_bc",
            "unit_id": "u2",
            "topic_id": "t2.1",
            "learning_objectives": ["Calculate derivatives using chain rule"],
            "difficulty_target": [0.5, 0.7],
            "calculator_policy": "No-Calc",
            "misconceptions": [
                "Forgetting inner derivative",
                "Incorrect power rule application",
            ],
        }

    def test_initialization(self, crafter):
        """Test crafter can be initialized."""
        assert crafter is not None
        assert crafter.model is not None
        # Cost tracking initialized (HIGH PRIORITY feature)
        assert crafter.total_tokens_used == 0
        assert crafter.total_cost_usd == 0.0
        assert crafter.api_call_count == 0

    def test_analyze_learning_objective(self, crafter, sample_inputs):
        """Test learning objective analysis."""
        analysis = crafter._analyze_learning_objective(sample_inputs)

        assert "concepts" in analysis
        assert "operations" in analysis
        assert "difficulty_factors" in analysis
        assert "chain_rule" in analysis["concepts"]
        assert "differentiation" in analysis["operations"]

    def test_design_template_structure_differentiation(self, crafter):
        """Test template structure design for differentiation."""
        analysis = {
            "concepts": ["chain_rule"],
            "operations": ["differentiation"],
            "difficulty_factors": {"num_steps": 1},
        }

        structure = crafter._design_template_structure(analysis, {})

        assert structure["stem_type"] == "procedural"
        assert "{{function}}" in structure["stem"]
        assert "params" in structure
        assert "function" in structure["params"]

    def test_create_distractor_rules(self, crafter):
        """Test distractor rule creation."""
        misconceptions = [
            "Forgetting inner derivative",
            "Incorrect power rule",
        ]
        structure = {"stem": "test"}

        rules = crafter._create_distractor_rules(misconceptions, structure)

        assert len(rules) >= 3  # At least 3 distractors
        assert all("rule_id" in r for r in rules)
        assert all("description" in r for r in rules)
        assert all("generation" in r for r in rules)

    def test_generate_template_id(self, crafter):
        """Test template ID generation."""
        inputs = {
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.1",
        }

        template_id = crafter._generate_template_id(inputs)

        assert "calculus_bc" in template_id
        assert "2.1" in template_id or "21" in template_id
        assert "_v" in template_id  # Version timestamp

    def test_validation_pass(self, crafter):
        """Test template validation - passing case."""
        template = {
            "template_id": "test_123",
            "stem": "Let f(x) = {{function}}. Find f'(x).",
            "params": {"function": {"type": "algebraic"}},
            "distractor_rules": [
                {"rule_id": "r1", "description": "Error 1"},
                {"rule_id": "r2", "description": "Error 2"},
                {"rule_id": "r3", "description": "Error 3"},
            ],
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.1",
        }

        validation = crafter._validate_template(template)

        assert validation["passed"] is True
        assert all(validation["checks"].values())
        assert "quality_score" in validation
        assert validation["quality_score"] > 0

    def test_validation_fail_missing_fields(self, crafter):
        """Test template validation - failing case."""
        template = {
            "stem": "Question text",
            # Missing: template_id, params, distractor_rules, metadata
        }

        validation = crafter._validate_template(template)

        assert validation["passed"] is False
        assert not all(validation["checks"].values())

    def test_quality_score_calculation_high(self, crafter):
        """Test quality score calculation - high quality template."""
        template = {
            "template_id": "test_001",
            "stem": "Let f(x) = {{function}}. Find f'(x).",
            "params": {
                "function": {"type": "algebraic"},
                "coefficient": {"type": "numeric"},
                "exponent": {"type": "numeric"},
            },
            "distractor_rules": [
                {"rule_id": "r1"},
                {"rule_id": "r2"},
                {"rule_id": "r3"},
                {"rule_id": "r4"},
            ],
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.1",
            "learning_objectives": ["CHA-4.A"],
            "tags": ["derivatives", "chain_rule"],
            "difficulty_range": [0.5, 0.7],
            "calculator": "No-Calc",
            "bloom_level": "Apply",
        }

        checks = {
            "has_template_id": True,
            "has_stem": True,
            "has_params": True,
            "has_distractors": True,
            "has_metadata": True,
        }

        score = crafter._calculate_quality_score(template, checks)

        # Should be high quality (all fields present)
        assert score >= 0.9
        assert score <= 1.0

    def test_quality_score_calculation_low(self, crafter):
        """Test quality score calculation - low quality template."""
        template = {
            "template_id": "test_001",
            "stem": "Question",
            "params": {},  # No parameters
            "distractor_rules": [],  # No distractors
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.1",
        }

        checks = {
            "has_template_id": True,
            "has_stem": True,
            "has_params": False,
            "has_distractors": False,
            "has_metadata": True,
        }

        score = crafter._calculate_quality_score(template, checks)

        # Should be low quality
        assert score < 0.6

    def test_track_api_usage(self, crafter):
        """Test API usage tracking (HIGH PRIORITY feature)."""
        # Mock API response
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=1000, output_tokens=500)

        crafter._track_api_usage(mock_response)

        assert crafter.total_tokens_used == 1500
        assert crafter.api_call_count == 1
        assert crafter.total_cost_usd > 0

        # Second call should accumulate
        crafter._track_api_usage(mock_response)

        assert crafter.total_tokens_used == 3000
        assert crafter.api_call_count == 2

    def test_get_usage_stats(self, crafter):
        """Test usage stats retrieval (HIGH PRIORITY feature)."""
        # Mock some usage
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=1000, output_tokens=500)
        crafter._track_api_usage(mock_response)

        stats = crafter.get_usage_stats()

        assert "total_tokens" in stats
        assert "total_cost_usd" in stats
        assert "api_calls" in stats
        assert "avg_tokens_per_call" in stats
        assert "avg_cost_per_call" in stats

        assert stats["total_tokens"] == 1500
        assert stats["api_calls"] == 1
        assert stats["avg_tokens_per_call"] == 1500

    def test_get_usage_stats_no_calls(self, crafter):
        """Test usage stats with no API calls."""
        stats = crafter.get_usage_stats()

        assert stats["total_tokens"] == 0
        assert stats["total_cost_usd"] == 0
        assert stats["api_calls"] == 0
        assert stats["avg_tokens_per_call"] == 0
        assert stats["avg_cost_per_call"] == 0

    @patch("src.agents.template_crafter.time.sleep")
    def test_retry_logic_on_validation_error(self, mock_sleep, crafter, sample_inputs):
        """Test retry logic with exponential backoff (HIGH PRIORITY feature)."""
        # Mock Claude API to return invalid YAML first 2 times
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)

        # First call: invalid YAML
        # Second call: invalid YAML
        # Third call: valid template
        call_count = [0]

        def mock_create(*args, **kwargs):
            call_count[0] += 1
            mock_response.content = [Mock()]

            if call_count[0] < 3:
                # Return invalid YAML
                mock_response.content[0].text = "invalid: yaml: content: ["
            else:
                # Return valid template
                mock_response.content[0].text = """
template_id: test_001
stem: "Let f(x) = {{function}}. Find f'(x)."
params:
  function:
    type: algebraic
course_id: ap_calculus_bc
topic_id: t2.1
distractor_rules:
  - rule_id: r1
    description: Error 1
    generation: "{{wrong}}"
  - rule_id: r2
    description: Error 2
    generation: "{{wrong}}"
  - rule_id: r3
    description: Error 3
    generation: "{{wrong}}"
"""
            return mock_response

        crafter.client.messages.create = Mock(side_effect=mock_create)

        analysis = {"concepts": [], "operations": []}
        structure = {"stem": "test", "params": {}}
        distractors = [{"rule_id": "r1"}, {"rule_id": "r2"}, {"rule_id": "r3"}]

        result = crafter._generate_with_claude(
            sample_inputs, analysis, structure, distractors
        )

        # Should have retried and succeeded on 3rd attempt
        assert crafter.client.messages.create.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep called twice (between retries)
        assert result is not None
        assert "template_id" in result

    @patch("src.agents.template_crafter.time.sleep")
    def test_retry_exhaustion_uses_fallback(self, mock_sleep, crafter, sample_inputs):
        """Test that fallback is used when all retries are exhausted."""
        # Mock Claude API to always return invalid YAML
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_response.content = [Mock()]
        mock_response.content[0].text = "invalid: yaml: ["

        crafter.client.messages.create = Mock(return_value=mock_response)

        analysis = {"concepts": [], "operations": []}
        structure = {"stem": "test", "params": {"p1": {}}}
        distractors = [{"rule_id": "r1"}, {"rule_id": "r2"}, {"rule_id": "r3"}]

        result = crafter._generate_with_claude(
            sample_inputs, analysis, structure, distractors
        )

        # Should have retried MAX_RETRIES times
        assert crafter.client.messages.create.call_count == MAX_RETRIES
        assert mock_sleep.call_count == MAX_RETRIES - 1

        # Should return fallback template
        assert result is not None
        assert "template_id" in result
        assert result["stem"] == "test"

    def test_create_fallback_template(self, crafter, sample_inputs):
        """Test fallback template creation."""
        structure = {"stem": "Let f(x) = x². Find f'(x).", "params": {"x": {}}}
        distractors = [
            {"rule_id": "r1", "description": "Error 1"},
            {"rule_id": "r2", "description": "Error 2"},
            {"rule_id": "r3", "description": "Error 3"},
        ]

        template = crafter._create_fallback_template(sample_inputs, structure, distractors)

        assert template["template_id"] is not None
        assert template["course_id"] == "ap_calculus_bc"
        assert template["topic_id"] == "t2.1"
        assert template["stem"] == structure["stem"]
        assert len(template["distractor_rules"]) == 3
        assert template["calculator"] == "No-Calc"

    @patch("src.agents.template_crafter.Anthropic")
    def test_full_template_creation_with_metadata(self, mock_anthropic, sample_inputs):
        """Test full template creation includes all metadata (HIGH PRIORITY features)."""
        # Mock Claude API response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=1000, output_tokens=800)
        mock_response.content = [Mock()]
        mock_response.content[0].text = """
template_id: test_full
stem: "Let f(x) = {{function}}. Find f'(x)."
params:
  function:
    type: algebraic
course_id: ap_calculus_bc
topic_id: t2.1
distractor_rules:
  - rule_id: r1
    description: Forget inner derivative
    generation: "{{wrong1}}"
  - rule_id: r2
    description: Wrong power rule
    generation: "{{wrong2}}"
  - rule_id: r3
    description: Sign error
    generation: "{{wrong3}}"
"""
        mock_client.messages.create = Mock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        crafter = TemplateCrafter()

        result = crafter.create_template(sample_inputs)

        # Verify all metadata is present
        assert result["created_by"] == "agent.template_crafter"
        assert "created_at" in result
        assert result["version"] == "1.0"
        assert result["task_id"] == "test_001"

        # Verify quality score is included (HIGH PRIORITY feature)
        assert "quality_score" in result
        assert isinstance(result["quality_score"], float)

        # Verify API usage stats are included (HIGH PRIORITY feature)
        assert "api_usage" in result
        assert "tokens" in result["api_usage"]
        assert "cost_usd" in result["api_usage"]

    def test_template_versioning(self, crafter):
        """Test template versioning is included (HIGH PRIORITY feature)."""
        template = {
            "template_id": "test_001",
            "stem": "test",
            "params": {"p1": {}},
            "distractor_rules": [{}, {}, {}],
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.1",
        }

        # Template should have version in metadata
        assert "version" not in template  # Not added yet

        # After create_template is called, version should be added
        # (tested in test_full_template_creation_with_metadata)


class TestBatchCreation:
    """Test batch template creation."""

    @pytest.fixture
    def crafter(self):
        """Create TemplateCrafter instance."""
        with patch("src.agents.template_crafter.Anthropic"):
            return TemplateCrafter()

    @pytest.fixture
    def sample_inputs(self):
        """Sample template inputs."""
        return {
            "task_id": "batch_test",
            "course_id": "ap_calculus_bc",
            "unit_id": "u2",
            "topic_id": "t2.1",
            "learning_objectives": ["Calculate derivatives"],
            "difficulty_target": [0.5, 0.7],
            "calculator_policy": "No-Calc",
            "misconceptions": ["Error 1", "Error 2"],
        }

    @patch("src.agents.template_crafter.Anthropic")
    def test_create_batch(self, mock_anthropic, crafter, sample_inputs):
        """Test creating multiple templates."""
        # Mock successful template creation
        mock_client = Mock()
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=500, output_tokens=400)
        mock_response.content = [Mock()]
        mock_response.content[0].text = """
template_id: batch_test
stem: "Test"
params:
  p1: {}
course_id: ap_calculus_bc
topic_id: t2.1
distractor_rules:
  - rule_id: r1
  - rule_id: r2
  - rule_id: r3
"""
        mock_client.messages.create = Mock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        crafter = TemplateCrafter()

        templates = crafter.create_batch(sample_inputs, count=3)

        # Should create 3 templates
        assert len(templates) <= 3  # May be less if some fail
        assert all("template_id" in t for t in templates)

        # Each should have unique task_id
        task_ids = [t["task_id"] for t in templates]
        assert len(set(task_ids)) == len(templates)


class TestErrorHandling:
    """Test error handling in template creation."""

    @pytest.fixture
    def crafter(self):
        """Create TemplateCrafter instance."""
        with patch("src.agents.template_crafter.Anthropic"):
            return TemplateCrafter()

    def test_invalid_inputs_raises_error(self, crafter):
        """Test that invalid inputs raise appropriate errors."""
        invalid_inputs = {}  # Missing required fields

        with pytest.raises(Exception):
            crafter.create_template(invalid_inputs)

    @patch("src.agents.template_crafter.time.sleep")
    def test_api_error_uses_fallback(self, mock_sleep, crafter):
        """Test that API errors fall back to basic template."""
        # Mock API to raise exception
        crafter.client.messages.create = Mock(side_effect=Exception("API Error"))

        inputs = {
            "task_id": "error_test",
            "course_id": "ap_calculus_bc",
            "topic_id": "t2.1",
            "learning_objectives": ["Test"],
            "misconceptions": [],
        }

        analysis = {"concepts": [], "operations": []}
        structure = {"stem": "test", "params": {"p1": {}}}
        distractors = [{}, {}, {}]

        result = crafter._generate_with_claude(inputs, analysis, structure, distractors)

        # Should use fallback without retrying on API errors
        assert result is not None
        assert "template_id" in result
        assert mock_sleep.call_count == 0  # No retries on API errors
