# Discovery

## Goal

Before changing the UI, make a small, factual inventory of what Portico shows,
what the current Roci app shows, and what Roci can already compose. This keeps
the rebuild tied to the real app rather than to memory or a loose description.

## Sources To Inspect

| Source | What To Record |
| --- | --- |
| Streamlit Portico page modules | Navigation group, navigation label, page heading, controls, cards, charts, tables, tabs, empty states, and page-specific actions. |
| Streamlit screenshots | Dark colors, main widths, rail width, spacing, text hierarchy, chart height, and control placement. The committed screenshots are 1500 by 1000. |
| `dashboard.toml` and its C# types | Existing page IDs, widget IDs, filter keys, chart kinds, and fields that can be extended safely. |
| `PorticoDashboardScene.cs` and its tests | Current shell, direct layout code, current state flow, and the tests that must be rewritten or retained. |
| Roci layout, control, overlay, table, chart, and skin source | Exact fluent APIs already available for this app. |
| Roci samples and visual tests | The existing way to capture and compare a desktop screen. |

## Discovery Steps

1. Run the Streamlit reference with its demo data and save one image for every
   page at a fixed desktop size. Use 1500 by 1000 as the primary comparison
   size because that is the size of the committed reference images. Use 1024 by
   720 as the narrow-desktop check.
2. Run the current Roci app with the same demo data and save the same set of
   images.
3. Make a page inventory table. For each page, record its page ID, source file,
   group/order, navigation label, page heading, icon, left-to-right and
   top-to-bottom regions, controls, and reports or visible page state affected
   by each control.
   Include segmented choices, single selects, multi-selects, number inputs,
   sliders, toggles, tabs, expanders, row selection, reset actions, and
   popovers where the source page uses them.
4. Map each region to an existing Roci primitive: vertical stack, horizontal
   stack, panel, text, control, overlay, data grid, or chart.
5. Mark a gap only when a small composition of existing Roci primitives is
   awkward, cannot provide the interaction, or would force page-specific code
   into several pages.
6. Add a test-only capture host for Portico if the current desktop host cannot
   accept Roci capture arguments. It must create deterministic demo sessions,
   select named page states, enable Roci automation and capture, and accept the
   normal Roci capture arguments. Make `roci:visual` run the named cases
   serially. Reuse Roci's capture verifier rather than creating a new image
   comparison system.
7. Save the inventory, images, Roci API mapping, and open questions in this
   packet before Phase 1 starts.

## Starting Component Inventory

| UI need | Current direction | Status at planning time |
| --- | --- | --- |
| Rows, columns, gaps, wrapping, grow, shrink, and alignment | Use Roci stacks and flex settings. | Available. |
| Dark surface, text, borders, selected state, and chart colors | Add a Portico app skin using Roci skin/style slots. | Available foundation; app styling is incomplete. |
| Permanent left navigation | Build a local navigation rail from flex, buttons/menu items, and selected state. | Needs a local proof. |
| Page header, metric card, section panel, and filter bar | Build small local Portico pieces from panels and standard controls. | Needs local composition, not a Roci feature. |
| Single-select, segmented choice, toggle, number input, slider, and collapsible detail | Use existing Roci controls. | Available. |
| Filter that selects more than one value | Build a local multi-select from a button, popover, checkbox list, count badge, and clear action. | Confirmed required local component. |
| Tabbed detail views | Use Roci `TabPanel` and `Tab`; keep selected tab in page state only where the source page needs it. | Available. |
| Deterministic visual capture | Add a test-only capture host. The release host is fixed at 1280 by 820 and does not enable Roci automation/capture. | Required. |
| Tables, selected rows, and chart/table detail | Use DataGrid and the existing chart API. | Available; verify the exact Portico cases. |
| Tooltips, drop-down details, and dialogs | Use existing Roci overlays. | Available. |
| CSS-like `order` or reverse flex direction | Do not add it unless a named Portico screen truly needs it. | Not needed by the starting design. |

## Local Component Rule

All first versions live under the Portico app UI folder. Each has a small set
of public builder methods that reads like an existing Roci control: set data,
selection, label, size, style, and event handler through named fluent methods.
The component must not accept a general dictionary of drawing options or make
callers know its internal child tree.

The first confirmed local component is a multi-select. It must support a
label, list of typed items, selected values, clear action, summary text, and a
selection-change event. The navigation rail, metric card, and section panel
start as local compositions too; they are not automatically candidates for
Roci.

## Decision Record To Fill During Phase 0

| Item | Evidence needed | Decision |
| --- | --- | --- |
| Visual test method | A sample capture and one stable comparison run. | Pending. |
| Capture host | A test-only host that accepts capture arguments and enables Roci automation/capture. | Pending. |
| Navigation rail | A local proof with selected page, keyboard focus, and narrow-window behavior. | Pending. |
| Multi-select | A local proof used by at least two real page filters. | Pending. |
| Typed page controls | A table that maps each source control to state, report/display behavior, and a test. | Pending. |
| Any chart gap | A named Streamlit chart and the smallest attempted Roci composition. | Pending. |
| Page configuration fields | Current TOML types plus one representative page loaded through them. | Pending. |

## Phase 0 Exit Check

- The inventory lists all ten current pages and exact source navigation text:
  Home; Income and savings; Spending by merchant; Spending by category; Year
  over year; Subscriptions; Transactions; Budget; Financial independence; and
  Data health.
- Every page has a reference image and a list of its interactive controls.
- The default TOML has a tested mapping for page ID, group/order, navigation
  label, page heading, and icon.
- Every source control has a typed page-state field or action handler,
  validation rule, report input or display action, and focused test.
- Every named layout region maps to a Roci primitive or a documented local
  component proof.
- `task roci:visual` runs named test-only capture cases at 1500 by 1000 and
  1024 by 720, even before the UI changes.
- No Roci code has changed.
