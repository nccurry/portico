# Software Architecture And Design Document

## 1. Design Summary

The app stays split into its current four concerns:

| Project | Keeps responsibility for |
| --- | --- |
| `Portico.Finance` | Financial rules and calculations. It knows nothing about Roci, TOML, or controls. |
| `Portico.Dashboard` | Typed report and page view data. It turns finance results and filter state into values, series, rows, and warnings. |
| `Portico.Adapters` | Sheet/CSV input and typed TOML parsing. |
| `Portico.App` | CLI, app lifetime, Roci construction, local UI components, and conversion of dashboard view data into controls and charts. |

The layout rebuild changes `Portico.App` and the dashboard presentation TOML. It
may add small display-only view models in `Portico.Dashboard`. It does not put
Roci types in Finance, Dashboard, or Adapters.

## 2. Page Tree

The root is an ordinary horizontal flex row.

```text
Desktop window
  Portico shell row
    Navigation rail
      Home item
      Analyze, Plan, and Maintain groups with page items
      Spacer
      Hide values, load status, refresh
    Main column
      Optional demo-data banner
      Page title and description
      Optional page action row
      Scrollable page body
        Filter/control bar
        Summary metric row
        Page sections
          Charts, tables, cards, and details
```

The rail has a fixed desktop width. The main column grows to use all remaining
space. Page bodies scroll; the rail and title area do not scroll. Normal page
layout uses vertical stacks, horizontal stacks, gap, grow, shrink, and wrap.
An absolute overlay is allowed only for a popover, tooltip, dialog, or other
temporary overlay.

## 3. Layout Rules

| Need | Rule |
| --- | --- |
| Page width | Main body uses the available main-column width with the same left/right gutter as the reference. Do not add a global maximum width unless Phase 0 records a source page that needs one. |
| Wide rows | Summary cards and chart/table pairs use a horizontal stack with deliberate grow weights. |
| Narrow desktop | At 1024 by 720, rows wrap or become vertical in a fixed order. No card, filter, or table header may disappear behind another item. |
| Section spacing | Use named skin spacing for page gap, section gap, and compact control gap. |
| Dense data | Tables may scroll inside a bounded section. A page does not create an unbounded series of full-width rows. |
| Charts | Give every chart a deliberate height based on its reference. A chart should not depend on an accidental parent height. |
| Content order | Build content in the same reading order as the Streamlit page. Do not use visual reordering to compensate for data order. |

## 4. Portico Skin

Create one app-owned dark skin and named styles for:

- Window background and rail background.
- Main page background, raised panel, muted panel, and table surface.
- Page title, section title, metric label, metric value, helper text, and
  warning text.
- Navigation item, selected navigation item, hover/focus state, and group label.
- Primary, secondary, quiet, and danger actions.
- Positive, negative, neutral, warning, loading, and hidden-value states.
- Chart series colors and grid/axis text.

The skin owns color, border, corner, font, and spacing choices. A page builder
may choose a named state style such as `warning` or `positive`; it must not
build its own colors or borders.

## 5. Local UI Pieces

Local components go under a focused `Portico.App` UI area, for example
`Ui/Skin`, `Ui/Components`, and `Ui/Pages`. The exact names must follow nearby
project conventions found in Phase 0.

| Piece | Inputs | Owns | Does Not Own |
| --- | --- | --- | --- |
| Navigation rail | Known page IDs, groups, order, labels, icons, selected page, app actions | Rail layout, selected visual state, keyboard focus | Data loading or report calculations |
| Page header | Title, description, optional action content | Header spacing and text hierarchy | Navigation state |
| Control bar | Configured controls and callbacks | Control alignment, compact wrapping, reset/clear placement | Filter meaning or report calculation |
| Metric card | Label, formatted value, trend/status, optional detail action | Card layout and positive, negative, warning, and hidden state styles | Formatting rules that belong to a report |
| Section panel | Title, helper text, body content, optional actions | Surface, section spacing, header/body order | Chart/table data loading |
| Empty/error panel | State, title, help text, retry action | Safe, readable state presentation | Retry implementation |
| Multi-select | Label, typed items, selected values, selection callback, summary text | Closed button, popover, checkbox list, count, clear action | The page's filter query |

