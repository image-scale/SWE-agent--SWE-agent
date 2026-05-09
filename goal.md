# Goal

## Project
SWE-agent — a Python project for autonomous software engineering.

## Description
SWE-agent is a tool that enables language models (like GPT-4 or Claude) to autonomously fix issues in repositories. It provides an agent-computer interface where LLMs can interact with a runtime environment, execute bash commands, navigate codebases, and submit patches. The project features configurable agents with different tool sets, conversation history management, multiple output parsers for LLM responses, and cost/token tracking.

## Scope
- Core types and exceptions for the agent system
- Model abstraction layer supporting multiple LLM providers via litellm
- Tool configuration, parsing, and command handling
- Multiple parsers for interpreting LLM output (thought/action, function calling, JSON, etc.)
- History processors for conversation management
- Problem statement definitions (text, file, GitHub issues)
- Environment abstraction for runtime execution
- Agent orchestration that ties models, tools, and environment together
- Configuration system using Pydantic models
- Test suite covering all core functionality
