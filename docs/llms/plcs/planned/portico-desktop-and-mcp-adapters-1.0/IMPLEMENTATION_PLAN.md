# Implementation Plan

## Phase 0: Confirm the foundation contract

### Work

- Review the implemented Application operations, outcomes, problem codes, and
  semantic report models.
- Inventory current Desktop state and retained captures.
- List the smallest useful MCP user tasks.
- Decide whether report queries are ready. If not, leave them out.
- Confirm the standard-input/output protocol startup behavior and the smallest
  command/configuration surface for portico mcp serve.

### Exit checks

- Every proposed Desktop/MCP action maps to exactly one Application operation.
- No proposed action needs a new Finance, Configuration, or Data shortcut.
- Input/output examples and redaction cases are agreed before coding.
- The MCP host has no HTTP listen mode and no Desktop launch path.

## Phase 1: Improve Desktop as an Application adapter

### Work

- Replace any remaining direct loading/configuration calls.
- Add reviewed readiness/error/empty/cancellation UX states.
- Preserve existing pages unless a reviewed desktop design says otherwise.
- Extend retained visual and interaction coverage for changed states.

### Exit checks

- Desktop depends only on Application and Roci.
- State transitions have focused tests.
- Existing unaffected page capture tests remain green.

## Phase 2: Add the MCP adapter

### Work

- Add Portico.Mcp as a small adapter project.
- Add the typed mcp serve command hand-off from Portico.Cli through Portico.App
  to the local standard-input/output host.
- Implement the approved static tool catalog.
- Validate input at the tool boundary.
- Map Application results to versioned MCP responses.
- Add optional report tools only when the semantic report contract is ready.

### Exit checks

- MCP has no direct adapter, CLI, Desktop, or Finance dependency.
- Standard output contains protocol only and the host does not launch Desktop.
- Contract tests cover valid, invalid, empty, cancellation, and failure cases.
- Redaction tests pass.

## Phase 3: Prove the full experience

### Work

- Run Desktop, MCP, architecture, Application, and E2E suites.
- Review tool descriptions and desktop text for plain English.
- Update public documentation with exact tool names and examples.
- Run one aggregate verification after all review fixes.

### Exit checks

- All P1/P2 review findings are fixed.
- No user-facing surface implies a remote server or write behavior that does
  not exist.
- The MCP and Desktop adapters remain replaceable outer layers.
