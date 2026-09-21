# Software Requirements Document

## 1. Objective

Rebuild the Roci desktop dashboard so it follows the layout and interaction
model of the current Streamlit Portico dashboard. The result remains a local,
read-only finance desktop app that loads the same configured data and reports.

The work is about the UI layer. It must not weaken or replace the tested
financial calculations.

## 2. Scope

### In Scope

- The dark desktop layout, permanent left navigation, page headers, control
  bars, cards, charts, tables, details, and status views in the ten current
  Portico pages.
- Typed TOML that chooses page group, labels, section order, filter controls,
  widget placement, and display options.
- Local Portico UI components written in the same fluent style as Roci
  components.
- A local multi-select control because the source pages need it and Roci has no
  dedicated multi-select control.
- Source-style tabs built with Roci's existing `TabPanel` and `Tab` controls.
- Automated and manual visual proof at fixed desktop sizes.
- A written review of any local component that could later belong in Roci.

### Out Of Scope

- New finance calculations, changes to workbook semantics, OAuth, write-back,
  notifications, containers, browser support, mobile support, or a generic
  dashboard designer.
- Moving code to Roci during this implementation.
- Pixel-for-pixel copying where the two renderers differ. The required result
  is the same visible structure, visual hierarchy, data, and interaction.
- Streamlit's hosted-service chrome such as the Deploy menu. Copy Portico's
  dashboard content, not the Streamlit frame around it.

## 3. Users And Main Flows

The user starts the desktop app with existing CLI arguments, sees the last or
default page, changes pages from the persistent left rail, changes a page
filter, reads the updated reports, opens detail where available, and can see
whether data is hidden, loading, missing, or stale.

The user must not need to know Roci internals, write TOML, or restart the app
to move between configured pages.

## 4. Required Behaviour

### RQ-01: Record The Reference Before Building

The project must record a visual and structural inventory of the Streamlit and
current Roci versions before layout work starts.

Acceptance:

- The discovery record has one entry and one fixed-size image for every page.
- It names each page's controls and what each control changes.
- It records the exact page ID, group/order, navigation label, page heading,
  and icon from the source navigation.
- It links every source control to typed page state or an action handler,
  validation, a report input or display action, and a focused test.
- It maps every major visible region to an existing Roci primitive or a local
  component that needs a proof.

### RQ-02: Use A Simple Flex Page Tree

The root window must be a horizontal flex row: left navigation rail plus a
main content area. The main area must be a vertical stack: page header,
optional control bar, scrollable page body, and temporary status or overlay
content when needed.

Acceptance:

- The rail stays visible while the user scrolls page content.
- The main body grows and shrinks without overlapping the rail.
- Rows that contain cards or charts use wrapping or a deliberate stacked
  fallback at the documented narrow desktop width.
- The page builder does not rely on absolute positions for normal layout.

### RQ-03: Put Appearance In One Portico Skin

The app must use a dark Portico skin for its background, surfaces, typography,
borders, selected states, controls, chart colors, and status colors.

Acceptance:

- Page builders use named Portico styles rather than hard-coded colors,
  borders, or spacing values.
- Selected navigation, active filters, positive/negative values, warnings, and
  disabled content have readable contrast.
- A screen capture of Home clearly separates the rail, page background,
  section panels, and interactive controls.

### RQ-04: Provide Permanent Navigation And Global Actions

The app must show Home as a standalone item, followed by Analyze, Plan, and
Maintain group headings. The default configuration must use the source labels,
order, and icons. The rail must show the selected page, hide-values control,
data-load status, and refresh action at its lower edge. In demo mode, a
source-style demo-data banner must appear above the page heading.

Acceptance:

- Selecting an item changes page content and marks that item selected.
- Home does not get a duplicate group heading, and source navigation labels do
  not change to the current near-match labels such as "Merchant Analysis".
- The selected page survives a normal UI rebuild while the app stays open.
- Hide-values changes all private values consistently and does not change the
  underlying finance result.
- Refresh reports loading, success, and failure without breaking navigation.

### RQ-05: Keep Page Layout And Controls Configuration-Driven

`dashboard.toml` must continue to select pages and reports. It must be extended
only with typed settings that the real UI needs: a known navigation group,
navigation label, page heading, known icon, section order, supported controls,
widget placement, and display choices.

C# owns a fixed set of control types: single select, segmented choice,
multi-select, number input, slider, toggle, tab choice, and action/reset. Each
page with controls has a typed page-state record. A control that changes report
data has a typed report request. A tab, expander, or action that only changes
the displayed UI has typed display state or an action handler. TOML chooses
labels, placement, defaults, and supported option sources. It does not define
the calculation a control performs.

Acceptance:

- A configuration test loads every supplied page and rejects missing or invalid
  section, control, or widget references with a useful message.
- Adding a supported section, filter, or widget to TOML does not require a new
  layout algorithm.
