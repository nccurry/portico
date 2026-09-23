# Test Plan

## 1. Test strategy

Tests prove behavior at the lowest useful layer first, then prove the real
process boundary. No ordinary test calls Google Sheets or opens an interactive
desktop window.

The current 222-test C# suite is a behavior-migration baseline, not a fixed
completion count. Every existing covered behavior must have an owning
replacement test or a documented reason it consolidated into a stronger test.

## 2. Test lanes

| Lane | Main proof | Test doubles |
| --- | --- | --- |
| Architecture | Evaluated production project references and Finance imports obey the target graph. | Actual project files, imported-reference fixture, and source samples. |
| Finance | Financial calculations and invariants are correct. | In-memory snapshots and settings. |
| Application | Use cases map inputs to semantic reports and typed problems. | Fake configuration and source interfaces. |
| Configuration | TOML schema, field validation, secret lookup, path resolution, and redaction work. | Temporary file roots. |
| Data | CSV/Google input normalizes to the shared snapshot or a typed data problem. | CSV fixtures and fake HttpMessageHandler. |
| CLI | Commands parse correctly and write stable text, JSON, stderr, and exit codes. | Fake Application service. |
| Desktop | Existing page state, interaction, and visual behavior survives the rewire. | Application fixture/service and fixed demo data. |
| App composition | A typed run command reaches Desktop without giving CLI a Desktop dependency. | Fake Application and Desktop host. |
| E2E | The published executable accepts files/options and returns public contracts. | Disposable fixture directory and published binary. |
| Visual | The retained Roci UI remains stable at documented window sizes. | Existing capture host and synthetic data. |

## 3. Required scenario matrix

### Finance and Application

- normal finance data;
- empty collections;
- zero, positive, and negative values;
- date and reporting-period boundaries;
- missing or invalid domain inputs;
- aliases, filters, transaction sets, ties, duplicates, refunds, and
  uncategorized rows where relevant;
- deterministic ordering;
- expected result and unexpected invariant paths.

### Configuration

- valid portico.toml;
- valid local and Google source declarations;
- missing file;
- invalid schema version;
- unknown key;
- invalid cross-reference;
- several independent errors in one file;
- relative data path;
- missing secret;
- default and explicit complete-file selection;
- rejected legacy document shape and weekly_summary input;
- a secret URL absent from all problem and JSON output.

### Data

- valid local CSV source;
- each required file missing;
- each required column missing or malformed;
- normalizer cross-table mismatch;
- fake Google success;
- fake Google non-success, timeout, cancellation, and invalid document;
- same semantic fixture through both source readers.
- the documented minimum supported date at and just below the boundary in
  transaction, balance, and budget inputs; an earlier date yields a typed data
  problem rather than reaching report lookback arithmetic.

### CLI

- each valid command;
- invalid command and invalid option;
- default and explicit config, secret, and dashboard paths;
- option accepted only by its documented command;
- text output;
- JSON success and expected-failure schema;
- stdout contains only result data;
- stderr contains diagnostics only;
- each documented exit code;
- documented exit-code precedence;
- cancellation and unexpected-host result;
- source URLs are neither accepted as command options nor echoed;
- no prompt and no secret leak.

### E2E

- config check succeeds in a disposable directory;
- config check rejects unknown keys or the legacy document shape;
- data check succeeds against copied demo CSV files;
- doctor succeeds in text and JSON;
- doctor returns a stable configuration/data failure;
- a published executable runs config check, data check, and doctor without the
  test process directly calling internal classes.

A fast build-output host-process check may support local development, but it
does not replace the required published-binary smoke.

## 4. Fixtures

Create small, named fixture directories. Each fixture contains only synthetic
data and the exact portico.toml, secrets example, CSV inputs, and expected
problem codes needed for its scenario.

Do not share mutable fixture files between tests. Each E2E test copies a
fixture into a disposable directory. Resolve relative paths from that copied
configuration file.

Google tests use fake HTTP responses. A manual, opt-in real-sheet check may
exist later, but it is never part of the normal suite and never logs a URL.

## 5. Coverage and review

Finance and Application must reach at least 95% line coverage and 90% branch
coverage after the new project baseline is established. A coverage percentage
does not excuse an untested error path or a weak assertion.

Phase 2 began with a dated local ratchet while semantic reports were being
added. On 2026-09-23, the built-in .NET coverage collector measured the named
`Portico.Finance` package at 90.00% lines and 79.54% branches, and the named
`Portico.Application` package at 97.62% lines and 82.69% branches. These are
pre-report baselines, not passing coverage gates. At the Phase 2 close, the
same named packages measured 97.13% lines / 90.20% branches for Finance and
98.56% lines / 93.80% branches for Application. By 2026-09-30, the local
`task dotnet:coverage` command must fail if either package is below 95% lines
or 90% branches. Phase 5 cannot pass until that gate is green; no CI workflow
is required.

Use this command for each owning test project:

```powershell
dotnet test <owning-test-project> --no-build --no-restore --collect 'Code Coverage;Format=cobertura' --results-directory <temporary-directory>
```

Read each named package in the Cobertura XML. The report-wide aggregate also
contains test and transitive assemblies and is not a valid layer measurement.

The required review order is:

1. architecture test and focused unit tests;
2. owning adapter/CLI/Desktop tests;
3. relevant code and test-quality review;
4. aggregate test, format, lint, documentation, and whitespace checks.

Fix all P1/P2 findings. Fix inexpensive P3 findings or record the reason for
deferral before the aggregate check.

## 6. Planned task lanes

The implementation chooses the exact Taskfile syntax, but the resulting
commands must make these lanes visible:

    dotnet:test:architecture
    dotnet:test:finance
    dotnet:test:application
    dotnet:test:configuration
    dotnet:test:data
    dotnet:test:cli
    dotnet:test:app
    dotnet:test:desktop
    dotnet:test:e2e
    dotnet:test:visual
    dotnet:test

Each focused command selects owning projects directly rather than applying a
test-name filter to the whole solution. Build/restore and test execution are
separate so a focused lane does not pay unrelated test-host cost.

## 7. Completion evidence

The final implementation records:

- the output and count for every automated lane;
- JSON examples for success and each public failure class;
- architecture-test evidence showing the graph is enforced;
- coverage output for Finance and Application;
- retained visual capture evidence;
- a short manual desktop smoke result; and
- git diff --check output.
