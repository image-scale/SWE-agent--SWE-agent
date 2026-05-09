# Acceptance Criteria

(Updated before each feature implementation. Define what "done" means for each task.)

## Task 1: Core types and exceptions

### Acceptance Criteria
- [ ] StepOutput class exists as a Pydantic model with fields: query, thought, action, output, observation, execution_time, done, exit_status, submission, state, tool_calls, tool_call_ids, extra_info
- [ ] StepOutput has a to_template_format_dict() method that returns a dictionary suitable for template rendering
- [ ] TrajectoryStep TypedDict exists with fields: action, observation, response, state, thought, execution_time, query, extra_info
- [ ] HistoryItem TypedDict exists with role, content, message_type fields plus optional fields like agent, is_demo, thought, action, tool_calls
- [ ] AgentInfo TypedDict exists with fields for model_stats, exit_status, submission, review, edited_files
- [ ] AgentRunResult Pydantic model exists with info and trajectory fields
- [ ] FormatError exception raised when model response cannot be parsed
- [ ] FunctionCallingFormatError exception with message, error_code and extra_info attributes
- [ ] ContextWindowExceededError raised when LM context limit is hit
- [ ] CostLimitExceededError with subclasses InstanceCostLimitExceededError, TotalCostLimitExceededError, InstanceCallLimitExceededError
- [ ] ContentPolicyViolationError and ModelConfigurationError exceptions exist