Each piece must expose a small set of public builder methods. Use method names
that match existing Roci controls where possible. Use specific methods for
label, items, selection, callback, width, and style rather than an options bag.
Keep the method sequence predictable: data first, state second, appearance
third, events last. Phase 0 must compare method names with existing Roci
controls before types are finalized.

### Multi-Select Behaviour

The local multi-select begins as a button that opens an anchored popover. The
popover contains a searchable checkbox list when the list is long enough, a
clear action, and a close action. It shows a short selection summary in the
closed state. It must retain selection when the page is rebuilt and must close
on the normal overlay dismissal paths. It is not added to Roci during this PLC.

## 6. State And Events

The app holds small UI state only:

| State | Scope | Changes it |
| --- | --- | --- |
| Selected page | App session | Navigation rail selection. |
| Hide values | App session | Global hide-values control. |
| Data load status | App session | Initial load and refresh. |
| Page controls | Typed record per page | Its control bar, page-specific controls, and reset action. |
| Selected tab | Per page when the source has tabs | Tab selection. |
| Selected data row or open detail | Per configured page | Table and detail actions. |
| Temporary overlay state | Local component | Popover, dialog, or tooltip actions. |

Changing a control updates a typed page-state record, asks the dashboard/report
layer for new view data, and redraws only the visible page presentation. It
does not reload source data unless the user asks to refresh. The current report
builder may still rebuild its whole dashboard report until a measured demo-data
update exceeds 250 ms. Only then add a page-level report cache and a focused
test. Hiding values changes only formatting at the display boundary.

### Typed Control And Report Path

The current `DashboardFilterKind.Select` and one shared `DashboardFilters`
record cannot represent the source pages. Phase 3 replaces that limitation with
a fixed list of typed control types: single select, segmented choice,
multi-select, number input, slider, toggle, tab choice, and action/reset.
Every source control must have four explicit links:

1. A page-state field with a valid C# type, or a named action handler.
2. A validation rule for user input and TOML defaults, or a statement that an
   action has no input value.
3. A typed input to the page's report request when it changes report data, or a
   typed display-state change when it only changes the UI.
4. A focused unit or interaction test with a known state or report result.

For the first three links, C# holds a mapping for each known control. The TOML
parser resolves that mapping before the page draws. The test suite checks the
fourth item; production code does not inspect test code. TOML controls
placement and allowed choices. C# owns the state, validation, display actions,
and calculation. A control must not be rendered until its C# mapping exists.

## 7. TOML Boundary

The existing dashboard TOML remains the place that chooses supported pages,
reports, filters, and chart presentation. Add typed presentation fields only
where the reference UI needs them.

| TOML concern | Examples |
| --- | --- |
| Navigation | Known C# group value, separate navigation label and page heading, icon from a fixed C# list, default page, visible order. |
| Page | Heading, description, control bar presence, refresh/hide-values relevance, and demo-banner relevance. |
| Section | Key, heading, helper text, order, layout form such as metric row or chart/table row. |
| Control | Key, label, finite supported kind, option source, default, validation range, and clear/reset behavior. |
| Widget | Existing typed report ID, section, order, span/grow choice, chart/table display choice. |

The parser validates IDs, references, and C# control mappings after it loads
TOML. It rejects unknown navigation groups/icons, control kinds, duplicate
keys, unknown section keys, unsupported option sources, controls without a
C# mapping, and widgets that name the wrong page. It does not read arbitrary
layout commands, raw colors, arbitrary method names, formulas, or source code
from configuration.

## 8. Page Builder Pattern

