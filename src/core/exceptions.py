"""Custom exceptions for Aprep agents."""


class AprepError(Exception):
    """Base exception for all Aprep errors."""

    pass


class ConfigurationError(AprepError):
    """Configuration-related errors."""

    pass


class ValidationError(AprepError):
    """Validation errors for data and templates."""

    pass


class ParsingError(AprepError):
    """Errors during document parsing."""

    pass


class CEDParseError(ParsingError):
    """Errors specific to CED document parsing."""

    pass


class TemplateError(AprepError):
    """Template-related errors."""

    pass


class GenerationError(AprepError):
    """Errors during question generation."""

    pass


class VerificationError(AprepError):
    """Errors during solution verification."""

    pass


class PlagiarismError(AprepError):
    """Plagiarism detection errors."""

    pass


class APIError(AprepError):
    """External API errors (Anthropic, etc.)."""

    pass


class WorkflowError(AprepError):
    """Workflow and orchestration errors."""

    pass
