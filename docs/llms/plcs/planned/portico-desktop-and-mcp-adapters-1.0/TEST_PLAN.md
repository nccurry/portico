# Test Plan

## Desktop tests

| Area | Required proof |
| --- | --- |
| Application wiring | A fake Application service drives each Desktop state without configuration/data implementations. |
| State transitions | Opening, ready, empty, configuration failure, data failure, cancellation, and unexpected failure have focused tests. |
| Navigation | Existing navigation and retained-state behavior remains covered. |
| Visual behavior | Fixed-size captures cover every changed status state and affected page. |
| Privacy | Error panels contain safe problem wording only. |

## MCP tests

| Area | Required proof |
| --- | --- |
| Tool catalog | Expected tools are present and no unapproved tool is registered. |
| Input validation | Missing, malformed, extra, and incompatible values fail before Application runs. |
| Success shape | Each tool returns its documented versioned response. |
| Failure shape | Each PorticoProblem group maps to stable safe tool output. |
| Ordering | Lists and problem arrays are deterministic. |
| Privacy | Secrets, URLs, rows, stack traces, and private paths never appear. |
| Read-only behavior | Tools do not change source/configuration files or finance data. |

## Integration and E2E tests

- Run Desktop against a fake Application service for UI isolation.
- Run MCP against a real Application fixture with fake Configuration/Data
  implementations.
- Run an App composition test that gives each outer host one configured
  Application service and proves neither Desktop nor MCP constructs a data
  reader.
- Run a standard-input/output MCP protocol E2E against portico mcp serve with a
  local test client. Run Desktop startup separately; Desktop and MCP do not
  coexist in one process.
- Do not call a real Google Sheet or require a live external MCP client in
  normal CI.

## Completion evidence

- Desktop visual capture evidence for changed states.
- MCP request/response examples for every public tool.
- Redaction test output.
- Architecture test output showing both adapters point only to Application.
- Aggregate verification output and git diff --check.
