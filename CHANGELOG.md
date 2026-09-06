# Changelog

This file records notable changes to Portico.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Portico uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-09-06

### Changed

- The weekly Discord summary now follows named transaction sets configured in
  `[weekly_summary]`, defaults to a 48-week usual-spending baseline, shows
  current-week active categories, and includes the combined absolute amount of
  outstanding uncategorized transactions.
- Production deployment now uses the tracked Docker Compose manifest with a
  pinned image tag and the existing persistent delivery-state volume.

### Removed

- `notifications.discord.categories` is no longer supported. Configure
  `weekly_summary.watched_transaction_sets` instead.

## [1.2.3] - 2026-09-03

### Fixed

- Account groups on the Home page now list positive net-worth contributions before negative contributions.

## [1.2.2] - 2026-09-03

### Fixed

- The browser demo now patches the bound `st.container` export used by every page and gives each built archive a fresh cache key.
- Account-group sparklines use the asset and liability colors instead of the fixed Streamlit metric color.
- The sidebar uses one divider between navigation and its global controls.

## [1.2.1] - 2026-09-03

### Fixed

- The browser demo now accepts responsive control rows when its bundled Streamlit runtime does not support the newer `wrap` argument on containers.

## [1.2.0] - 2026-09-03

### Added

- Reusable transaction sets let spending reports share one definition of discretionary, utility, and other views.
- Local CSV files are a first-class spreadsheet source alongside the configured remote spreadsheet.

### Changed

- `config.toml` is now the one complete normal configuration file; `portico-demo.toml` is the complete synthetic-data configuration.
- Reporting periods use the latest loaded spreadsheet date, and the demo banner is inferred from the demo configuration filename.
- Configuration, documentation, and container labels use generic spreadsheet language.

### Fixed

- Spending-by-category, merchant, and year-over-year views now apply the same configured discretionary policy.
- Cash-flow month labels and data points share one aligned time scale.
- Merchant aliases are used consistently when merchant rows are grouped.

## [1.1.0] - 2026-09-01

### Added

- An interactive GitHub Pages preview for synthetic accounts, net worth, and spending data.
- Net-worth movement by account group on the Home page.
- Emergency-fund, debt-paydown, and FI funding progress on the Home page.
- Daily cumulative spending against the selected monthly budget pace.

### Changed

- Time-frame controls now use one shared layout across the reporting pages.
- Default financial-safety settings include savings, credit cards, home loan, and auto loan groups.
- The default Home-page FI funding target is $5 million.

### Fixed

- Budget pace uses the latest imported transaction date and does not show a future-month pace.
- The browser demo runs the full app against stable synthetic fixture dates.
- Emergency-fund spending excludes the partial current month.

## [1.0.0] - 2026-08-30

### Added

- Read-only dashboards for income, spending, budgets, subscriptions, net worth, financial independence, and data health.
- Google Sheets support based on the Tiller Foundation Template.
- A synthetic demo with no financial records or Google Sheets connection.
- Configurable analysis defaults with private local overrides.
- A non-root Linux container with local-only network defaults.
- A configurable weekly Discord expense summary with an optional built-in schedule.
- A shared development container, native bootstrap scripts, tests, and release checks.

[Unreleased]: https://github.com/nccurry/portico/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/nccurry/portico/compare/v1.2.3...v1.3.0
[1.2.3]: https://github.com/nccurry/portico/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/nccurry/portico/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/nccurry/portico/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/nccurry/portico/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nccurry/portico/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nccurry/portico/releases/tag/v1.0.0
