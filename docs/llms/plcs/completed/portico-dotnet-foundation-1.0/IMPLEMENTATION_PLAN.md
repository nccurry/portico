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
- Build directly against the sibling `../roci` checkout, allow `ROCI_ROOT` for
  another local checkout, and give a clear setup error when Roci is missing.
- Keep continuous integration deferred. Keep visual capture opt-in.
- Rebaseline the existing desktop UI test and capture evidence.

### Exit checks

- The migration inventory has no unclassified active C# setting.
- The current non-visual test count and doctor output are captured.
- The root default task runs a non-visual .NET path without invoking legacy
  Python files.
- The local Roci source contract is documented and rejects a missing checkout
  clearly.
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
  production project files in Debug and Release.
- Enforce the final edges for the new projects and freeze the current legacy
  edges: App's Adapters, Dashboard, Finance, and Roci references through Phase
  4; Adapters to Dashboard and Finance through Phase 3; and Dashboard to
  Finance through Phase 4. Reject any added Portico or external Roci edge.
- Add forbidden-dependency tests or source scans for Finance.
- Move only assembly markers, neutral records, and test scaffolding needed to
  establish the build graph.
- Keep the old Dashboard implementation operational while its replacement is
  being built.

### Exit checks

- The Phase 1 scaffold compiles, and every evaluated production reference
  matches the final matrix or an enumerated temporary transition exception.
- Architecture tests fail when deliberately given direct and imported
  prohibited-reference fixtures.
- The architecture suite evaluates every production project and its exact
  Portico and Roci reference sets, including the time-bounded legacy edges.
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
- Put the new path's shared normalizer in Data. The old Adapters normalizer
  remains only for the still-live App path until Phase 4 removes that path;
  do not make Data depend on Adapters to avoid a temporary second boundary.
- Define and enforce a supported source-date floor before report calculations.
  It must leave every configured current/comparison lookback representable;
  reject earlier transaction, balance, or budget dates with a safe typed data
  problem. Do not clip matched comparison periods to unequal lengths.
- Inject HTTP ownership from Portico.App rather than constructing clients in
  CLI code.
- Translate expected errors to PorticoProblem values and redact secrets.
- Add root demo fixtures in the new schema. Keep the old demo file only for
  the still-live App path until Phase 4; the new reader must reject its old
  document shape. An explicit config path selects a location, not a
  filename-based compatibility switch.

### Exit checks

- Configuration and Data tests run without Desktop or CLI references.
- CSV and fake-Google fixtures normalize to the same snapshot contract.
- Dates too early for the supported report windows fail at the data boundary,
  before a report can underflow the calendar.
- All failure output is safe and deterministic.
- Application's new configuration and data path does not call the old mixed
  TOML loader or old source types. The old App path may retain them only until
  its Phase 4 rewire, with architecture tests freezing those temporary edges.

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
- Delete the old Adapters normalizer, mixed TOML loader, and source types once
  the new App path and owning tests have replaced their last production uses.
- Remove the old root demo configuration after App uses the new portico.toml.
- Replace Finance's display-ready exclusion sentences, budget empty-state copy,
  and Data Health names/actions/status strings with typed reasons and status.
  Keep the existing desktop wording in its presentation mapping.
- Resolve ownership of lookback choices, filter-control options, and the
  default income view when the new configuration and Desktop contracts are
  settled; keep only financial policy in FinanceSettings.

### Exit checks

- CLI contract tests prove text, JSON, stdout/stderr, exit code, and redaction
  behavior.
- A published-process E2E test runs config check, data check, and doctor.
- Existing desktop interaction and visual tests pass without layout changes.
- No CLI or Desktop project references Configuration or Data directly.
- App composition tests prove a parsed run command reaches Desktop without a
  Portico.Cli-to-Portico.Desktop reference.
- Finance returns financial values and typed classifications, not desktop
  wording or control choices.

## Phase 5: Finish quality, operations, and documentation

### Goal

Make the target maintainable for the next feature.

### Work

- Expand the Phase 0 default task into focused local lanes for core,
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
