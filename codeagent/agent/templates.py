"""Template configuration for agent messages."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TemplateConfig(BaseModel):
    """Configuration for message templates used by the agent."""

    system_template: str = ""
    """Template for the system message."""

    instance_template: str = ""
    """Template for the problem instance description."""

    next_step_template: str = "Observation: {{observation}}"
    """Template for showing command output to the model."""

    next_step_truncated_observation_template: str = (
        "Observation: {{observation[:max_observation_length]}}<response clipped>"
        "<NOTE>Observations should not exceeded {{max_observation_length}} characters. "
        "{{elided_chars}} characters were elided. Please try a different command that produces less output "
        "or use head/tail/grep/redirect the output to a file.</NOTE>"
    )
    """Template for truncated observations."""

    max_observation_length: int = 100_000
    """Maximum length of observation before truncation."""

    next_step_no_output_template: str | None = None
    """Template when command produces no output. Defaults to next_step_template."""

    strategy_template: str | None = None
    """Optional template for strategy instructions."""

    demonstration_template: str | None = None
    """Template for formatting demonstrations."""

    demonstrations: list[Path] = Field(default_factory=list)
    """Paths to demonstration files."""

    put_demos_in_history: bool = False
    """If True, add demonstrations step-by-step to history instead of as a single message."""

    shell_check_error_template: str = (
        "Your bash command contained syntax errors and was NOT executed. "
        "Please fix the syntax errors and try again. Here is the output:\n"
        "{{bash_stdout}}\n{{bash_stderr}}"
    )
    """Template for bash syntax errors."""

    command_cancelled_timeout_template: str = (
        "The command '{{command}}' was cancelled because it took more than {{timeout}} seconds. "
        "Please try a different command that completes more quickly."
    )
    """Template for command timeout errors."""

    format_error_template: str = (
        "Your output was not formatted correctly. Please follow the expected format:\n"
        "{{expected_format}}\n\nYour output:\n{{output}}"
    )
    """Template for format errors."""

    blocked_action_template: str = (
        "The action '{{action}}' is not allowed. "
        "Please use a different command."
    )
    """Template for blocked actions."""

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context) -> None:
        if self.next_step_no_output_template is None:
            self.next_step_no_output_template = self.next_step_template