- A control cannot appear in TOML unless a C# mapping supplies its page state
  or action handler, validation, and report input or display action. The test
  suite must include a focused behavior or report test for every supplied
  control.
- Financial formulas and report calculations remain C# code, not TOML strings.
- The UI does not accept raw flex or drawing values from untyped maps.

### RQ-06: Build Shared Local UI Pieces First

Before page rebuilds, the app must provide small local pieces for repeated
Portico patterns: section header, metric card, section panel, filter/control
bar, empty/error panel, and multi-select.

Acceptance:

- At least two pages use each shared piece that is introduced.
- Each local component has focused tests for its state and event behavior.
- Each public builder reads like a Roci control and hides its child layout.
- The component does not contain a Portico report calculation.

### RQ-07: Rebuild The Ten Pages In A Controlled Order

The project must rebuild Home, the six Analyze pages, the two Plan pages, and
Data Health using the shared shell and pieces.

Acceptance:

- Home has the "Accounts and net worth" heading, 3M/6M/1Y/2Y/5Y/All time
  choices, net-worth view, safety cards, account groups, and inventory/detail
  content matching the reference's main regions.
- Analyze pages have their reference filter placement, summary deck, charts,
  rankings or tables, and details where present.
- Budget has month and group controls, plan-versus-actual content, summary
  values, and detailed budget rows.
- Financial Independence has its editable scenario controls, reset action,
  metrics, projections, funding view, and sensitivity view.
- Data Health has its quality summary, warnings, and actionable detail.
- Income and Savings, Spending by Category, Spending by Merchant, and
  Financial Independence retain the source tabs where their detail views use
  tabs.
- Every page keeps its data and control behavior after navigation away and back.

### RQ-08: Handle Data And Privacy States Clearly

The app must keep its read-only model and show useful UI for load, empty,
invalid, stale, hidden-value, and failed-refresh states.

Acceptance:

- No page shows an unhandled exception when data is unavailable.
- The shell makes the active data state visible.
- Hidden values replace values consistently in cards, charts, tables, and
  details while labels and structure remain readable.

### RQ-09: Prove Layout And Behaviour

The project must add repeatable visual proof and retain full unit coverage for
calculation, configuration, and state handling.

Acceptance:

- A `task roci:visual` command produces or checks fixed-size page images.
- Roci image comparisons use baseline images captured on the same platform.
  Streamlit images remain manual references; retained UI-tree/bounds tests
  prove named regions, order, clipping, and overlap.
- Each phase has a named automated check and a short visual checklist.
- `task roci:format`, `task roci:lint`, `task roci:build:strict`, and
  `task roci:test` pass before the work is complete.
- Finance tests include the existing broad input cases and pass unchanged or
  are improved with new display-boundary tests.

### RQ-10: Decide What Belongs In Roci Later

At the end, the team must review every local component that was added. The
review must say keep local, improve local, or propose a separate Roci change.

Acceptance:

- The review names the proven Portico uses and the public builder shape.
- It identifies Portico-specific policy that must remain in the app.
- It does not make a Roci change as part of this PLC.

## 5. Quality Requirements

| Area | Requirement |
| --- | --- |
| Readability | Page code should read as a short list of regions and reports, not as a large tree of anonymous controls. |
| Layout | The desktop UI must work at 1500 by 1000 and 1024 by 720 without clipped primary controls or overlapping content. |
| Performance | Changing a control redraws only the visible page and does not reload source data. The app may rebuild the current whole-dashboard report until a measured demo-data update exceeds 250 ms; only then add a page-level report cache with a focused test. |
| Accessibility | Keyboard focus must reach rail items and filter controls. Selected, disabled, warning, and hidden-value states must not depend only on color. |
| Failure handling | Bad dashboard TOML and data load failures must produce an actionable message rather than a crash. |
| Test isolation | Finance and dashboard tests must not require a network connection or an interactive desktop unless they are explicitly visual tests. |

## 6. Requirement Traceability

| Requirement | Main phase | Automated proof |
| --- | --- | --- |
| RQ-01 | 0 | Inventory check and baseline capture command. |
| RQ-02, RQ-03 | 1 | Layout/state tests and fixed-size shell capture. |
| RQ-04 | 2 | Navigation and global-state interaction tests. |
| RQ-05, RQ-06 | 3 | TOML parsing and shared-component tests. |
| RQ-07 | 4 through 7 | Page report, control, and screen checks. |
| RQ-08 | 2 and 7 | Data-state and hidden-value tests. |
| RQ-09 | 0 through 8 | Task commands listed in TEST_PLAN.md. |
| RQ-10 | 8 | Written local-component review. |

## 7. Done Means

This PLC is done when all requirements above have evidence, all ten pages use
the new shell and shared UI pieces, the app remains data/configuration-driven,
and the final review says what stays local and what may be proposed for Roci in
a future, separate change.
