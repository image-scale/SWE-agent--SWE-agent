"""Custom exceptions for the agent system.

This module defines all custom exceptions used by the agent to signal
various error conditions like parsing failures, cost limits, and
configuration errors.
"""

from typing import Any, Literal


class FormatError(Exception):
    """Raised when the model response cannot be parsed into thought and actions.

    This typically occurs when the model's output doesn't match the expected
    format for the current parser (e.g., missing code blocks for ThoughtActionParser).
    """
    pass


class FunctionCallingFormatError(FormatError):
    """Format error specific to function calling parser.

    Provides additional context about what went wrong with the function call,
    including an error code and extra information for error templates.
    """

    def __init__(
        self,
        message: str,
        error_code: Literal[
            "missing", "multiple", "incorrect_args", "invalid_json",
            "invalid_command", "missing_arg", "unexpected_arg"
        ],
        **extra_info: Any,
    ):
        super().__init__(message + f" [error_code={error_code}]")
        self.message = message
        self.error_code = error_code
        self.extra_info = {"error_code": error_code, **extra_info}


class ContextWindowExceededError(Exception):
    """Raised when the language model's context window is exceeded.

    This happens when the conversation history plus the next prompt
    would exceed the model's maximum input token limit.
    """
    pass


class CostLimitExceededError(Exception):
    """Base exception for cost-related limits being exceeded."""
    pass


class InstanceCostLimitExceededError(CostLimitExceededError):
    """Raised when the cost limit for a single task instance is exceeded.

    This helps prevent runaway costs on difficult or stuck problems.
    """
    pass


class TotalCostLimitExceededError(CostLimitExceededError):
    """Raised when the total cost limit across all instances is exceeded.

    This is a hard stop that halts all processing to prevent budget overruns.
    """
    pass


class InstanceCallLimitExceededError(CostLimitExceededError):
    """Raised when the per-instance API call limit is exceeded.

    This limits the number of model queries for a single problem instance.
    """
    pass


class ContentPolicyViolationError(Exception):
    """Raised when the model response violates a content policy.

    Some model providers reject responses that contain inappropriate content.
    """
    pass


class ModelConfigurationError(Exception):
    """Raised when the model configuration is invalid.

    This indicates that no further retries should be made because the
    configuration itself is broken, not just a transient API error.
    """
    pass
