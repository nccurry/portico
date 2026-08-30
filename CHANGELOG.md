# Changelog

This project records notable changes in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Renamed the application from Tiller Streamlit to Portico.
- Renamed the application environment variables from `TILLER_*` to `PORTICO_*`.
- Renamed the container image to `ghcr.io/nccurry/portico`.
- Simplified native setup so each bootstrap installs Task once before Task installs the Python toolchain.

### Added

- Apache-2.0 licensing and public project metadata.
- Validated public configuration with ignored local overrides.
- A synthetic demo mode and configuration doctor.
- A non-root Linux container with demo and live Compose profiles.
- Localhost network defaults and an explicit trusted-LAN command.
- Original Portico branding and a five-screen synthetic demo gallery.
- A GitHub Pages workflow for the static demo gallery.
- A shared development container and atomic CI jobs for linting, tests, coverage, privacy, documentation, and container smoke tests.
- Native Linux and Windows bootstrap checks in CI.

### Removed

- Device-specific system service installers and notifier scheduling.

[Unreleased]: https://github.com/nccurry/portico/compare/v1.0.0...HEAD
