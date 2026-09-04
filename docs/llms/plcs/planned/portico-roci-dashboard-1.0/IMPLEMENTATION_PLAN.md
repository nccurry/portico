# Portico Dashboard in Roci 1.0 Implementation Plan

## Document Control

- Lifecycle status: Planned
- PLC packet: [README.md](README.md)
- Owner: Portico and Roci maintainers
- Last updated: 2026-09-03
- Related SRD: [SRD.md](SRD.md)
- Related SADD: [SADD.md](SADD.md)

## Implementation Strategy

Start with a configuration and data path that can be tested without a graphics
window. This gives the project a useful doctor command and establishes exact
financial result fixtures before any chart can hide an error.

Next, make the first Roci additions in their own companion branch: the drawer
and the typed date/category chart grammar. These are needed by Home and the
monthly dashboards, so there is no reason to delay a clean framework decision.
Only then build the desktop shell and pages. Range bars and heatmaps arrive when
the Subscription and Financial Independence pages need them.

Every phase creates an observable result, not merely a folder or an abstraction.
Each phase is reviewable on its own, and an advanced Portico page may not use a
custom-drawing workaround while the equivalent Roci component is missing.

## Phase Summary

| Phase | Goal | Requirements | Code areas | Validation | Exit criteria | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Create a runnable C# foundation and redacted setup checker | REQ-001, 004, 013-015, 018, 020 | Solution, Task/mise, config parser, doctor, demo skeleton | Task lint/build/test and doctor | Local demo config validates in text and JSON modes | Planned |
| 1 | Load data and prove financial calculations before UI work | REQ-005-007, 011-012, 016 | Finance, adapters, synthetic data, report records | Finance/adapter/CLI tests | Exact results pass from local and mocked remote sources | Planned |
| 2 | Add the Roci baseline the dashboard needs | REQ-003, 009-010, 017 | Separate Roci drawer, date/category charts, samples/tests | Roci focused and broad gates | Native drawer and date/category overlay components are usable from Portico | Planned |
| 3 | Deliver a usable desktop shell and Home dashboard | REQ-002-004, 008-009, 014, 017 | App host/session/renderer, Home config/report | Desktop behaviour and Home captures | Drawer navigation and Home work from local demo data | Planned |
| 4 | Deliver every standard dashboard page | REQ-002, 004, 008-009, 017 | Income, Spending, YoY, Merchant, Budget, Top, Data Health | Report/UI/visual tests | Seven configured page views work with filters and data grids | Planned |
| 5 | Deliver advanced Roci visuals and the remaining pages | REQ-002, 008-010, 017, 020 | Roci range bars/heatmap; Subscriptions and FI | Roci and app visual/interaction tests | All ten views use native Roci components, with no custom app drawing workaround | Planned |
| 6 | Harden, document, and prove publish paths | REQ-015-020 | Full suite, docs, publish profiles, final review | Broad Task/Roci checks and publish smoke | Evidence and known limits are recorded for a ready-to-review result | Planned |

## Phase Details

### Phase 0: Foundation and Doctor Command

- Problems solved: Provides a repeatable build/test command surface and catches
  configuration mistakes before desktop work begins.
- Included requirements: REQ-001, REQ-004, REQ-013, REQ-014, REQ-015,
  REQ-018, REQ-020.
- Concrete delivery:
  - A solution with Portico.Finance, Portico.Dashboard, Portico.Adapters, and
    Portico.App projects plus matching test projects.
  - global.json, mise.toml, Taskfile.yml, editor/analyzer settings, and a
    non-committed RociSourceRoot development setting documented without an
    absolute path.
  - Versioned TOML parser/binder and rules validator for current Portico
    calculation settings plus the dashboard page/filter/widget section.
  - portico doctor with text and JSON output, stable exit codes, URL/data
    redaction, and a local-demo configuration.
  - A checked-in synthetic four-tab fixture skeleton and ignored secrets-file
    template.
