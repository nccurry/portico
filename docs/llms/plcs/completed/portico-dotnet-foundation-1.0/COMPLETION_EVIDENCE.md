# Foundation completion evidence

Verified locally on 2026-09-23 with .NET 11 preview SDK and the clean local
Roci checkout `roci-ui-focus-outline-containment` at `c814b027`, selected by
`ROCI_ROOT`. Continuous integration remains deferred as requested.

## Automated checks

`task check` passed: formatting, a zero-warning strict build, all focused
non-visual lanes, the published-process check, coverage, and the local Roci
source contract. `task dotnet:test:visual` passed separately and retained 48
desktop PNG captures at the configured window sizes.

| Lane | Passed |
| --- | ---: |
| Architecture | 14 |
| Finance | 86 |
| Application | 84 |
| Configuration | 18 |
| Data | 58 |
| CLI | 45 |
| App composition | 7 |
| Desktop, non-visual | 148 |
| Published-process E2E | 1 |
| **Unique non-visual total** | **461** |

The architecture lane evaluates the final production project-reference sets
in Debug and Release, including imported references. No active App,
Dashboard, or Adapter transition edge remains. The published-process test
copies synthetic CSV data and exercises `config check`, `data check`, and
`doctor`, including invalid configuration, missing data, safe output, and exit
codes.

`task dotnet:coverage` now fails below 95% lines or 90% branches in either
named package. The measured `Portico.Finance` package passed at 97.15% lines
and 90.42% branches; `Portico.Application` passed at 98.69% lines and 94.30%
branches. The collector's report-wide total is not used as the gate.

## Command-result examples

These examples use synthetic data and the stable `portico.command-result.v1`
schema. The first success and configuration failure were also observed from
the built executable. The published-process and CLI tests verify the other
result classes and exit-code policy. Expected JSON results use standard
output; usage and unexpected host errors use standard error instead.

```jsonl
{"schema":"portico.command-result.v1","command":"doctor","outcome":"success","details":{"source":"local_csv","transactions":986,"balances":432,"budgets":1344},"problems":[]}
{"schema":"portico.command-result.v1","command":"config-check","outcome":"failure","details":null,"problems":[{"code":"config.file-not-found","message":"The selected file does not exist.","field":"configuration","retryable":false}]}
{"schema":"portico.command-result.v1","command":"data-check","outcome":"failure","details":null,"problems":[{"code":"data.missing-file","message":"The local data directory is missing accounts.csv.","field":null,"retryable":false}]}
{"schema":"portico.command-result.v1","command":"data-check","outcome":"failure","details":null,"problems":[{"code":"source.timeout","message":"The data source did not respond in time.","field":null,"retryable":true}]}
{"schema":"portico.command-result.v1","command":"config-check","outcome":"failure","details":null,"problems":[{"code":"operation.cancelled","message":"The operation was cancelled.","field":null,"retryable":true}]}
```

The matching exit codes are 0, 3, 4, 5, and 5. Invalid syntax exits 2 with
`Argument error: ...` on standard error; an unexpected internal error exits
1 with the fixed `Portico could not complete the command because of an
internal error.` diagnostic. Neither path emits a JSON result. CLI tests also
prove configuration failures take precedence over data or retryable failures.

## Desktop and review evidence

The retained desktop interaction tests passed. The visual lane opened the
Roci capture host and produced 48 PNGs. A manual comparison with the Phase 0
captures found 43 exact matches and five Data Health/Transactions differences
caused by the corrected handling of the demo workbook's `Hide` marker. The
new counts are covered by tests. No layout redesign was made. A normal
`task run` reached `Opening the Portico desktop dashboard.` and remained
running until it was deliberately interrupted. This tool session exposed no
visible window handles, so live window interaction could not be observed.
The retained 1500x1000 and 1024x720 Merchants captures were reviewed by eye;
text and controls remained visible. A human interactive pass on a visible
desktop remains a recommended follow-up, not an unreported pass.

Phase audits and the final eleven-gate audit found no remaining P1 or P2
finding after corrections. Active documentation now describes the implemented
.NET graph and clean configuration cutover. `git diff --check` passed.

The default sibling `../roci` checkout was dirty at `7511540e` and had two
independently reproduced `Roci.Ui` compile errors. It is not claimed as a
passing dependency. No Roci or CI source was changed for this packet.
