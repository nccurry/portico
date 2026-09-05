# Portico Roci Layout Rebuild 1.0 PLC Packet

## Lifecycle

- Status: In progress
- Created: 2026-09-04
- Current phase: Phase 2 — add navigation rail and global state
- Owner: Portico maintainers
- Target worktree: `../portico-roci-rebuild`
- Target branch: `nccurry/roci-portico-plc`
- Roci branch: no changes in this PLC

## Implementation Progress

Phase 0 completed on 2026-09-04.

- The source navigation, page regions, controls, and Roci component decisions
  are recorded in [DISCOVERY.md](DISCOVERY.md).
- A test-only capture host now creates deterministic demo sessions and captures
  all ten current pages at 1500 by 1000 and 1024 by 720.
- `task roci:visual` writes and verifies 20 PNG files in
  `artifacts/visual/portico-current`.
- The merged phase passed `task roci:restore`, `task roci:test:desktop`,
  `task roci:visual`, `task roci:format`, `task roci:lint`,
  `task roci:build:strict`, and `git diff --check`. The two Phase 0 child
  reviews also passed `$audit-codebase`; the capture review passed
  `$frontend-design-review` for its narrow Phase 0 scope.

Phase 1 completed on 2026-09-04.

- The old light top bar and overlay drawer were replaced with a dark flex shell:
  fixed rail, growing main column, fixed page header, and vertically scrolling
  page body.
- [PorticoSkin.cs](../../../../../src/Portico.App/Ui/PorticoSkin.cs) now owns
  the Portico colors, spacing, text styles, action styles, semantic states, and
  chart palette.
- Wide and narrow layout tests prove the 232-pixel rail, full-height shell,
  scroll boundary, and deliberate card wrapping at 1024 by 720.
- The merged phase passed `task roci:format`, `task roci:lint`,
  `task roci:build:strict`, `task roci:test:desktop`, `task roci:visual`, and
  `git diff --check`. Its code and design audits found no P1 or P2 issue.

The rail intentionally contains only a Phase 1 placeholder. Phase 2 replaces
it with exact source navigation, selection, privacy, load status, and refresh
state. Typed page controls, configuration extensions, and report mappings
remain Phase 3 work.

## Purpose

The first dashboard PLC proved that Portico can load its data and draw its
reports with Roci. This PLC rebuilds the desktop UI so its structure, controls,
and visual weight follow the Streamlit Portico app much more closely.

This is a local Portico change first. New UI pieces live in the Portico app,
but they must use Roci's normal fluent builder style and compose normal Roci
controls. At the end, the team will decide which pieces are general enough to
move into Roci. This PLC does not change the Roci worktree.

## What This Packet Covers

- A clear record of the Streamlit UI and the current Roci UI before work starts.
- A dark desktop shell with a permanent left navigation rail.
- A source-to-config mapping for page IDs, labels, headings, icons, controls,
  and reports.
- Typed TOML settings for navigation, page sections, controls, and widget
  placement. Typed C# page state, report inputs, and display actions own
  control behaviour; financial formulas stay in C#.
- Shared local controls and panels that look and behave like the Portico UI.
- One careful rebuild of each Portico dashboard page.
- Unit, interaction, configuration, and visual checks for every phase.
- A final short list of local components that may be worth moving to Roci.

## What This Packet Does Not Cover

- New financial rules, new data sources, OAuth, write-back, notifications,
  containers, browser builds, or a Roci merge request.
- A generic dashboard framework.
- Moving any code into Roci before the Portico version has proved its shape.

## Packet Files

- [DISCOVERY.md](DISCOVERY.md) records what must be checked before UI work.
- [SRD.md](SRD.md) defines the required result and its acceptance checks.
- [SADD.md](SADD.md) describes the page tree, local component boundaries,
  configuration boundary, and data flow.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) gives the phased build
  order and a concrete result for each phase.
- [TEST_PLAN.md](TEST_PLAN.md) lists automated and manual proof for the work.

## Build Order

| Phase | Concrete result |
| --- | --- |
| 0 | Written UI inventory, source mapping, test-only capture host, and screen captures. |
| 1 | Dark skin, page sizing, spacing, and flex layout rules. |
| 2 | Permanent left navigation rail and global shell state. |
| 3 | Shared cards, section headers, control bars, local multi-select, typed page controls, and source tabs. |
| 4 | Home page rebuilt from those shared pieces. |
| 5 | Analyze pages rebuilt one at a time. |
| 6 | Budget and Financial Independence rebuilt one at a time. |
| 7 | Data Health, empty/error states, and cross-page polish. |
| 8 | Full proof run and a written Roci-promotion decision. |

## Rules For The Work

- Do not start a later phase while the prior phase has a known layout or test
  failure.
- Keep report calculations separate from view code. The finance test suite must
  stay green after every UI phase.
- Put new colors, spacing, font sizes, and panel styles in one Portico skin.
  Do not scatter raw values through page builders.
- Keep each local component small. A page may compose it, but it must not know
  how the component draws itself.
- Use flex rows and columns for page layout. Do not add a new layout engine.
- Record a missing Roci component only after a small Portico version proves
  that normal Roci composition cannot express the needed behavior cleanly.

## Review Changes

An independent review checked this packet against the Streamlit source and
screenshots, the current Portico Roci app, and the Roci API.

| Finding | Plan change |
| --- | --- |
| The current C# session has only four single-choice filters, but the source pages use several input types. | Phase 3 now requires typed page state, validation, report/display mappings, and tests for every source control. TOML only selects supported controls. |
| Tabs and reset actions can change the page without changing a financial report. | Each C# control mapping now routes to either a report input or display/action state; the test suite covers every supplied control. |
| Roci has no dedicated multi-select, but the source uses multi-selects. | Multi-select is a required Portico-local component, not a conditional experiment. |
| Four source pages use tabs and Roci already supplies tabs. | The component inventory and page plan now use Roci `TabPanel` and `Tab`; no local tab widget is planned. |
| The release host cannot make deterministic visual captures. | Phase 0 now adds a test-only capture host and `roci:visual` command that use Roci automation/capture. |
| The committed reference images are 1500 by 1000 and the current Taskfile lacks `roci:test:dashboard`. | The primary visual size is 1500 by 1000, and all focused checks use the real `roci:test:desktop` command. |
| Current desktop labels differ from the Streamlit rail. | The discovery and configuration requirements now require an exact source-to-TOML navigation mapping. |
| A few source details are labeled expanders rather than popovers. | Page coverage now names the relevant source controls, including Choose categories, Subscription settings, Year-to-date position, and Source details. |

## Completion Condition

The app builds and its existing finance, adapter, dashboard, and desktop tests
pass. Every configured Portico page has the same main regions, controls, and
data views, navigation label, and page heading as its Streamlit reference. The
packet ends with visual proof and a decision for each local component: keep it
in Portico, improve it locally, or propose it for Roci later.
