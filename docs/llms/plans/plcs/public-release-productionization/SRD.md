# Public Release Productionization — Software Requirements

Status: Proposed

Target release: `v1.0.0` stable public release

Branch: `ncurry/public-release-productionization`

Base: local `main` at `da76d0a` (one commit ahead of `origin/main` when planned)

## 1. Purpose

Prepare Tiller Streamlit for a public Apache-2.0 release that a new user can understand, try without private data, configure safely, deploy as a Linux container, and contribute to without relying on the maintainer's environment.

The work must preserve the maintainer's current workflow through ignored local overrides. Public defaults must remain useful and broadly aligned with the existing financial assumptions without publishing employer, institution, account, merchant, or household-specific values.

## 2. References

- Current repository `README.md`, `Taskfile.yml`, `pyproject.toml`, `.streamlit/secrets.example.toml`, and `scripts/check_repository_privacy.py`
- Canonical synthetic CSV fixtures under `demo/data/`
- Existing hide-values implementation in `src/value_visibility.py`
- The maintainer's local visual reference repository
- Apache License 2.0 canonical text
- Official Streamlit and `st-gsheets-connection` documentation, verified during implementation

## 3. Users and first-success outcomes

### 3.1 Prospective user

A visitor must understand the product and see representative screens within one minute of opening the repository.

### 3.2 Evaluating user

A user must run a complete local demo without Google credentials, a Tiller workbook, a Discord webhook, or outbound data access after dependencies are installed.

### 3.3 Tiller user

A user must configure the four supported sheet tabs, validate the configuration, and receive actionable errors for missing tabs, invalid `gid` values, schema mismatches, or inaccessible data.

### 3.4 Linux operator

An operator must deploy the Linux container with a localhost-only default and explicitly opt into LAN or reverse-proxy exposure.

### 3.5 Contributor

A contributor must find the setup, checks, contribution expectations, support boundaries, security reporting path, versioning policy, and release process in tracked documentation.

## 4. Scope

### 4.1 In scope

- Apache-2.0 licensing and third-party attribution review
- Public project metadata and an unofficial Tiller affiliation disclaimer
- Layered application configuration with safe, useful defaults
- A network-independent demo backed by synthetic data
- Human-readable configuration diagnostics
- Localhost-by-default networking and explicit LAN/reverse-proxy guidance
- An original SVG logo and Roci-inspired README presentation
- Documented screenshots captured only from demo data
- Schema and compatibility documentation
- Community, support, and security documentation
- A multi-architecture OCI container image for Linux amd64 and ARM64 hosts
- Linux source validation and multi-architecture container CI
- Dependency, secret, and release automation
- A repeatable `v1.0.0` GitHub and container release process

### 4.2 Out of scope for `v1.0.0`

- PyPI publication; the repository remains an application with `tool.uv.package = false`
- Kubernetes manifests or Helm charts
- Public internet exposure without an authenticated reverse proxy
- Multi-user authorization inside the Streamlit application
- Editing Tiller data from the dashboard
- A plugin system or generalized data-provider framework
- Telemetry, analytics, or crash reporting

## 5. Functional requirements

### 5.1 Licensing and public identity

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| PUB-001 | License the repository under Apache License 2.0. | `LICENSE` contains the canonical Apache-2.0 text; `pyproject.toml` and README identify Apache-2.0; CI or a release check verifies the file exists. |
| PUB-002 | Record project ownership and required notices. | README includes `Copyright 2026 Nick Curry and contributors`. No per-file copyright header is required. `NOTICE` is added only if a bundled asset or dependency requires attribution. |
| PUB-003 | Avoid implying official Tiller affiliation. | README and project metadata describe the project as unofficial and not affiliated with or endorsed by Tiller. |
| PUB-004 | Provide complete public metadata. | `pyproject.toml` includes description, README, license expression, maintainer, repository/issues URLs, and supported Python policy. |

