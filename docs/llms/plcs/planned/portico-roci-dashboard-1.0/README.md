# Portico Dashboard in Roci 1.0 PLC Packet

## Lifecycle

- Status: In progress
- Folder: `docs/llms/plcs/planned/portico-roci-dashboard-1.0/`
- Owner: Portico and Roci maintainers
- Created: 2026-09-03
- Last updated: 2026-09-04
- Current phase: Phases 0 and 1 are implemented in the Portico worktree; Phase 2 Roci component work is in progress
- Portico worktree: `nccurry/roci-portico-plc` in `../portico-roci-rebuild`
- Companion Roci work: `nccurry/portico-roci-components` in
  `../roci-portico-components`, created cleanly from
  `2404411b80c65bcb2e0f07f59492a875456d6074`

## Summary

Build a C# desktop dashboard that recreates Portico's ten current dashboard
views with Roci. It reads the same four-sheet financial workbook shape as the
Streamlit app, keeps the existing TOML calculation settings unchanged, and
reads page layout, filters, and chart choices from a separate `dashboard.toml`.

This is intentionally a dashboard-only project. It does not include the
Discord summary, containers, browser demo, OAuth, write-back, or multi-user
work. The useful first result is a desktop app that can validate a public Google
Sheets setup, load it, and show the Home dashboard through a left slide-out
page menu. Later phases fill in the rest of the views and turn the Roci gaps
found during that work into ordinary reusable Roci components.

The app will not invent a formula language. Each TOML widget names a known,
typed dashboard report such as `monthly-cash-flow` or `fi-sensitivity`. C# owns
the calculation and its tests; TOML selects and labels the report, its layout,
and its filters.

## Problem Evidence

- The current Portico app has Home plus nine page modules, and its
  `config.toml` already owns transaction sets, aliases, lookbacks, thresholds,
  budgets, subscriptions, safety, and financial-independence inputs. Its Python
  loader rejects unknown top-level TOML tables, so a dashboard section cannot
  be added to that file without breaking the existing app.
- Its visualization work is mostly defined in page code, so changing a label,
  chart order, filter control, or page layout requires code even when the
  financial rule is already configuration-driven.
- Roci already has fluent numeric line, area, scatter, bar, reference-guide,
  sparkline, tab, menu, and grid building blocks. It does not currently have a
  first-class navigation drawer, date axis/data path, categorical line values
  that can share an axis with bars, range bars for timelines, or a heatmap
  series. Those are real requirements for Portico rather than speculative
  additions.

## Packet Contents

- [SRD.md](SRD.md): scope, requirements, acceptance criteria, and traceability.
- [SADD.md](SADD.md): project boundaries, TOML shape, data flow, Roci work, and
  test design.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): phased delivery with a
  concrete output from every phase.
- [FIXTURES.md](FIXTURES.md): data, calculation, UI, and Roci-component test
  cases.

## Decision Snapshot

