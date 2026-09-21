# Transaction sets and spreadsheet sources — requirements

## Purpose

Replace report-specific spending-view rules with reusable, named transaction
sets. A set can select exact Groups, Categories, and Accounts; normalized
Merchants; or literal transaction-description text, then include or exclude
other sets. Reports opt into the sets they expose rather than reimplementing
their own taxonomy.

At the same time, make local CSV exports a first-class source. The committed
demo becomes an explicit local-data profile, not a special source mode or an
auto-detected fallback.

The normal configuration is one complete `config.toml` file. A user edits or
mounts that file directly. A separate complete `portico-demo.toml` file exists
only for the committed synthetic data.

## Scope

Included:

- Named transaction sets and named report filter sets in tracked TOML.
- Consistent discretionary filtering in Spending by Category, Spending by
  Merchant, and Year over Year.
- Exact utility membership for Year over Year, replacing fuzzy Group and
  Category matching.
- Removal of the subscription-detection regex shortcut in favor of explicit
  category values.
- Shared merchant normalization and aliases wherever merchant rows are grouped.
- Explicit `remote` and `local` spreadsheet sources, with a checked-in demo
  configuration.
- The cash-flow/savings-rate chart month-alignment regression.
- Documentation, demo packaging, container wiring, and tests.

Excluded:

- Writing classifications back to a spreadsheet or adding a custom Categories-sheet
  column.
- A general boolean query language, arbitrary regular expressions, or a source
  plugin framework.
- Changing an ad hoc page filter into a persistent configuration change.

## Terms

- **Transaction set**: a named, reusable set of expense transactions.
- **Filter set**: the transaction-set choices one report or widget exposes.
- **Exact selector**: a Group, Category, or Account value compared exactly to
  its normalized spreadsheet field.
- **Merchant selector**: a value compared through the existing normalized
  merchant and alias logic.
- **`transactions_like` selector**: a case-insensitive, literal substring of
  `Full Description`. It is deliberately not a regex.

## Functional requirements

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| TS-1 | TOML defines named transaction sets with a stable key and label. | Each set may declare `groups`, `categories`, `accounts`, `merchants`, `transactions_like`, `includes`, and `excludes`. Unknown keys, duplicate labels, unknown references, self-references, and reference cycles fail at configuration load. |
| TS-2 | Set matching is understandable and data-backed. | Values within a selector are alternatives. Direct selectors and `includes` form a union; `excludes` are subtracted last. Groups, Categories, and Accounts use exact equality. An empty `all` set matches the input expense universe. |
| TS-3 | Merchant and text matching are explicit. | Merchant selections use the same normalization and aliases as merchant reports. `transactions_like` normalizes case and whitespace and never interprets a value as regex. |
| TS-4 | Configured values do not create a second category taxonomy. | Utility and discretionary definitions select real spreadsheet values or explicitly named transaction text; no `*_terms` substring heuristic remains for those policies. |
| TS-5 | Discretionary is one configured policy. | A discretionary set can exclude tax payments, checks, home-loan activity, Airbnb/travel activity, and configured non-routine Groups/Categories. Spending by Category, Spending by Merchant, and Year over Year produce the same included rows for that set. |
| TS-6 | Widgets opt into named choices. | A filter set contains ordered transaction-set keys and a valid default. Spending pages expose `all` and `discretionary`; Year over Year exposes `all`, `utilities`, and `discretionary`. Other pages do not show Utilities unless their filter set names it. |
| TS-7 | Existing per-session adjustment controls remain available. | An adjustment is a page-local overlay on the selected configured set, is resettable, and never edits TOML. Its final result and transaction-detail rows agree with the summary and chart. |
| SUB-1 | Subscription discovery has no hidden regex taxonomy. | Remove `detection_excluded_pattern`; retain an array of exact `detection_excluded_categories`. Remove any now-unnecessary regex validation and matching. |
| MER-1 | Merchant aggregation is consistent. | Amazon and Walmart-style description variants condense through the configured aliases in every merchant aggregation path, while transaction/detail tables retain their raw descriptions. |
| DATA-1 | Local CSV is a real, explicit source. | `data.source` accepts only `remote` and `local`. Local reads the four standard spreadsheet CSV files from a configured directory. There is no automatic source selection. |
| DATA-2 | Demo is an example local-data configuration. | The tracked `portico-demo.toml` selects `local` and the committed synthetic directory. Reports use the latest data date and the demo banner comes from that exact filename. |
| DATA-3 | Runtime selection stays small and safe. | Remove `PORTICO_DATA_SOURCE`. `PORTICO_CONFIG_PATH` can select one other complete configuration file, never an overlay. Docker mounts `config.toml` directly and, for local CSV, a data directory. |
| CHART-1 | The cash-flow panels share month positions. | The bars, surplus line, savings-rate line, selection rules, and visible month axis use one canonical temporal month field and one shared x scale. A July datum and July label occupy the same x coordinate. |

## Quality requirements

- Keep the configuration parser strict and frozen/typed.
- Keep transaction-set evaluation as small, pure Pandas functions in `src`.
- Apply the selected set before report aggregation so totals, charts, merchant
  tables, and detail tables reconcile.
- Preserve read-only spreadsheet behavior and the synthetic-demo privacy boundary.
- Keep the existing editable controls, Streamlit session-state behavior, value
  hiding, and error handling intact.

## Delivery phases

1. Define the typed configuration contract and complete normal and demo files.
2. Add the transaction-set resolver and route spending ledgers through it.
3. Migrate the Spending, Merchant, and Year over Year controls and calculations.
4. Remove the subscription regex and centralize merchant alias propagation.
5. Replace demo mode with local CSV source/profile wiring across Task, Docker,
   browser-demo packaging, doctor, and documentation.
6. Repair the month scale, add regression tests, and run the full verification
   suite.

## Verification matrix

| Requirement | Primary tests |
| --- | --- |
| TS-1, TS-2, TS-3 | Config unit tests and pure transaction-set tests for exact, literal, normalized-merchant, include, exclude, and cycle cases. |
| TS-5, TS-7 | Spending-ledger unit tests plus integration tests asserting identical discretionary row identities/totals across consumers. |
| TS-6 | Streamlit AppTests for configured options, defaults, and page-local state. |
| SUB-1 | Subscription-candidate unit tests with category exclusions and regex-looking text treated literally. |
| MER-1 | Merchant-analysis, Spending detail, Subscription, and Top Transactions tests using alias variants. |
| DATA-1, DATA-2, DATA-3 | Config, spreadsheet-source, doctor, browser-demo archive, and container-smoke tests. |
| CHART-1 | Chart-spec/unit regression verifying the common temporal x encoding and aligned selected-month rule. |

Final gates: Ruff, format check, strict mypy, unit tests, integration/AppTests,
container smoke test, documentation checks, and `git diff --check`. Fix all P1
and P2 findings; fix inexpensive P3 findings or record them.
