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
- [ ] ThoughtActionParser parses model response into thought and action by finding code blocks wrapped in backticks
- [ ] ThoughtActionParser raises FormatError when no code block is found
- [ ] XMLThoughtActionParser extracts action from <command></command> tags
- [ ] XMLThoughtActionParser raises FormatError when command tags are missing
- [ ] FunctionCallingParser extracts action from tool_calls in model response
- [ ] FunctionCallingParser raises FunctionCallingFormatError with "missing" code when no tool calls present
- [ ] FunctionCallingParser raises FunctionCallingFormatError with "multiple" code when more than one tool call
- [ ] FunctionCallingParser validates tool call against command list and raises error for unknown commands
- [ ] JsonParser parses JSON object with "thought" and "command" fields
- [ ] JsonParser raises FormatError for invalid JSON or missing keys
- [ ] Identity parser returns the message unchanged as both thought and action
- [ ] ActionParser verifies the first word is a known command name
- [ ] EditFormat is a variant of ThoughtActionParser for edit operations
