# Acceptance Criteria

(Updated before each feature implementation. Define what "done" means for each task.)

## Task 1: Core types and exceptions

### Acceptance Criteria
- [x] StepOutput class exists as a Pydantic model with fields: query, thought, action, output, observation, execution_time, done, exit_status, submission, state, tool_calls, tool_call_ids, extra_info
- [x] StepOutput has a to_template_format_dict() method that returns a dictionary suitable for template rendering
- [x] TrajectoryStep TypedDict exists with fields: action, observation, response, state, thought, execution_time, query, extra_info
- [x] HistoryItem TypedDict exists with role, content, message_type fields plus optional fields like agent, is_demo, thought, action, tool_calls
- [x] AgentInfo TypedDict exists with fields for model_stats, exit_status, submission, review, edited_files
- [x] AgentRunResult Pydantic model exists with info and trajectory fields
- [x] FormatError exception raised when model response cannot be parsed
- [x] FunctionCallingFormatError exception with message, error_code and extra_info attributes
- [x] ContextWindowExceededError raised when LM context limit is hit
- [x] CostLimitExceededError with subclasses InstanceCostLimitExceededError, TotalCostLimitExceededError, InstanceCallLimitExceededError
- [x] ContentPolicyViolationError and ModelConfigurationError exceptions exist

## Task 2: LLM output parsers

### Acceptance Criteria
- [x] ThoughtActionParser parses model response into thought and action by finding code blocks wrapped in backticks
- [x] ThoughtActionParser raises FormatError when no code block is found
- [x] XMLThoughtActionParser extracts action from <command></command> tags
- [x] XMLThoughtActionParser raises FormatError when command tags are missing
- [x] FunctionCallingParser extracts action from tool_calls in model response
- [x] FunctionCallingParser raises FunctionCallingFormatError with "missing" code when no tool calls present
- [x] FunctionCallingParser raises FunctionCallingFormatError with "multiple" code when more than one tool call
- [x] FunctionCallingParser validates tool call against command list and raises error for unknown commands
- [x] JsonParser parses JSON object with "thought" and "command" fields
- [x] JsonParser raises FormatError for invalid JSON or missing keys
- [x] Identity parser returns the message unchanged as both thought and action
- [x] ActionParser verifies the first word is a known command name
- [x] EditFormat is a variant of ThoughtActionParser for edit operations

## Task 3: History processors

### Acceptance Criteria
- [x] DefaultHistoryProcessor returns history unchanged
- [x] LastNObservations keeps only the last N observation messages, replacing earlier ones with a summary
- [x] LastNObservations never removes the first observation (instance template)
- [x] LastNObservations respects always_keep_output_for_tags and always_remove_output_for_tags
- [x] TagToolCallObservations adds tags to history items for specific tool calls
- [x] CacheControlHistoryProcessor adds cache_control markers to the last N user messages
- [x] CacheControlHistoryProcessor removes cache_control from other messages
- [x] RemoveRegex removes content matching regex patterns from history items

## Task 4: Model abstraction layer

### Acceptance Criteria
- [x] InstanceStats tracks instance_cost, tokens_sent, tokens_received, api_calls
- [x] InstanceStats supports addition and subtraction operations
- [x] ModelConfig provides configuration for LLM with name, temperature, cost limits
- [x] AbstractModel defines interface with query() method and stats property
- [x] PredeterminedModel returns preset responses (useful for testing)
- [x] ReplayModel replays actions from a trajectory file
- [x] Cost limits raise appropriate exceptions (InstanceCostLimitExceededError, TotalCostLimitExceededError)

## Task 5: Tool configuration and handler

### Acceptance Criteria
- [x] ToolFilterConfig specifies blocklist/allowlist for commands
- [x] ToolConfig combines filter settings, command execution settings, and environment variables
- [x] ToolHandler validates actions against blocklist and returns whether action should be blocked
- [x] ToolHandler checks for submission command in output
- [x] ToolHandler generates command documentation from registered commands
- [x] ToolHandler handles multiline command input with heredoc syntax

## Task 6: Problem statement types

### Acceptance Criteria
- [x] ProblemStatement protocol defines id, get_problem_statement(), and get_extra_fields()
- [x] EmptyProblemStatement returns empty string with generated UUID
- [x] TextProblemStatement returns provided text with auto-generated ID from hash
- [x] FileProblemStatement reads content from file path
- [x] Problem statements can provide extra fields for template rendering