- Expected edits:
  - Root solution/build files and README setup section.
  - src/Portico.Finance, src/Portico.Dashboard, src/Portico.Adapters,
    src/Portico.App, and tests/ project folders.
  - config examples, data/demo, .gitignore, and docs.
- Validation:
  - task format
  - task lint
  - task build:strict
  - task test:adapters
  - task doctor
  - task test
  - git diff --check
- Exit criteria:
  - A clean checkout can run doctor against the synthetic local config.
  - doctor --output json emits one valid redacted JSON document on stdout.
  - Invalid schema version, duplicate page/widget ID, unknown widget/filter
    kind, invalid default, bad source selection, and a secret URL in a failure
    path have named tests.
- Rollback or fallback: Revert the isolated foundation commits. No source data,
  network resource, or Roci public API has changed.
- Cleanup: Do not leave a parallel Python build command or an untyped temporary
  configuration model after typed records land.

### Phase 1: Deterministic Data and Finance Core

- Problems solved: Makes the workbook contract and all financial calculations
  explicit and testable before charts are connected.
- Included requirements: REQ-005, REQ-006, REQ-007, REQ-011, REQ-012,
  REQ-016, REQ-018.
- Concrete delivery:
  - A shared CSV parser/normalizer for local and public-sheet sources.
  - Explicit Google URL validation and CSV export resolution with cancellation
    and safe diagnostics.
  - Immutable PortfolioSnapshot, data-health findings, and typed report
    result records for all ten views.
  - The current Portico financial behaviour ported as pure named calculators.
  - A synthetic complete workbook and expected-result fixture matrix.
- Sub-phase 1A, sources:
  - Implement LocalCsvSnapshotSource and GoogleSheetsSnapshotSource behind the
    one source interface.
  - Use a fake HttpMessageHandler in tests; no automated test reaches Google.
  - Add header, type, duplicate, malformed URL/gid, response, cancellation,
    and redaction cases.
- Sub-phase 1B, finance/report rules:
  - Port classification, transaction-set, aliases, aggregates, budget,
    subscription, safety, FI, and data-health rules in dependency order.
  - Set the clock explicitly for reports that use today.
  - Add exact expected outputs for each named case before a page consumes it.
- Expected edits:
  - Finance records/calculators and focused test data.
  - Adapter source/TOML merge code, test fake handler, local CSV fixture data.
  - Dashboard report records and report-builder tests.
- Validation:
  - task test:finance
  - task test:adapters
  - task test
  - task lint
  - task build:strict
  - git diff --check
- Exit criteria:
  - Local CSV and mocked Google CSV normalize to the same portfolio snapshot.
  - Every page has a typed report result with an exact fixture case.
  - Calculation tests cover empty data, zero denominator, negative/refund,
    transfer, aliases, exclusions, uncategorized values, missing balances,
    monthly/year boundaries, leap day, sort ties, and invalid rows.
  - No finance or report test references Roci, MonoGame, a real URL, or a
    secret file.
- Rollback or fallback: Revert calculator/source commits independently. Keep
  the existing Python app unchanged as behavioural reference during this phase.
- Cleanup: Remove provisional duplicated arithmetic once its named calculator
  is accepted; do not retain both a page-local and a domain calculator.

### Phase 2: Roci Baseline Additions

- Problems solved: Adds the reusable Roci language needed to navigate the
  app and represent normal financial time/category charts cleanly.
- Included requirements: REQ-003, REQ-009, REQ-010, REQ-017, REQ-020.
- Concrete delivery:
  - A separate Roci companion branch/worktree created from the reviewed Roci
    base, named in this packet before its first code change.
  - NavigationDrawer with per-item fluent authoring and normal input/dismissal
    behaviour.
  - Date-aware chart points/axis/guides and category-aligned connected series
    that can share categories with bars.
  - Roci API, core/state, rendering/hit-test, sample, and visual evidence for
    each addition.
  - A temporary Portico project-reference setting that proves the app can
    consume the new Roci surface without copying it.