### 5.2 Configuration and defaults

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| CFG-001 | Load application settings through one validated configuration module. | Pages and analyses no longer read household-tunable defaults directly from scattered constants or `st.secrets`; invalid values fail with field-specific messages. |
| CFG-002 | Layer tracked defaults and ignored local overrides. | Precedence is documented and tested: tracked defaults, optional ignored local settings, then explicit environment/Task overrides for deployment values. Secrets remain separate. |
| CFG-003 | Ship safe, useful defaults. | Current anonymous thresholds, financial assumptions, and report exclusions remain unchanged; employer, institution, named-account, local-merchant, and identifying household defaults are absent from tracked configuration. |
| CFG-004 | Preserve the maintainer workflow. | A local override file can reproduce the current account selections, exclusions, thresholds, network binding, and notification schedule without source edits. |
| CFG-005 | Keep configuration bounded. | Household policy and deployment choices are configurable. Chart construction, internal column names, layout sizes, and other implementation details remain code-owned unless a user requirement proves otherwise. |
| CFG-006 | Initialize local settings safely. | `task config:init` creates a local settings file only when absent, never overwrites an existing file, supports non-interactive use, and returns a non-zero status on failure. |

### 5.3 Demo and diagnostics

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| DEMO-001 | Provide `task demo`. | The command starts every dashboard page from committed synthetic data and does not require `.streamlit/secrets.toml`, Google Sheets, Discord, or personal files. |
| DEMO-002 | Make demo mode explicit. | The UI shows a persistent “Demo data” indicator; normal `task run` never silently falls back to demo data. |
| DEMO-003 | Keep demo data first-class and private-data-safe. | Demo CSVs are documented as synthetic, pass the repository privacy checker, and are shared by demo and integration tests rather than copied into two divergent datasets. |
| DEMO-004 | Provide `task doctor`. | The command validates settings, secret presence, connection URLs, per-tab numeric `gid`, access, required columns, and basic parseability without starting the UI. It exits non-zero on failure. |
| DEMO-005 | Keep diagnostics safe and actionable. | Doctor output names the failed check and remediation without printing complete sheet URLs, webhook values, or financial rows. |
| DEMO-006 | Cover disconnected and malformed configurations. | Tests cover absent config, inaccessible sheets, missing `gid`, duplicate tab mapping, wrong tab schema, empty sheets, and demo success. |

### 5.4 Network and deployment safety

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| NET-001 | Default to localhost. | Development and documented Linux container paths publish to `127.0.0.1` unless the operator explicitly selects another address. |
| NET-002 | Make LAN exposure explicit. | A documented `task run:lan` or equivalent opt-in binds to `0.0.0.0`, prints the lack-of-authentication warning, and is covered by Task tests or render assertions. |
| NET-003 | Document supported exposure patterns. | Deployment docs distinguish local-only, trusted-LAN, private VPN, and authenticated TLS reverse-proxy use. Public port forwarding is explicitly unsupported. |
| NET-004 | Keep one deployment path. | Linux containers are the only documented deployment. Device-specific and systemd deployment artifacts are removed after the container reaches feature parity. |
| NET-005 | Keep live data focused on Google Sheets. | Google Sheets is the only supported live data provider. The app uses link-readable, read-only sheet URLs. CSV files remain demo/test-only. |
| NET-006 | Provide an operator health check. | Documentation identifies a non-sensitive health check suitable for local service monitoring and reverse proxies. |

### 5.5 Container distribution

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| CTR-001 | Publish an official OCI image. | Every stable tag publishes a versioned image to GitHub Container Registry; the image is not published from untrusted pull-request code. |
| CTR-002 | Support common host architectures. | The release image includes `linux/amd64` and `linux/arm64` manifests and passes smoke tests for both build targets. |
| CTR-003 | Run with least privilege. | The runtime image uses a non-root user, contains runtime dependencies only, provides a health check, and does not bake secrets, local configuration, demo captures, development tools, or caches into image layers. |
| CTR-004 | Keep host exposure safe. | Streamlit listens on the container interface, while documented `docker run` and Compose examples publish port 8501 to host loopback by default. LAN publishing is explicit. |
| CTR-005 | Provide demo and live container paths. | A user can run demo mode without mounts. Live mode mounts Streamlit secrets read-only and mounts only the writable state directory required by the app/notifier. |
| CTR-006 | Tag container releases predictably. | Release images have immutable version tags plus moving major/latest tags and basic OCI source/version labels. |

