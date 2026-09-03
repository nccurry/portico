# Synthetic demo data

All committed fixture data is synthetic. It describes a set of accounts from May 1992
through April 1995 and drives the browser demo, integration tests, and
screenshots.

Run `uv run --locked --dev python scripts/generate_demo_data.py` to regenerate
`accounts.csv`, `balance_history.csv`, `categories.csv`, and
`transactions.csv`. Reports use the latest date in the loaded synthetic data.

The fixture includes twelve accounts across Savings, Credit Cards, Investments,
Retirement, and Liabilities. Balances rise and fall independently. Transactions
include bills, rent, food, travel, gifts, and varied merchant names.
Budgets vary by category, season, and year.

## Subscription scenarios

- Flicker Stream, CloudBox Storage, and Soundwave Music stay active for the
  whole fixture.
- Morning Gazette and Pantry Box end before the final year.
- Fit Club ends in 1994 and returns in January 1995.

## Fixed data-quality scenarios

Three pairs of duplicate transactions remain in the data-health report:

- 02/07/1995 | -$45.99 | Juniper Kitchen Receipt | Everyday Card
- 12/12/1994 | -$125.50 | Harbor Home Receipt | Travel Rewards Card
- 10/05/1994 | -$78.00 | Northstar Coffee Receipt | Everyday Card

The fixture also has two equal $1,250 shopping purchases in March 1995. They
exercise stable ordering for tied top transactions.
