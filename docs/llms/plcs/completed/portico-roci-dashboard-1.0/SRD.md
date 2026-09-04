# Portico Dashboard in Roci 1.0 Software Requirements Document

## Document Control

- Lifecycle status: Complete
- PLC packet: [README.md](README.md)
- Owner: Portico and Roci maintainers
- Reviewers: Portico maintainer; Roci maintainer
- Last updated: 2026-09-04
- Related SADD: [SADD.md](SADD.md)
- Related implementation plan: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

## Executive Summary

Portico is a personal-finance dashboard whose current Streamlit version reads
four spreadsheet tabs and presents ten views. This work creates a C# desktop
version using Roci. The goal is both a faithful dashboard and a practical test
of Roci's data-visualization language. Where a needed visualization is awkward
or missing, the fix belongs in Roci rather than in a Portico-only drawing hack.

The finished dashboard accepts public, read-only Google Sheets tab URLs or the
checked-in local CSV fixture. Production hosting and user accounts are not part
of this release.

## Delivery Record

The delivered experiment has a configuration-defined page menu, ten configured
pages, local CSV and public Google Sheets CSV sources, named C# reports, and a
Roci desktop renderer. Its chart vocabulary includes metrics, tables, lines,
areas, bars, category bar/line overlays, scatter plots, timelines, heatmaps,
and sparklines.

The intended drawer composition worked with `AnchorOverlay` and `MenuList`, so
Roci did not gain a generic drawer. The companion Roci branch instead adds the
four actual framework gaps: typed date/category chart data, category overlays,
timeline ranges with typed date guides, and heatmap cells.

This is a functional experimental dashboard, not a pixel-for-pixel replacement
for every Streamlit interaction. The remaining Streamlit-specific linked
selection and page-detail variants are listed as later product work in the PLC
README. The Roci component visual suite is the visual regression proof; the
Portico app uses retained-tree and interaction tests rather than a separate
app screenshot baseline.

## Audience

This document is for the person implementing the Portico desktop app, the
person reviewing Roci component changes, and anyone testing financial results.
Readers should know the existing Portico workbook and configuration files, and
the Roci `UiBuilder` fluent style.

## References

- `docs/architecture.md` in this repository.
- `config.toml`, `portico-demo.toml`, `src/config.py`, and `src/sheet_config.py`
  in this repository.
- `Home.py` and `app_pages/` in this repository.
- `../roci/docs/llms/plcs/PLC-README-template.md`, `SRD-template.md`,
  `SADD-template.md`, and `IMPLEMENTATION_PLAN-template.md`.
- `../roci/docs/articles/api-language-guide.md` and
  `../roci/src/Roci.Ui/UiBuilder.Widgets.Charts.Fluent.cs`.

## Consumer And Developer Outcomes

| Outcome | Success signal | Notes |
| --- | --- | --- |
| A person can open their public workbook in the desktop dashboard | `portico run` validates four URLs, loads the CSV exports, and renders data without OAuth. | Credentials are never requested. |
| A person can move between familiar Portico views | The left drawer names Home and all nine current pages; selection changes the displayed page. | Drawer works at narrow and wide window sizes. |
| A person can use filters to change a view | A configured control changes the intended report, chart, table, or selected period only. | Filter state is local to the desktop process. |
| A maintainer can change presentation without changing finance code | TOML changes page order, labels, widgets, layout, and declared filters; invalid TOML fails with a useful location and reason. | TOML cannot run formulas or arbitrary code. |
| A maintainer can trust money calculations | Synthetic table tests cover normal and edge cases with exact expected results. | Currency remains `decimal` until the chart boundary. |
| A Roci user gains generally useful visualization support | Component changes are separately tested and sampled in Roci, then consumed by Portico through fluent calls. | No Portico-specific type leaks into Roci. |

## System Overview