- Sub-phase 2A, drawer:
  - Add a left drawer with open state, per-item item verb, selected state,
    dismissal, input/focus rules, and ordinary layout/style composition.
  - Add a tiny Roci sample rather than a Portico screen copied into the sample.
- Sub-phase 2B, chart coordinates:
  - Add typed DateOnly points and typed date guide support.
  - Add category-backed connected-series data and validation for a bar/line
    overlay with the same ordered identities.
  - Preserve immutable authoring state, owned static snapshots, atomic
    invalid-configuration failure, tooltip/hit identity, and cache rules.
- Expected edits:
  - Only the companion Roci worktree: Roci.Ui components/chart model/layout/
    rendering/hit tests, sample scenarios, visual baselines, docs.
  - Portico only receives a development reference configuration and a compiled
    consumer test. It does not duplicate component implementation.
- Validation in the Roci worktree:
  - Focused API and chart unit tests for each component.
  - Focused rendering/input tests for drawer, date, and category paths.
  - task lint
  - task build:strict
  - task test
  - task samples:visual-test:ui-visualizations
  - git diff --check
- Exit criteria:
  - A fluent compiled consumer creates a drawer with several items and opens,
    selects, and dismisses it.
  - A date chart retains DateOnly in ticks/tooltips/hits and rejects incompatible
    axis use before state mutation.
  - Bars and a connected category line share categories without application
    index offsets; mismatch failure is clear and atomic.
  - Existing Roci chart visual baselines remain unchanged unless the component's
    own approved sample adds new coverage.
- Rollback or fallback: Revert only the companion Roci commits and keep Portico
  on its currently referenced Roci revision. Do not replace the component with
  manual Portico drawing.
- Cleanup: Do not add a second ChartBuilder, a Portico namespace, or temporary
  number-to-date conversion helpers in Portico.

### Phase 3: Desktop Shell and Home

- Problems solved: Turns the verified data/report core into a usable desktop
  dashboard and proves the configuration-driven presentation approach.
- Included requirements: REQ-002, REQ-003, REQ-004, REQ-008, REQ-009,
  REQ-014, REQ-017.
- Concrete delivery:
  - Roci MonoGame host, startup/loading/error states, and DashboardSession.
  - Configured left drawer, top bar, page selection, configured filter control
    rendering, and responsive layout.
  - Home dashboard with date-aware net-worth chart, allocation bars, account
    cards/sparklines, and safety metrics from the existing Portico rules.
  - Local demo run path and interaction/capture tests for the Home screen.
- Sub-phase 3A, shell:
  - Implement the CLI composition root and desktop state transitions.
  - Render only configuration-defined visible pages/items. Keep page name and
    widget ID stable through the renderer.
  - Exercise load, first-load error, reload failure with stale snapshot, drawer
    open/select/dismiss, and a narrow window.
- Sub-phase 3B, Home:
  - Map typed Home report values to existing Roci charts/cards and new date
    support.
  - Configure title, cards, chart order, lookback control, and safety
    presentation through TOML.
- Expected edits:
  - Portico.App host/session/renderer and desktop test project.
  - Dashboard Home report/definition and configuration examples.
  - App visual-test fixture/capture setup and user setup documentation.
- Validation:
  - task test:desktop
  - task test:finance
  - task visual-test
  - task lint
  - task build:strict
  - task test
  - git diff --check
- Exit criteria:
  - portico run with local demo data opens Home without external connectivity.
  - The slide-out drawer selects a configured page and safely dismisses.
  - Home metrics/charts match the same report fixture values used in Phase 1.
  - Wide, narrow, open-drawer, closed-drawer, no-data, and first-load-error
    visual cases have approved evidence.
- Rollback or fallback: Revert the app shell/Home commits while retaining Phase
  1 data tests and separately reviewable Phase 2 Roci work.
- Cleanup: Remove any hard-coded sample page list, display-only calculation, or
  duplicate Home layout after the TOML renderer replaces it.

### Phase 4: Standard Dashboard Pages

- Problems solved: Delivers the views that use the existing Roci chart/grid
  surface plus the Phase 2 date/category additions.