Each page has a short page builder that performs the same steps:

1. Read its typed page configuration and retained page state.
2. Ask `Portico.Dashboard` for its typed view data.
3. Build the page header and any page action row.
4. Build its control bar from typed control definitions.
5. Build sections in configured order using shared components.
6. Attach user events to typed state changes and rebuild the current page.
7. Show the shared empty/error panel when view data cannot be shown.

The page builder may choose which report-to-view mapping is needed, but it must
not reimplement finance rules, parse TOML, or construct arbitrary low-level
layout for a repeated card or panel pattern.

## 9. Page Coverage

| Navigation group | Navigation label / page heading | Required main parts |
| --- | --- | --- |
| Standalone | Home / Accounts and net worth | 3M/6M/1Y/2Y/5Y/All time choice, net-worth chart, summary band, safety cards, account groups, inventory/detail. |
| Analyze | Spending by category | Filter bar, spending metrics, category/time chart, ranking, detail table, and Adjust view popover. |
| Analyze | Income and savings | Filter bar, income metrics, trend/source views, detail tabs, and monthly-totals detail. |
| Analyze | Year over year | Period controls, comparison metrics, year comparison chart/table, Choose categories popover, and Details expander. |
| Analyze | Subscriptions | Filter bar, recurring summary, subscription table, monthly and charge details, and the Subscription settings expander. |
| Analyze | Spending by merchant | Filter bar, merchant ranking, trend/detail views, and Adjust view popover. |
| Analyze | Transactions | Date/category/account controls, More filters popover, transaction ranking/table, and selected detail. |
| Plan | Budget | Month/group controls, budget metrics, plan-versus-actual, dense budget detail, Year-to-date position expander, and Adjust view popover. |
| Plan | Financial independence | Scenario inputs, reset, metrics, projection, funding, sensitivity, Adjust source data popover, and Source details expander with tabs. |
| Maintain | Data health | Health summary, data warnings, counts, actionable detail, and Check settings popover. |

## 10. Visual Proof Design

Phase 0 adds a test-only Portico capture host when the release host cannot
accept Roci capture arguments. It uses fixed input data, window size, font
setup, and clock/date inputs. It enables Roci automation and capture features.
The baseline captures are evidence, not a source of fake test data.

Compare Roci captures only with baseline images made on the same platform.
Treat the Streamlit screenshots as manual visual references. Use retained UI-
tree or bounds tests for rail width, page margin, header position, control-bar
position, card count, section order, chart/table split, overlap, and clipping.

## 11. Future Roci Review

At the end, review each local component using these questions:

1. Does it have two or more different Portico uses?
2. Is its data and event model useful outside a finance dashboard?
3. Can its builder API use Roci naming without Portico terms?
4. Does it compose existing Roci controls cleanly, or expose a real missing
   primitive?
5. Can its tests move without Portico data or skin values?

Only a component that answers yes to all five becomes a separate Roci proposal.
The expected starting answer is that multi-select may qualify after proof;
navigation, metric cards, and section panels are likely Portico-local.

### Final Decision

| Item | Decision | Reason |
| --- | --- | --- |
| Multi-select | Keep it in Portico. | It has several page uses, but its keyboard and focus behavior still needs a library-level design. |
| Navigation rail | Keep it in Portico. | Its pages, groups, labels, icons, and actions are specific to this dashboard. |
| Headers, control bars, metric cards, and panels | Keep them in Portico. | Roci stacks, panels, text, and controls compose these pieces without a missing primitive. Portico owns their visual tokens. |
| Typed TOML control routes | Keep them in Portico. | They map Portico report inputs and page state. They are not a general UI component. |
| Timeline and heatmap charts | Move to the companion Roci worktree. | Subscriptions and Financial Independence use them through generic chart data and fluent APIs. |
| Per-category bar colors | Make a separate Roci proposal later. | The current chart style has one fill per series. The source needs one fill per category value. |