The desktop executable reads configuration, resolves public spreadsheet URLs,
loads four CSV tabs, normalizes them into an in-memory portfolio snapshot, and
calculates typed page reports. A Roci host renders a configuration-selected page
and its controls. User input creates a new page-filter state and recomputes the
affected report; it does not alter the spreadsheet.

There are two codebases with separate ownership:

1. The Portico worktree contains the executable, finance rules, adapters,
   configuration, tests, and dashboard views.
2. A companion Roci branch contains only reusable UI/chart component changes,
   their samples, tests, and documentation.

## Scope And Non-Scope

- In scope: a C# Roci desktop dashboard, public Google Sheets CSV loading,
  local demo CSV loading, all ten current dashboard views, TOML-driven page
  layout/filters/charts, a slide-out left drawer, a small CLI, strong finance
  tests, and the necessary reusable Roci components.
- Out of scope: Discord summaries, Docker or other containers, browser demo,
  Streamlit replacement for every operational feature, OAuth, private Sheets
  API access, editing sheets, write-back, multi-user accounts, and remote data
  storage.
- Compatibility target: the current Portico `config.toml` and
  `portico-demo.toml` calculation sections; the four worksheet concepts
  Transactions, Balance History, Categories, and Accounts; the ten dashboard
  views listed in [FIXTURES.md](FIXTURES.md#page-and-visualization-inventory).
- Explicit non-goal: an embedded formula, SQL, expression, or templating
  language in TOML.

## Stakeholders And Affected Systems

- A person who supplies public spreadsheet URLs and views their finances.
- Portico maintainers who change configuration, finance rules, and dashboard
  presentation.
- Roci maintainers who review reusable navigation and chart components.
- The Google Sheets CSV export endpoint, treated as an untrusted external
  input.
- Task, mise, .NET, MonoGame DesktopGL, and Roci project-reference tooling.

## Requirements

| ID | Priority | Type | Requirement | Rationale | Acceptance criteria |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | Must | Delivery | Keep Portico application work in the requested linked worktree and put Roci framework changes in a separate clean companion worktree and branch. | Prevents mixed ownership and makes framework review possible. | Each repository has a clean, reviewable diff and neither copies source from the other. |
| REQ-002 | Must | Functional | Deliver a desktop C# executable using Roci that can show Home plus Income and Savings, Spending by Category, Year over Year, Subscriptions, Merchant Analysis, Budget, Top Transactions, Financial Independence, and Data Health. | These are the current dashboard surface. | Every view has a page definition, route, report, and test fixture. |
| REQ-003 | Must | Functional | Provide a left slide-out navigation drawer with a menu trigger, page items, current-page indication, dismissal, and keyboard/input-safe behaviour. | The requested navigation should work without using tabs for the entire app. | Tests cover open, select, dismiss, and narrow-width behaviour; visual capture shows drawer and closed states. |
| REQ-004 | Must | Configuration | Read the current Portico calculation configuration unchanged and add a separate versioned `dashboard.toml` for page order, text, layout, widgets, colors, filter controls, and defaults. | The dashboard should be configuration-driven without turning TOML into code or breaking the current Python loader. | Valid finance and dashboard files map to typed records; invalid IDs, duplicate IDs, unknown widget kinds, bad options, and bad defaults fail before the window opens. |
| REQ-005 | Must | Data | Load the four public Google Sheets tabs from explicit HTTPS Google Sheets URLs, export each as CSV, and require no OAuth. | This matches the current app and the agreed access model. | URL/parser tests cover valid share URLs, missing/invalid IDs or gids, HTTP failure, CSV failure, and no live-network unit test. |
| REQ-006 | Must | Data | Support a local CSV/demo source with the same normalized schema as the sheet source. | It makes development and deterministic tests possible without real finances. | The same report fixtures pass against normalized local and mocked-sheet inputs. |
| REQ-007 | Must | Functional | Preserve the existing named transaction sets, filter sets, merchant aliases, lookbacks, thresholds, budget, subscriptions, financial-safety, and financial-independence settings. | Users can begin from the existing configuration instead of translating finance rules. | Parser and report tests cover every supported configuration section; dashboard-only ignored legacy fields are called out in diagnostics. |
| REQ-008 | Must | Functional | Render configured filter controls and apply them only to the reports/widgets that declare their binding. | Controls must have clear and limited effects. | UI and report tests prove filter changes, reset/default behaviour, and linked selections. |
| REQ-009 | Must | Visualization | Recreate every current Portico visualization and table with the same data meaning, including layered charts, guides, sparklines, rank bars, scatter points, timelines, heatmap, data grids, and metric cards. | The experiment is about real visualization coverage, not a token dashboard. | The page inventory in FIXTURES has one report and visual/interaction proof per item. |
| REQ-010 | Must | Framework | Reuse Roci's existing overlay and menu primitives first. Add only the missing reusable support for a generic drawer, date-aware chart data/axes, category-aligned line/bar overlays, interval/range bars, and heatmap cells when current components cannot express the Portico view cleanly. | Portico should expose and fix framework sharp edges without adding Portico concepts to Roci. | Each Roci addition has fluent API compilation tests, behaviour tests, a sample, and a Portico use before it is considered complete. |
| REQ-011 | Must | Correctness | Keep financial values as `decimal` and dates as `DateOnly` in finance/report code; convert only at the Roci chart adapter. | Avoids binary rounding and timezone shifts in financial results. | Tests cover exact money totals, rounding at presentation, leap day/month boundaries, negative/refund values, and zero denominators. |
| REQ-012 | Must | Correctness | Put financial calculations in pure, named C# functions with table-driven expected-result tests. | A view should not be the only place a calculation can be verified. | Each calculation family has named normal, boundary, and invalid-data cases in the fixture matrix. |
| REQ-013 | Must | Diagnostics | Provide `run` and `doctor` CLI commands with `--config`, `--dashboard`, `--secrets`, source and URL overrides, clear exit codes, and machine-readable `doctor --output json`. | The desktop app needs a practical setup and diagnosis path. | Help, exit-code, precedence, redaction, and JSON tests pass; data is on stdout and diagnostics are on stderr for JSON mode. |
| REQ-014 | Must | Architecture | Keep UI rendering, dashboard/report calculation, external adapters, and finance domain code in one-directional project boundaries. | Loose coupling makes calculations and configuration testable without graphics or network access. | Project-reference tests and source review show no Roci/HTTP/TOML dependency in finance code. |
| REQ-015 | Must | Tooling | Use the sibling Roci Task and mise conventions for restore, format/lint, build, test, visual test, and publish checks. | One documented command surface reduces setup drift. | `task lint`, `task build:strict`, `task test`, and documented focused tasks work from a clean checkout. |
| REQ-016 | Must | Testing | Use synthetic, non-sensitive fixtures and test more than happy paths for each financial calculation and source adapter. | Passing visual screens alone cannot prove finance results. | Fixture matrix includes income, spending, transfers, refunds, aliases, exclusions, uncategorized entries, missing balances, period edges, ties, and empty data. |
| REQ-017 | Must | Quality | Capture representative wide and narrow dashboard frames and test configured user interactions without refreshing a failing baseline as a fix. | Visualization regressions need observable evidence. | Portico and Roci visual suites compare approved baselines; a changed capture is investigated. |
| REQ-018 | Must | Security | Do not log raw sheet URLs, spreadsheet contents, or secret-file values. | Financial data and links should not leak through diagnostics. | Redaction tests prove `doctor`, failures, and exceptions show source names and safe reasons only. |
| REQ-019 | Should | Packaging | Keep project layout compatible with self-contained `win-x64` and `linux-x64` publishing; prove profiles only after the normal desktop build works. | It keeps the later static-binary goal open without blocking core work. | Final phase records publish results and any MonoGame/native limitation. |
| REQ-020 | Must | Documentation | Document setup, source formats, TOML schema, CLI, calculation conventions, Roci contribution boundary, and deferred work in plain English. | This is an experimental app that must still be understandable. | README/docs examples compile or are tested; plain-language review has no unclear term that changes behaviour. |

## Requirement Quality Checklist

- [x] Every Must requirement has acceptance criteria.
- [x] Every requirement states one behaviour or constraint.
- [x] Vague terms are paired with a specific inventory or validation path.
- [x] Implementation details appear only where they are required constraints.
- [x] Deferred packaging work has an owner and resolution phase.

## Interfaces, Data, States, And Modes

### Inputs

- `config.toml` or `portico-demo.toml`: existing checked-in, non-secret
  financial calculation settings.
- `dashboard.toml`: checked-in, non-secret desktop page and widget settings.
- `portico.secrets.toml`: ignored local sheet URLs.
- CLI overrides: explicit local source directory or individual named sheet URL.
- Four CSV tabs: Transactions, Balance History, Categories, and Accounts.

### Application states

`Starting` → `Validating configuration` → `Loading source` → `Ready`.

If validation or loading fails, the app stays on a diagnostic screen with a
safe explanation and the command needed to run `doctor`. It does not show a
partial financial dashboard that mixes fresh and failed sources. A deliberate
reload replaces the complete in-memory snapshot only after all required inputs
validate.

### Command modes

- `portico run`: starts the desktop dashboard.
- `portico doctor`: validates settings, source location, URL shape, and headers
  without opening a dashboard window.

The detailed option contract is in [SADD.md](SADD.md#configuration-and-cli).

## Quality Attributes

| Attribute | Scenario | Measure |
| --- | --- | --- |
| Determinism | A fixture workbook is loaded twice. | Both normalized snapshots and report outputs compare equal. |
| Correctness | A calculation sees normal, empty, negative, boundary, and invalid inputs. | Named expected-result tests pass without rendering a UI. |
| Privacy | `doctor` receives a URL or source failure. | Output names the logical sheet and failure class, never raw URL/content. |
| Responsiveness | A user changes a filter after data has loaded. | Only affected report/view models recompute; TOML parsing and CSV fetch do not run per frame. |
| Maintainability | A page label or widget layout changes. | A typed TOML change is enough when the report kind already exists. |
| Usability | Window is narrow or drawer is open. | The retained-tree tests prove the page remains reachable, dismissible, and clearly labelled. |
| Testability | Unit tests run in CI. | No network, graphics window, real workbook, or secret file is required. |
| Compatibility | A user starts from current Portico configuration. | Supported calculation sections load unchanged; excluded weekly summary settings receive a clear dashboard-only notice. |

## Phased Delivery

| Phase | Goal | Included requirements | Exit criteria |
| --- | --- | --- | --- |
| 0 | Runnable project and setup checker | 001, 004, 013-015, 018, 020 | `doctor` validates a demo configuration and produces redacted text/JSON output. |
| 1 | Deterministic data and finance core | 005-007, 011, 012, 016 | Local/demo and mocked-sheet data produce verified typed reports without a UI. |
| 2 | Roci baseline additions | 003, 009-010, 017 | The existing overlay/menu composition is proven or a generic drawer is added; typed date/category chart additions pass normal Roci samples and tests. |
| 3 | Desktop shell and Home view | 002-004, 008, 009, 014, 017 | Roci app opens Home with a configured drawer, controls, and native date charts. |
| 4 | Standard dashboard views | 002, 004, 008-009, 017 | Income, Spending, YoY, Merchant, Budget, Top Transactions, and Data Health work with tests/captures. |
| 5 | Advanced Roci work and view parity | 002, 008-010, 017, 020 | Range bars and heatmap land in the companion branch; Subscriptions and Financial Independence use them; all ten views meet their inventory. |
| 6 | Whole-app hardening and publish proof | 015-020 | Broad checks, docs, visual proof, and publish evidence are complete. |

## Traceability

| Requirement | Design section | Validation method | Evidence target |
| --- | --- | --- | --- |
| REQ-001 | [Repository boundaries](SADD.md#repository-boundaries) | Git/worktree inspection | Separate Portico and Roci diffs |
| REQ-002, REQ-009 | [Page reports and rendering](SADD.md#page-reports-and-rendering) | Unit, integration, visual | Page inventory fixtures |
| REQ-003, REQ-010 | [Roci work](SADD.md#roci-work-owned-by-the-companion-branch) | Roci API/unit/sample/visual | Drawer and chart fixture sets |
| REQ-004, REQ-007 | [Configuration](SADD.md#configuration-and-cli) | Parser/validation tests | TOML fixture cases |
| REQ-005, REQ-006, REQ-018 | [Data loading](SADD.md#data-loading-and-normalization) | Adapter tests with fake HTTP | URL, header, redaction cases |
| REQ-008 | [Filter state](SADD.md#filter-state-and-interaction) | Report and UI interaction tests | Bound-control cases |
| REQ-011, REQ-012, REQ-016 | [Calculation design](SADD.md#financial-calculation-design) | Table-driven unit tests | Finance matrix |
| REQ-013, REQ-015 | [Tooling](SADD.md#tooling-packaging-and-diagnostics) | CLI and Task checks | Command contract tests |
| REQ-014 | [Building blocks](SADD.md#building-blocks) | Project/source review | Dependency diagram and build |
| REQ-017 | [Test architecture](SADD.md#test-architecture) | Visual capture comparison | Wide/narrow and Roci samples |
| REQ-019 | [Packaging](SADD.md#tooling-packaging-and-diagnostics) | Publish smoke test | Runtime-specific publish record |
| REQ-020 | [Readability](SADD.md#readability-and-documentation) | Docs/plain-language review | Updated setup/config guide |

## Risks, Assumptions, And Open Questions

| Item | Type | Impact | Owner | Resolution plan |
| --- | --- | --- | --- | --- |
| A public Google Sheet may stop exposing CSV or change columns | Risk | App cannot load a source | Portico | Validate URL/header errors early; keep a local demo source; do not scrape viewer HTML. |
| Existing Python calculations have implicit sign/period rules | Risk | A visually correct report could be numerically wrong | Portico | Make each rule explicit in C# tests with synthetic expected values before wiring its view. |
| Roci chart work may uncover more missing components | Risk | Advanced pages may block | Roci | Add only page-proven reusable components, test them upstream, and keep page work behind typed page-result records. |
| `weekly_summary` has no dashboard meaning | Assumption | Existing config has an unused section | Portico | Parse it for compatibility and emit a one-time notice; do not implement notifications. |
| Static native publishing may conflict with graphics dependencies | Deferred | Packaging scope | Portico | Test normal publish first, then self-contained profiles; evaluate Native AOT only from measured results. |

## Validation

Run the documented Task commands from the Portico worktree, including focused
finance, adapter, CLI, desktop, and visual suites before the broad suite.
Run the matching focused Roci tests and samples in the companion Roci worktree
for every framework change. Do not use actual financial sheet URLs in automated
tests. Finish with `task lint`, `task build:strict`, `task test`, visual checks,
documentation checks, and `git diff --check`.

## Definition Of Done

- [x] Every Must requirement is implemented or explicitly deferred in the PLC
      README.
- [x] The ten-page dashboard and each implemented visualization family have
      report, retained-tree, interaction, or Roci visual evidence.
- [x] Calculation tests give exact expected outputs for normal and edge cases.
- [x] Roci changes are independently reviewed, tested, sampled, and documented.
- [x] Setup, CLI, TOML, and deferred scope documentation are current.
- [x] Remaining risks and packaging results are recorded in the completed packet.
