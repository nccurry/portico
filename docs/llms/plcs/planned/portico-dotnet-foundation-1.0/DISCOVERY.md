# Discovery

## Starting point

The current C# solution has four main projects:

    Portico.App -> Portico.Adapters, Portico.Dashboard, Portico.Finance, Roci
    Portico.Adapters -> Portico.Dashboard, Portico.Finance
    Portico.Dashboard -> Portico.Finance
    Portico.Finance -> no Portico project

The graph builds working software but has three important boundary problems:

1. Portico.Finance contains WorkbookSourceKind and DataSourceSettings. Finance
   therefore knows how data arrived.
2. Portico.Dashboard combines reusable report construction with mutable
   display/session state.
3. Portico.App parses commands, reads TOML, constructs CSV/Google sources,
   creates a DashboardSession, starts Roci, and formats command output.

The current TOML loader also combines finance settings, dashboard definitions,
sheet URLs, file access, and error translation. The current CLI exposes only
run and doctor.

## Confirmed baseline

- The non-visual C# suite passed 222 tests: 57 Finance, 47 Dashboard, 16
  Adapter, and 102 App tests.
- Treat that as a behavior-migration baseline, not a permanently required test
  count. Each covered behavior must move to an owning replacement test or have
  a documented reason it consolidated into a stronger test.
- A direct full solution run passed 223 tests. Its extra App test is the
  opt-in visual capture lane and took more than three minutes, so future
  routine task lanes must preserve the visual-test exclusion explicitly.
- The already-built doctor command succeeded against the demo data.
- Doctor JSON output already proves there is a useful seed for a stable
  machine-readable command contract.
- Normal test and demo data are synthetic. Keep that rule.

## Configuration findings

- Current config.toml was a Python/Streamlit contract and has been archived.
- Current portico-demo.toml and dashboard.toml are still active C# demo
  fixtures, but they use the old structure and will be replaced in this PLC.
- Relative data directories currently resolve from the selected configuration
  file. Preserve that behavior.
- Sheet URLs belong in a separate secret file and must never appear in output.
- The current C# CLI also accepts the --sheet NAME=URL option. The new CLI must
  remove it because a command-line URL can leak through process metadata before
  output redaction applies.
- weekly_summary exists in the archived configuration but is not part of the
  target foundation. The new schema must reject it rather than silently ignore
  it.

## Legacy archive

The Python/Streamlit source, tests, dependencies, deployment files, historical
screenshots, historical planning files, and Python-only workflows now live in
legacy/python.

demo/data, portico-demo.toml, and dashboard.toml remain at the root because the
active C# demo uses them. The archive is reference-only and is not an active
test or deployment target.

The root Taskfile is intentionally transitional: it still contains Python
targets whose paths now point at the archive, and the archive move left no
active CI workflow. Phase 0 first restores a working default .NET
build/test/check path and a minimal non-visual CI gate. Later phases expand
that into focused lanes. The opt-in visual test must never enter a default
task or CI lane.

The completed [Roci layout rebuild PLC](../../completed/portico-roci-layout-rebuild-1.0/README.md)
is the retained desktop visual baseline. It is historical evidence, not future
foundation scope.

## Reference patterns to retain

### Roci

Roci uses explicit C# union result types for expected operation outcomes and
has project-reference architecture tests. Portico should adopt both ideas in a
smaller form:

- use a result only for expected boundary failures;
- keep programmer errors as exceptions;
- test project references rather than relying on team memory; and
- let the outer composition project own framework and adapter wiring.

### Dungeon Draft Tactics

Its useful lesson is structural, not a code template: keep shared runtime code
separate from concrete hosts, use project boundaries only where ownership is
real, and keep test folders aligned with the code they test.

## Risks and controls

| Risk | Control |
| --- | --- |
| New projects add ceremony without clarity. | Create a project only for a stable ownership boundary; do not add Common, Shared, or generic Infrastructure. |
| The configuration redesign drops finance behavior. | Build a field inventory before writing the new schema; reject unsupported fields explicitly. |
| Result types hide developer defects. | Use them only for expected user, configuration, source, and cancellation outcomes. |
| The UI rewire changes desktop behavior. | Preserve existing UI tests and captures; no visual redesign belongs here. |
| Tests pass while dependency direction decays. | Add architecture tests before moving substantial code. |
| Google Sheets makes routine tests flaky. | Use fake HTTP and fixed fixtures in normal lanes; keep real-sheet checks opt-in. |
| The archive leaves default task or CI paths broken. | Restore a non-visual .NET default task and CI gate in Phase 0, before structural work. |
| Test count becomes a vanity gate during reorganization. | Trace existing behavior to replacement tests; use scenario coverage rather than a fixed count as the completion proof. |

## Open implementation questions

These are implementation choices, not product decisions:

- Whether Application uses two small input interfaces or one composed workspace
  loader. Choose the smaller option that keeps TOML and source types out of
  core logic.
- Exact report model names after the current DashboardReportBuilder is split.
- The package/tool used to collect coverage. The requirement is the evidence,
  not a specific coverage product.
- Whether the existing Portico.Roci.slnx evolves in place or is replaced by a
  broader .NET solution file. The architecture tests must not depend on the
  answer.
