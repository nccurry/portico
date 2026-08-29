# Demo image provenance

All five screenshots use the committed synthetic data under `demo/data/`. They do not use Google Sheets, local configuration, or live financial data.

## Capture details

| Images | Source revision | Date | Viewport |
| --- | --- | --- | --- |
| `demo-overview.png`, `demo-spending.png`, `demo-budget.png` | `5b166956e8f498a420c6dfc502e31be2928ddc5e` | 2026-08-29 | 1440 × 1000 |
| `demo-financial-independence.png`, `demo-data-health.png` | `6bb05112f297a099decc7d097542c9f20175f950` | 2026-08-29 | 1440 × 1000 |

The demo reference date is `2026-04-17T00:00:00+00:00`, as recorded in `demo/data/REFERENCE_DATE.txt`.

## Capture command

From the repository root in PowerShell:

```powershell
$env:PORTICO_DATA_SOURCE = "demo"
.tools/bin/uv.exe run --locked --dev streamlit run Home.py --server.address=127.0.0.1 --server.port=8502 --client.toolbarMode=minimal
```

Open each page and capture the viewport at 1440 × 1000. The two screenshots from revision `6bb0511` used Chromium 151 through Playwright. Playwright is not a project dependency.

The same revision was also reviewed at 390 × 844 with the sidebar collapsed. The content reflowed without horizontal clipping, so no separate narrow image is committed.
