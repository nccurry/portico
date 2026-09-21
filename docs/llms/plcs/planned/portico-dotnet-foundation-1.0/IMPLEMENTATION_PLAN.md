# Implementation Plan

## Delivery rules

- Work from the core outward. Do not start a later phase while its inward
  dependency is unstable.
- Preserve the existing desktop behavior during the foundation work.
- Fix every P1 and P2 finding found by a phase review. Fix inexpensive P3
  findings or record why they remain.
- Run the named phase checks before moving to the next phase.
- Do not add MCP, HTTP, gRPC, report commands, or visual redesign work under
  this packet.

## Phase 0: Establish the baseline and migration inventory

### Goal

Turn the repository into a clear .NET-first starting point without pretending
the target architecture already exists.

### Work

- Record the current project graph, public CLI behavior, configuration fields,
  data-source behavior, test counts, and a behavior-to-replacement-test trace.
- Treat legacy/python as reference-only. Do not repair or extend it.
- Create a field-by-field inventory from active C# settings to proposed
  portico.toml fields, marking each as keep, rename, move, or reject.
- Mark weekly_summary as reject.
- Define the new config and JSON schema examples before parser work begins,
  including default and explicit companion-file selection.
- Document the clean configuration cutover: create new portico.toml files from
  supported samples, reject the legacy document shape, and provide no automatic
  migration or fallback parser.
- Decide the exact solution/test project layout and replace default task paths
  with working .NET build/test/check commands in the implementation branch.
- Restore a minimal active CI gate for restore, build, and non-visual C# tests.
  Keep visual capture opt-in.
- Rebaseline the existing desktop UI test and capture evidence.

### Exit checks

- The migration inventory has no unclassified active C# setting.
- The current non-visual test count and doctor output are captured.
- The root default task and active CI gate run a non-visual .NET path without
  invoking legacy Python files.
- The planned project-reference matrix is reviewed.
- No UI or MCP behavior changed.

## Phase 1: Create and enforce project boundaries

### Goal

Create the target project structure before moving business behavior.

### Work

- Add Portico.Application, Portico.Configuration, Portico.Data,
  Portico.Cli, Portico.Desktop, and Portico.Architecture.Tests.
- Keep Portico.App as the executable.
- Add an architecture test that evaluates allowed project references from
  production project files in the active build configuration.
- Add forbidden-dependency tests or source scans for Finance.
- Move only assembly markers, neutral records, and test scaffolding needed to
  establish the build graph.
- Keep the old Dashboard implementation operational while its replacement is
  being built.

### Exit checks

- The target graph compiles with no forbidden reference.
- Architecture tests fail when deliberately given direct and imported
  prohibited-reference fixtures.
- Existing Finance, Dashboard, Adapter, and App tests still pass.

## Phase 2: Make Finance pure and introduce Application

### Goal

Move financial rules and semantic reports behind an in-process application API.

### Work

- Remove WorkbookSourceKind and DataSourceSettings from Finance.
- Split current Dashboard ownership: semantic report types/building to
  Application; Roci-specific state remains outside.
- Define the smallest Application requests, workspace model, input interfaces,
  outcomes, and PorticoProblem model.
- Use explicit C# 15 success/failure unions only for expected boundary results.
- Build deterministic Finance and Application tests using in-memory snapshots
  and settings.
- Preserve existing report semantics before changing inputs or CLI behavior.

### Exit checks

- Finance has no source-choice, TOML, Roci, or CLI types.
- Application tests cover normal, empty, invalid, cancellation, and problem
  ordering behavior.
- Core and Application pass the initial coverage gate or have a documented
  ratchet plan with a failing-gate date.

## Phase 3: Build configuration and data adapters

### Goal

Replace mixed adapter behavior with separate, typed configuration and data
boundaries.

### Work

- Implement the versioned portico.toml and portico.secrets.toml readers.
- Create exact fixtures for valid config, multiple invalid fields, missing
  secrets, relative paths, unknown keys, legacy document shape, and rejected
  weekly_summary.
- Implement local CSV and Google Sheets readers against Application input
  interfaces.
- Keep WorkbookNormalizer as the shared trust boundary, moving it to the
  owning Data project.
- Inject HTTP ownership from Portico.App rather than constructing clients in
  CLI code.
- Translate expected errors to PorticoProblem values and redact secrets.
- Replace root demo fixtures with the new schema. Do not support the old
  document shape; an explicit config path remains a location selector rather
  than a filename-based compatibility switch.

### Exit checks

- Configuration and Data tests run without Desktop or CLI references.
- CSV and fake-Google fixtures normalize to the same snapshot contract.
- All failure output is safe and deterministic.
- The old mixed TOML loader and source type leak are removed or unused.

## Phase 4: Rewire Portico.App, CLI, and Desktop

### Goal

Make all active call surfaces use Application without changing the desktop UX.

### Work

- Move command parsing and terminal output formatting into Portico.Cli.
- Implement run, config check, data check, and doctor plus the documented
  per-command option, exit-code, and JSON contracts.
- Make Portico.App compose the readers, Application, CLI, and Desktop.
- Let Portico.App dispatch the typed run command to Application and Desktop;
  it must not duplicate CLI grammar or terminal formatting policy.
- Replace direct adapter construction in CLI code with Application calls.
- Move Roci startup and dashboard presentation into Portico.Desktop.
- Translate Application problems into existing desktop status/error views.
- Remove DashboardSession and old App paths only after equivalent tests pass.

### Exit checks

- CLI contract tests prove text, JSON, stdout/stderr, exit code, and redaction
  behavior.
- A published-process E2E test runs config check, data check, and doctor.
- Existing desktop interaction and visual tests pass without layout changes.
- No CLI or Desktop project references Configuration or Data directly.
- App composition tests prove a parsed run command reaches Desktop without a
  Portico.Cli-to-Portico.Desktop reference.

## Phase 5: Finish quality, operations, and documentation

### Goal

Make the target maintainable for the next feature.

### Work

- Expand the Phase 0 default task and CI gate into focused lanes for core,
  application, configuration, data, CLI, desktop, architecture, E2E, visual,
  and aggregate verification.
- Make active documentation .NET-first and retain legacy links only as
  reference.
- Publish a short clean-cutover guide explaining the new configuration files
  and the deliberate absence of compatibility.
- Remove obsolete project references, duplicate tests, stale task paths, and
  old architecture claims.
- Run code, test, documentation, and dependency-boundary reviews.
- Re-run the whole verification suite after all fixes.

### Exit checks

- All named test lanes pass.
- Finance plus Application meet the coverage gate.
- The root documentation describes the implemented architecture accurately.
- Active documentation and samples explain the configuration cutover.
- git diff --check passes.
- The Desktop and MCP PLC can begin without depending on old App, Dashboard, or
  Adapter seams.