### 5.6 Brand, README, and screenshots

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| BRD-001 | Create an original vector logo. | `assets/logo.svg` uses simple editable SVG geometry, includes `<title>` and `<desc>`, renders at 16, 64, and 220 pixels, works on light and dark backgrounds, and does not copy Roci or Tiller artwork. |
| BRD-002 | Align branding with the dashboard. | The logo uses the established blue, green, gold, and dark palette and communicates “financial rows becoming insight” or an equivalent selected concept. |
| BRD-003 | Give the README a product-first hero. | README includes centered logo/title/tagline, a small link row, no more than five useful badges, a representative screenshot, feature summary, and immediate demo path before developer details. |
| BRD-004 | Keep the README concise. | Deep setup, schema, Linux container, Discord, network, contribution, and release material moves to linked documents under `docs/`. README remains a high-value landing page rather than the complete operator manual. |
| IMG-001 | Capture screenshots only from demo data. | The capture process does not use live Sheets or local settings. Captures include a visible demo indicator and contain no real identifiers. |
| IMG-002 | Document screenshot provenance. | A short capture checklist records demo mode, viewport, page, and date. The first release does not add a browser-automation dependency solely for README images. |
| IMG-003 | Cover representative UI. | At minimum, committed images show Home, Spending by Category, Budget, Financial Independence, and Data Health; one narrow viewport is reviewed for responsive behavior. |

### 5.7 Documentation, compatibility, and community

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| DOC-001 | Document the first-success path. | A fresh user can bootstrap and run demo mode using only commands copied from README. |
| DOC-002 | Document live Tiller configuration. | Setup explains the four tabs, exact URL/`gid` requirement, sharing implications, secret permissions, and validation command. |
| DOC-003 | Publish a schema contract. | Documentation lists required and optional columns, sign conventions, joins, supported date forms, category semantics, and behavior for unknown columns. |
| DOC-004 | State compatibility policy. | The repository states its Linux container architectures, Python policy, Streamlit version policy, and Tiller schema assumptions. Other operating systems receive no host-specific deployment guides. |
| COM-001 | Add contributor and issue guidance. | Concise `CONTRIBUTING.md`, `SECURITY.md`, one bug-report template, and one pull-request template exist and point to real commands. |
| COM-002 | Keep community policy proportional. | Templates direct users to bugs, questions, and feature discussions without requesting financial data. Add broader policy files only if contribution volume creates a need. |

### 5.8 CI, security, and release

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| CI-001 | Test the documented runtime. | Linux runs full source validation. Multi-architecture container builds and smoke tests cover `linux/amd64` and `linux/arm64`; native desktop setup matrices are not required. |
| CI-002 | Protect private data in current files and history. | CI runs the current privacy checker. Before the repository becomes public, a one-time local history scan checks all refs. |
| CI-003 | Review dependencies and licenses. | Automated dependency updates are enabled. A one-time pre-release review records incompatible dependency licenses or known critical advisories. |
| CI-004 | Verify documentation and assets. | CI checks internal links, required community files, SVG parseability/accessibility metadata, README image paths, and `git diff --check`. |
| REL-001 | Define versioning and changelog policy. | `CHANGELOG.md` is latest-first and human-oriented. The stable 1.x compatibility policy and breaking-change notation are documented. |
| REL-002 | Provide a release verification command. | `task release:check` is non-interactive, runs required local gates once, emits a clear summary, and returns non-zero when any gate fails. |
| REL-003 | Automate GitHub and container releases from tags. | A `v*` tag workflow verifies the tag matches `pyproject.toml`, runs release gates, publishes the multi-architecture GHCR image, and creates a GitHub Release. It does not publish to PyPI. |
| REL-004 | Ship `v1.0.0` as a stable public release. | Configuration keys, documented Task commands, Google Sheets schema expectations, and container invocation form a documented 1.x compatibility contract. Release notes state security boundaries, supported configuration, known limitations, and upgrade expectations. |