- Included requirements: REQ-002, REQ-004, REQ-008, REQ-009, REQ-017,
  REQ-020.
- Concrete delivery:
  - Income and Savings, Spending by Category, Year over Year, Merchant
    Analysis, Budget, Top Transactions, and Data Health pages.
  - Configured controls, selected states, tables, no-data states, and page
    descriptions for each view.
- Sub-phase 4A, monthly/category views:
  - Add Income and Savings and Spending by Category using category bars plus
    line overlays and linked selected-month/category state.
  - Add Year over Year using existing lines/points and reference guides.
- Sub-phase 4B, operational views:
  - Add Merchant Analysis, Budget, Top Transactions, and Data Health.
  - Use date data for daily/transaction views, ordinary horizontal bars/
    sparklines/tables where already suitable, and no custom chart drawing.
- Expected edits:
  - Named page report builders, page renderer mappings, page TOML definitions,
    finance/report fixtures, interaction tests, and visual cases.
- Validation:
  - task test:finance
  - task test:desktop
  - task visual-test
  - task lint
  - task build:strict
  - task test
  - git diff --check
- Exit criteria:
  - All seven pages appear only when configured and in configured drawer order.
  - Every declared filter changes precisely its bound report/widget.
  - Each chart/table has an exact report fixture and a visual/no-data fixture.
  - Dashboard data grids show their private synthetic test rows correctly and
    normal logs still reveal no raw values.
- Rollback or fallback: Revert a page-sized commit without changing the source
  contract or another page. A blocked visual is recorded as a Roci gap, not
  solved by an untested app renderer.
- Cleanup: Delete copied chart setup and page-only filter logic once the shared
  typed renderer/binding path handles it.

### Phase 5: Advanced Roci Components and Advanced Pages

- Problems solved: Finishes the two Portico pages that prove interval and
  two-axis-cell visualization needs.
- Included requirements: REQ-002, REQ-008, REQ-009, REQ-010, REQ-017,
  REQ-020.
- Concrete delivery:
  - On the companion Roci branch: generic date range bars, typed date guides
    needed by timelines, and categorical heatmap cells with labels/hits.
  - In Portico: Subscriptions and Financial Independence views, including
    lifecycle timeline, current-date guide, projection/depletion display,
    funding bars, and sensitivity heatmap.
- Sub-phase 5A, reusable Roci features:
  - Implement range bar records, range series authoring, layout, hit tests,
    tooltip rules, validation, and a focused Roci sample.
  - Implement heatmap cells, color scale/labels, two category axes, hit tests,
    and focused Roci sample.
  - Verify static inputs are owned and no per-frame input enumeration or
    allocation path is introduced.
- Sub-phase 5B, consumer pages:
  - Connect Subscription lifecycle inference/observed data to range bars and
    date guides through a typed report.
  - Connect FI projection and sensitivity-grid calculations to date and heatmap
    components. Keep the clock injected and grid ordering stable.
- Expected edits:
  - Companion Roci components, docs, samples, tests, and visual evidence.
  - Portico Subscription/FI reports, renderer mappings, TOML page/widget
    definitions, interaction fixtures, and app captures.
- Validation:
  - In Roci: focused component tests, task lint, task build:strict, task test,
    task samples:visual-test:ui-visualizations, and git diff --check.
  - In Portico: task test:finance, task test:desktop, task visual-test,
    task lint, task build:strict, task test, and git diff --check.
- Exit criteria:
  - Range start/end/category identity remains visible in tooltip and hit
    results, invalid ranges fail atomically, and the current-date guide is
    typed rather than a numeric conversion.
  - Heatmap cells retain category/value identity, show configured labels/scale,
    and resolve stable hits.
  - Subscriptions and FI work from local demo and mocked source data.
  - The full ten-view inventory in FIXTURES is complete.
- Rollback or fallback: Revert advanced Roci and consumer commits together only
  if their API cannot meet Roci review. Do not keep a Portico canvas/texture
  substitute.
