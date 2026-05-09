# Todo

## Plan
Build the SWE-agent system bottom-up with user-facing functionality first. Start with core types and exceptions, then build the parsing system (the most testable user-facing feature), followed by history processors, model abstraction, tool handling, problem statements, environment, and finally the agent that ties everything together.

## Tasks
- [x] Task 1: Implement core types (StepOutput, TrajectoryStep, History types) and custom exceptions for the agent system (types.py + exceptions.py + tests)
- [x] Task 2: Implement LLM output parsers that extract thought and action from model responses (ThoughtActionParser, FunctionCallingParser, JsonParser, XMLParser, etc.)
- [x] Task 3: Implement history processors for managing conversation context (DefaultHistoryProcessor, LastNObservations, CacheControlProcessor, TagToolCallObservations)
- [>] Task 4: Implement the model abstraction layer with LiteLLM integration, cost tracking, and multiple model types (HumanModel, ReplayModel, LiteLLMModel)
- [ ] Task 5: Implement tool configuration, command definitions, and tool handler for managing available commands and their execution
- [ ] Task 6: Implement problem statement types for defining tasks (TextProblemStatement, FileProblemStatement, EmptyProblemStatement, GithubIssue)
- [ ] Task 7: Implement the environment abstraction for managing runtime execution and repository operations
- [ ] Task 8: Implement the agent class that orchestrates models, tools, environment, and history to solve problems
