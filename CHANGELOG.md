# Changelog

This file records notable changes to Portico.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Portico uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/nccurry/portico/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/nccurry/portico/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nccurry/portico/releases/tag/v1.0.0