- Cleanup: Remove temporary app feature flags or numeric date shims as native
  Roci features replace them.

### Phase 6: Hardening, Documentation, and Publish Proof

- Problems solved: Turns working features into a maintainable, reviewable
  result and records what packaging can genuinely support.
- Included requirements: REQ-015, REQ-016, REQ-017, REQ-018, REQ-019,
  REQ-020.
- Concrete delivery:
  - Final setup/config/CLI/cross-platform documentation in plain English.
  - Whole-suite tests and review of quality, abstraction, test coverage,
    performance, documentation, and visual readability.
  - Fix every P1/P2 review finding. Fix a small P3 finding in this phase or
    record it as deferred work. Re-run the affected review/check, then run one
    aggregate validation pass.
  - Publish proof for normal desktop output, then self-contained win-x64 and
    linux-x64 attempts.
  - Completed PLC validation notes and a clear list of intentionally deferred
    work.
- Expected edits:
  - README, configuration guide, CLI help, Taskfile, docs, capture inventory,
    and completed packet evidence.
  - Only justified code fixes found by the validation work.
- Validation:
  - task format
  - task lint
  - task build:strict
  - task test
  - task visual-test
  - task publish:win-x64
  - task publish:linux-x64
  - Matching Roci full gates for final component source.
  - git diff --check
- Exit criteria:
  - All required Portico and Roci tests pass from documented commands.
  - Visual changes have been inspected; no baseline was refreshed merely to
    accept a defect.
  - Docs explain public-sheet setup, local demo, TOML schema, CLI precedence,
    privacy limits, Roci contribution boundary, and deferred features.
  - Publish results record actual outputs and missing native dependencies, if
    any. Native AOT is marked supported only if a real published app was run.
- Rollback or fallback: Code fixes are independently reversible. Failed
  self-contained publishing leaves the normal desktop path intact and is
  recorded as a packaging limitation, not treated as a dashboard failure.
- Cleanup: Remove debug logging, copied values, obsolete fixture generators,
  unused Task targets, and stale documentation before completion.

## Cross-Phase Risks

| Risk | Affected phases | Mitigation | Owner |
| --- | --- | --- | --- |
| C# port changes a hidden Python financial convention | 1, 3-5 | Define sign, date, rounding, and sorting rules with exact synthetic cases before connecting UI | Portico |
| Public sheet export changes or a tab URL is wrong | 0-1, 3-6 | Explicit URLs, strict URL/header validation, doctor, redacted errors, local demo source | Portico |
| A needed Roci feature exposes a deeper renderer/state issue | 2, 5 | Build and validate in companion Roci branch first; stop rather than add app-only custom drawing | Roci |
| Dashboard TOML becomes a second programming language | 0, 3-5 | Keep a finite typed page/widget/filter catalog and reject arbitrary expressions | Portico |
| Visual captures conceal incorrect totals | 1, 3-6 | Treat finance/report expected-value tests as the numerical oracle; captures verify layout and interaction | Portico |
| Local Roci source reference breaks a clean clone | 2-6 | Make reference optional/documented; use a checked reference after Roci acceptance; test normal clean build | Portico |
| Native graphics dependencies block self-contained publish | 6 | Test normal output first, record native runtime facts, and defer Native AOT without blocking app work | Portico |

## Completion Criteria

- [ ] Every Must requirement from SRD appears in at least one phase.
- [ ] The app can load valid public-sheet URLs or local demo CSV without OAuth.
- [ ] All ten views and every item in the page inventory have report, interaction,
      and visual evidence.
- [ ] All financial calculator families have exact normal and edge-case tests.
- [ ] Roci additions are reusable, fluent, tested, sampled, and independently
      reviewable.
- [ ] Validation uses Task commands rather than ad hoc equivalent commands.
- [ ] Documentation/readability cleanup and privacy checks are complete.
- [ ] Packaging results are recorded accurately, including any deferral.
- [ ] The final packet records evidence, residual risks, and follow-up work.