## 6. Quality attributes

| Attribute | Requirement |
| --- | --- |
| Privacy | Demo, screenshots, diagnostics, logs, tests, and release artifacts must never require or expose personal financial data. |
| Security | Loopback is the default. Secrets are ignored, permission-restricted where supported, and never printed by diagnostics. |
| Reliability | Demo and doctor commands have bounded startup/connection timeouts, deterministic exit behavior, and actionable errors. |
| Maintainability | Configuration and data-source selection have one owner each. Pages consume validated objects and do not implement their own precedence rules. |
| Portability | The OCI image supports `linux/amd64` and `linux/arm64`. Documentation describes Linux container deployment only and does not prevent use through compatible container runtimes on other hosts. |
| Accessibility | Logo metadata, alt text, keyboard navigation, color contrast, value-hiding behavior, and narrow layouts receive explicit review. |
| Performance | Demo startup and common pages remain interactive with the current synthetic dataset. Container startup and health readiness are bounded. A larger synthetic dataset is used for a non-blocking baseline before `v1.0.0`. |
| Operability | Human-readable diagnostics, container health checks, Compose commands, and clear network profiles support routine operation. |
| Compatibility | Breaking changes to documented configuration, commands, sheet requirements, or container usage require a new major version. Additive settings and pages may ship in minor versions. |

## 7. Assumptions and constraints

- Streamlit remains the application framework.
- Google Sheets is the only live data source for `v1.0.0`; CSV input is supported only for the bundled synthetic demo and tests.
- Google Sheets access uses link-readable read-only URLs. Service accounts and write access are not part of the product.
- The four current logical sheets remain the supported minimum.
- The repository continues to use uv and Task with exact lockfile pins.
- Standard-library `tomllib` is preferred over adding a configuration dependency.
- Demo data may be relocated, but tests must keep a single source of truth.
- Personal local overrides are not committed, even when they are convenient defaults for the maintainer.
- Public screenshots are generated only from synthetic demo data.

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| Configuration work becomes a general framework. | Support only current household/deployment choices and one local override layer. Defer plugin/provider registration. |
| Demo and test fixtures diverge. | Make demo data the shared canonical synthetic dataset. |
| Link-readable Google Sheets sharing is misunderstood. | Explain that anyone with the URL may be able to read the workbook and keep the app read-only. |
| Logo resembles Tiller or Roci branding too closely. | Explore multiple simple concepts, document originality constraints, and review at small sizes before selection. |
| Screenshot tooling adds heavy maintenance. | Capture a small named set manually from canonical demo mode and record the exact capture context. |
| Deployment paths diverge. | Remove device-specific and systemd paths after the Linux container supports demo, live data, health checks, updates, and notifier state. |
| Personal defaults leak through screenshots or config examples. | Run privacy checks over assets/config and require demo-only capture provenance. |
| Container port publishing bypasses the loopback default. | Bind Streamlit inside the container as required, but publish to `127.0.0.1` on the host in every default command and Compose file. |
| ARM64 images build but fail at runtime. | Build both architectures and run an ARM64 container smoke test before release. |

## 9. Phased delivery

The implementation phases and merge boundaries are defined in `PLAN.md`. Each phase must be independently reviewable and leave `main` usable. Later phases may refine earlier docs, but must not rely on an unmerged private branch.

## 10. Audit and validation policy

For every phase, fix all P1/P2 findings. Fix P3 findings when inexpensive or explicitly required; otherwise record them. Rerun affected specialist checks after fixes and run one aggregate verification after convergence. Do not use an unbounded “resolve every finding until perfect” gate.