| Decision | Status | Rationale | Link |
| --- | --- | --- | --- |
| Use a standalone C# desktop app plus a separate Roci change branch | Accepted | The dashboard is a real Roci consumer, while framework fixes remain reviewable and reusable on their own. | [SADD: Repository boundaries](SADD.md#repository-boundaries) |
| Read public Google Sheets through their CSV export URLs | Accepted | It matches the current app, needs no OAuth, and works with user-supplied public URLs. | [SADD: Data loading](SADD.md#data-loading-and-normalization) |
| Preserve Portico's calculation TOML and add a separate typed dashboard TOML | Accepted | `config.toml` and `portico-demo.toml` stay valid for the Python app; `dashboard.toml` owns only desktop presentation. | [SADD: Configuration](SADD.md#configuration-and-cli) |
| Use a left slide-out page drawer | Accepted | First compose it from Roci's existing overlay and menu primitives. Add a reusable generic drawer only when that proof shows a real gap. | [SADD: Desktop shell](SADD.md#desktop-shell-and-navigation) |
| Add only the chart features Portico proves necessary | Accepted | Date series, category-aligned overlays, range bars, and heatmaps are each exercised by a named Portico view. | [SADD: Roci work](SADD.md#roci-work-owned-by-the-companion-branch) |
| Exclude notifications, containers, browser demo, OAuth, and write-back | Accepted | They are outside the dashboard experiment and would hide the visualization work behind unrelated systems. | [SRD: Scope](SRD.md#scope-and-non-scope) |
| Start with normal .NET desktop publishing | Accepted | It is the shortest route to a working app. Self-contained Windows/Linux publishing is planned as a later proof, not a Phase 1 constraint. | [SADD: Packaging](SADD.md#tooling-packaging-and-diagnostics) |

## Package And API Impact

- Portico gains four C# projects: pure finance code, dashboard/report code,
  adapters for TOML and sheet CSV, and a Roci desktop host with a small CLI.
- The Portico application consumes Roci through normal project references while
  the companion branch is active. It must not copy Roci source into this repo.
- The companion Roci branch may add public `Roci.Ui` components for a generic
  drawer, temporal/category chart data, range bars, and heatmaps. Existing
  `MenuList` composes the page items. Each addition follows Roci's fluent
  `UiBuilder` language and includes its own sample and tests.
- No public network endpoint, server, OAuth client, database, container, or
  browser build is added.

## Review Changes And Evidence

The 2026-09-04 design review used the current Portico configuration loader and
the current Roci source, API guide, and Task command list. It made these
concrete corrections before implementation:

| Finding | Plan change |
| --- | --- |
| Portico's Python loader rejects unknown top-level TOML tables. | Keep financial settings in the existing files. Put desktop-only page and widget settings in `dashboard.toml`, selected with `--dashboard`. |
| The draft dashboard example referred to `lookback.income_savings` and `income_savings.savings_rate_target`, neither of which exists in the current files. | Use `lookback.default_lookback_months` and `income_savings.target_rate`; add a config-reference fixture. |
| `template = "income-savings"` repeated the page ID without adding behaviour. | Remove `template`; typed page/report code validates the page ID and each configured widget kind. |
| Roci already has `AnchorOverlay`, `Modal`, and `MenuList`, but not a slide-out drawer primitive. | Prove the shell with existing components first. If they cannot provide a left slide, scrim dismissal, and input isolation cleanly, add a generic `Drawer`; do not add Portico-specific navigation items to Roci. |
| The Roci task surface has `task test:visual` and `task samples:visual-test`, not the planned scoped sample command. | Use the real Task commands and focused project tests in Roci validation. |
| Roci's default checkout contains unrelated untracked PLC work. | Create the required clean companion worktree from the chosen Roci commit. Do not develop in the default checkout. |

The four Portico project boundaries remain because each removes a current
dependency: Finance has no I/O or UI, Dashboard has no Roci or parser types,
Adapters owns external formats, and App is the only desktop/Roci host.

## Review Verdict

Ready to implement. The packet has a concrete configuration boundary, an exact
clean Roci base, commands that exist, and phase exit checks that test finance
results before UI rendering. The remaining design work is intentionally limited
to the public Roci API shape exposed by the drawer proof and component tests.

## Current Open Questions

No open question blocks the first implementation phase. The two deliberately
deferred choices below have safe defaults.

| Question | Impact | Owner | Resolution plan |
| --- | --- | --- | --- |
| Which publish profiles become supported releases? | Packaging only | Portico maintainer | Start with framework-dependent desktop publish, then prove self-contained `win-x64` and `linux-x64` in the final phase. Native AOT is optional after its graphics compatibility is measured. |
| Should a future version discover sheet tabs from a workbook URL? | Convenience only | Portico maintainer | Keep explicit tab URLs now. Do not depend on Google viewer HTML parsing; add discovery only with a stable API or a separate approved design. |

## Planning Readiness Checklist

- [x] Scope and non-scope are explicit.
- [x] Must requirements are testable and have acceptance criteria.
- [x] Major alternatives and tradeoffs are recorded.
- [x] Quality attributes are measurable or inspectable.
- [x] Package boundaries and dependency impact are explicit.
- [x] Roci fluent-builder rules are explicit for every planned Roci widget.
- [x] Documentation, readability, and abstraction reuse expectations are clear.
- [x] SRD maps Must requirements to acceptance criteria and validation.
- [x] Implementation plan has phase exit criteria.
- [x] Deferred work is visible and not required by the first implementation phase.

## Implementation Checklist

- [x] Record the active Portico and Roci branch names in the packet.
- [ ] Keep the SRD and SADD current when an implementation decision changes.
- [ ] Record validation evidence as phases complete.
- [ ] Remove replaced experimental code as the typed implementation lands.
- [ ] Move the packet to `completed/` only after all required validation passes.

## Validation Evidence

| Date | Check | Result | Notes |
| --- | --- | --- | --- |
| 2026-09-03 | Read Portico architecture, configuration, loader, and all page modules | Pass | Established the dashboard inventory and existing configuration behaviour. |
| 2026-09-03 | Read Roci PLC templates, chart code, samples, build tooling, and authoring rules | Pass | Confirmed reusable chart composition and the specific missing components. |
| 2026-09-03 | Inspect current Roci chart data and bar geometry | Pass | Confirmed numeric-only connected data, bar-only categories, zero-baseline bars, and no interval or heatmap series. |
| 2026-09-03 | CQ sheet-loader check | Pass | Explicit per-tab URLs are safer than parsing undocumented Google viewer metadata. |
| 2026-09-04 | PLC accuracy review | Pass | Verified strict current-config parsing and actual field names, current Roci menu/overlay/chart APIs, the actual Roci Task commands, and the need for a clean companion worktree. |

## Completion Notes

Not started. This packet is the agreement for the implementation work; it is
not a claim that the desktop app or Roci additions exist yet.
