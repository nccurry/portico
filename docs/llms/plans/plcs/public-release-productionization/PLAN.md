# Public Release Productionization — Phased Delivery Plan

Status: Phases 1–6 implemented locally; Pages deployment follows the merge to `main`

Target: stable `v1.0.0`

## Delivery principles

- Merge each phase independently and keep `main` usable after every merge.
- Preserve the maintainer workflow through ignored local overrides before removing personal constants.
- Use one Google Sheets integration: link-readable, read-only workbook URLs.
- Build demo mode before producing public screenshots.
- Make loopback networking the default; make LAN access an explicit choice.
- Treat the Linux container as the single documented deployment runtime. Do not add host-specific guides for other operating systems.
- Treat GitHub Pages as a demo host only. It never replaces the Linux container or GitHub releases.
- Keep the v1 solution small: no service accounts, auth framework, provider abstraction, Kubernetes, PyPI package, SBOM program, or automated browser screenshot system.
- A `1.0.0` release declares the documented configuration, task commands, Google Sheets schema expectations, and container invocation as the stable 1.x public contract.

## Phase overview

| Phase | Outcome | Suggested merge unit | Depends on |
| --- | --- | --- | --- |
| 0 | Requirements and architecture agreed | Planning docs | None |
| 1 | Repository is legally and socially consumable | License, metadata, minimal policies | Phase 0 |
| 2 | Personal behavior moves behind validated settings | Config and defaults | Phase 1 |
| 3 | Anyone can run and diagnose the app without private data | Demo and doctor | Phase 2 |
| 4 | Linux container deployment and network behavior are documented and safe by default | Network and deployment | Phase 2 |
| 5 | Public landing experience is polished | Logo, README, docs, screenshots | Phases 3–4 |
| 6 | Browser compatibility is tested and GitHub Pages publishes an honest demo | GitHub Pages demo or static fallback | Phases 3 and 5 |
| 7 | CI and release mechanics enforce the public contract | CI, image publishing, release | Phases 1–6 |
| 8 | Stable release is verified and published | `v1.0.0` | Phase 7 |

## Phase 0 — Plan and decisions

### Objective

Agree on the public contract before changing runtime behavior.

### Resolved decisions

- License: Apache-2.0 for all original repository code.
- First public version: stable `v1.0.0`.
- Deployment documentation: Linux containers only. The OCI image remains usable through standard container runtimes on other hosts without host-specific guides.
- Live data: Google Sheets only, using link-readable workbook URLs. No service accounts.
- Offline/demo data: committed synthetic CSV fixtures only.
- Security posture: personal-app safeguards, not enterprise controls.
- Image registry: GitHub Container Registry (GHCR) only.
- Copyright: use `Copyright 2026 Nick Curry and contributors` once in the README legal section. Do not add per-file copyright headers.
- Device-specific deployment: remove it from the public surface; do not document particular boards or appliances.

### Deliverables

- `SRD.md`
- `SADD.md`
- This phased plan
- A short decision record for each remaining choice

### Exit gate

- Requirement IDs are testable and mapped to an owner and phase.
- Deferred items are explicit.
- All release-shaping decisions are resolved.
- `git diff --check` passes.

## Phase 1 — Public foundation

### Objective

Make the repository legally reusable, clearly unofficial, and easy to contribute to without changing dashboard behavior.

### Work items

1. Add the canonical Apache License 2.0 text as `LICENSE`.
2. Add one copyright line to the README legal section. Apache-2.0 does not require a separate copyright file or per-file copyright headers.
3. Add `NOTICE` only if a bundled third-party asset or dependency requires an attribution notice.
4. Complete `[project]` metadata in `pyproject.toml`: description, README, SPDX license, author/maintainer, project URLs, and supported Python version.
5. Add an unofficial/non-affiliation Tiller disclaimer.
6. Add only the useful public files: concise `CONTRIBUTING.md`, concise `SECURITY.md`, one bug-report template, and one pull-request template.
7. Ensure templates say not to include workbook contents, credentials, or financial records.
8. Add `CHANGELOG.md` with an Unreleased section.
9. Add `docs/releasing.md` with versioning and release prerequisites.
10. Review tracked agent/editor files; retain contributor guidance and remove personal tool preferences.

### Validation and acceptance

- Parse project metadata and verify required fields.
- Validate documentation links and run the privacy checker.
- Run lint, focused tests, and `git diff --check`.
- Apache-2.0, attribution, and the unofficial status are unambiguous.
- No runtime behavior changes.

### Suggested pull request

`docs(public): add license metadata and contribution basics`

## Phase 2 — Validated configuration and safe defaults

### Objective

Move household-specific behavior out of source constants while retaining sensible defaults and a one-file local override.

### Approved tracked defaults

Keep the maintainer's current anonymous numeric defaults unchanged:

| Setting | Proposed default |
| --- | --- |
| Expense outlier threshold | `$3,000` |
| Income outlier threshold | `$20,000` |
| Large transaction threshold | `$500` |
| Savings target | `20%` |
| FI expected annual return | `7%` |
| FI withdrawal rate | `4%` |
| FI spending lookback | `12 months` |
| FI projection horizon | `50 years` |
| Duplicate minimum amount | `$10` |
| Duplicate date window | `1 day` |

Keep the current anonymous report defaults as well, including common category/group exclusions and Tiller semantics such as excluding transfers from spending totals. Replace only named FI accounts with rules that include asset accounts in common groups such as `Savings`, `Investments`, and `Retirement`.

Do not track exact account names, employer names, institutions, personal merchant aliases, Discord destinations, or household-only/misspelled categories. Put exact replacements in ignored `config/local.toml`. This gives new users working defaults while making the maintainer's current behavior one local file away.

### Work items

1. Inventory `src/constants.py` and classify every value as application behavior, deployment choice, visual detail, or household policy.
2. Add `config/defaults.toml` containing the current approved anonymous defaults without changing their values.
3. Add `config/local.example.toml`; ignore `config/local.toml`.
4. Add a small `src/config.py` loader using `tomllib` with precedence: tracked defaults, local overrides, then explicit runtime values where needed.
5. Validate unknown keys, types, ranges, duplicates, and path values with useful errors.
6. Add `task config:init`; copy the example only when the destination does not exist.
7. Migrate report filters, FI assumptions, subscription exclusions, and duplicate thresholds.
8. Keep sheet URLs and webhook values in `.streamlit/secrets.toml` rather than TOML configuration.
9. Create the maintainer's ignored local migration checklist without committing personal values.
10. Update tests to inject settings instead of mutating module globals.

### Validation and acceptance

- Unit tests cover precedence, missing local file, invalid TOML, unknown keys, types, and ranges.
- Page tests prove tracked defaults have intentional behavior.
- Privacy tests reject personal identifiers in tracked configuration.
- `task config:init` never overwrites.
- A new user gets useful behavior without editing Python.
- The maintainer can restore exact personal behavior with ignored overrides only.

### Suggested pull request

`feat(config): add validated defaults and local overrides`

## Phase 3 — Demo mode and configuration doctor

### Objective

Provide a useful first run without private data and a simple path from demo mode to a live Google Sheet.

### Work items

1. Promote synthetic fixtures to `demo/data/` as the canonical demo dataset.
2. Preserve a reference date and document fixture provenance and deliberate edge cases.
3. Allow committed CSV files only under the documented demo path.
4. Add one explicit branch in the existing spreadsheet loader: demo reads canonical CSV fixtures; live reads link-readable Google Sheets.
5. Add a shared, visible demo banner.
6. Add `task demo` with loopback binding, no secrets requirement, and no external calls.
7. Ensure `task run` never silently falls back to demo mode.
8. Add `scripts/doctor.py` and `task doctor`.
9. Check configuration presence, four sheet URLs, numeric `gid` values, workbook access, expected columns, and basic parsing.
10. Keep doctor output short and human-readable; return nonzero on failure and never print sheet data or secret values.
11. Add bounded timeouts to external and health checks.
12. Use the canonical demo data in AppTest and integration fixtures.

### Validation and acceptance

- Fail tests if demo mode invokes the Google connector.
- Run a smoke test for every page in demo mode.
- Test missing/malformed/duplicate `gid` values and wrong-tab schemas.
- Test doctor exit codes, redaction, and actionable messages.
- A fresh checkout reaches a useful dashboard without Drive or Sheets access.
- Live mode supports the documented link-readable Google Sheets setup only.

### Suggested pull requests

1. `feat(demo): add canonical synthetic dataset and offline mode`
2. `feat(diagnostics): add configuration doctor`

## Phase 4 — Linux container deployment and networking

### Objective

Make the app easy to run on common platforms while keeping local access as the default.

### Work items

1. Change the default bind address from `0.0.0.0` to `127.0.0.1`.
2. Add `task run:lan` as the explicit all-interface command and print a short reminder that the app has no login screen.
3. Preserve validated `ADDRESS` and `PORT` overrides.
4. Add a multi-stage `Dockerfile` and `.dockerignore`.
5. Run the container as a non-root user with a health check.
6. Add Compose examples for demo and live modes. Demo needs no secrets or host data; live mounts `.streamlit/secrets.toml` read-only; host publication defaults to `127.0.0.1`.
7. Build `linux/amd64` and `linux/arm64` images for common x86-64 and ARM64 Linux container hosts.
8. Document local, trusted LAN, private VPN, and user-managed reverse-proxy modes for Linux container deployment.
9. State plainly that Google Sheets must be link-readable and that anyone with the link may be able to read it. Do not add service-account instructions.
10. Remove device-specific and systemd deployment scripts, tasks, tests, and documentation after the container path reaches feature parity.

### Validation and acceptance

- Assert Task and Compose loopback defaults.
- Assert LAN mode uses `0.0.0.0` only when requested.
- Validate address and port inputs.
- Build and smoke-test both architectures in CI.
- Verify the demo container starts healthy without secrets.
- Network and Google sharing limitations are stated without enterprise security machinery.

### Suggested pull requests

1. `feat(deploy): default local networking to loopback`
2. `feat(container): add Linux demo and live images`

## Phase 5 — Brand, README, documentation, and screenshots

### Objective

Turn the repository into a polished landing page with truthful public visuals.

### Work items

1. Create three original SVG logo concepts using simple geometry and the dashboard palette.
2. Review each at favicon, navigation, and README sizes on light and dark backgrounds.
3. Select one concept and keep only the final useful assets.
4. Add accessible SVG `<title>` and `<desc>` elements.
5. Build a Roci-inspired README structure without copying artwork or prose: centered hero, concise tagline, restrained badges, screenshot, container demo quick start, live Google Sheets setup, features, docs map, license, and disclaimer.
6. Move detailed Linux deployment, configuration, Google Sheets, Discord, troubleshooting, and release procedures into focused guides.
7. Manually capture Home, Spending, Budget, FI, and Data Health from canonical demo mode.
8. Record the exact commit, demo reference date, viewport, and command in a screenshot provenance note.
9. Review desktop and narrow widths; recapture only when the UI materially changes.
10. Add descriptive alt text and captions.

### Validation and acceptance

- Parse SVG as XML and verify accessible metadata.
- Validate README and documentation links and image paths.
- Run privacy checks over text and asset metadata.
- Confirm every screenshot shows the demo banner and contains no personal names, values, URLs, or notifications.
- Branding is original, legible at small sizes, and distinct from Roci and official Tiller marks.
- Screenshots remain reproducible without adding a browser automation stack.

### Suggested pull requests

1. `feat(brand): add original logo and public visual identity`
2. `docs(public): rebuild readme and publish setup guides`
3. `docs(images): add demo screenshots and provenance`

## Phase 6 — Browser demo and GitHub Pages

### Objective

Test whether Portico can run fully in the browser. Publish it from GitHub Pages only when the complete demo works.

### Result

The 2026-08-29 compatibility test used stlite 1.8.1 with the complete app and synthetic data. The runtime started Portico but failed on Streamlit 1.60 APIs. The first confirmed error was the unsupported `width` argument on `st.toggle`.

The phase uses the planned static fallback. The GitHub Pages workflow publishes the five synthetic screenshots, the logo, local demo instructions, and the source commit. Portico does not include browser-only API shims.

### Work items

1. Run a time-boxed stlite 1.8.1 test with the complete Portico app and canonical demo data.
2. Record the first blocking Streamlit compatibility error.
3. Keep browser-only shims and a second dashboard implementation out of the repository.
4. Build a static gallery from the committed logo and five canonical demo screenshots.
5. Record the deployed source commit and link to the canonical repository.
6. Publish the gallery from `main` through GitHub Actions.
7. Enable GitHub Pages with GitHub Actions as its source and record the public URL.
8. Add the hosted gallery link to the README only after the public URL passes the release gate.

### Validation and acceptance

- GitHub Pages serves only static HTML, JavaScript, WebAssembly, and data files.
- The compatibility result names the tested stlite and Streamlit versions and the first blocking API.
- The static fallback uses only canonical synthetic screenshots and contains no private services or data.
- The deployed page records the Git commit and links to the GitHub source.
- The static gallery replaces the interactive claim because stlite is not compatible.
- A failed stlite test does not block the container release.

### Suggested pull request

`feat(web-demo): publish the Portico demo on GitHub Pages`

## Phase 7 — CI and release automation

### Objective

Make source and container releases repeatable with a small set of useful checks.

### Work items

1. Organize CI into Linux gates for lint, type checks, tests, coverage, privacy, demo smoke, and documentation links.
2. Build and smoke-test the container on pull requests.
3. Add dependency update automation with grouped lockfile updates.
4. Add `task release:check` for required files, version/changelog consistency, tests, privacy, docs links, and a demo-container smoke test.
5. Perform one dependency advisory/license review and one full-history secret scan before changing repository visibility.
6. Add a `vX.Y.Z` tag workflow that verifies the tag/version, reruns release checks, publishes `linux/amd64` and `linux/arm64` images to GHCR, and creates a GitHub Release from curated notes.
7. Tag images with the exact version, major/minor aliases, and `latest` for stable releases.
8. Add basic OCI labels for source URL, revision, version, and Apache-2.0 license.
9. Document minimal branch protection, required checks, and how to correct a bad tag or release note.

### Validation and acceptance

- Validate workflow syntax and run local equivalents.
- Test tag/version comparison logic.
- Build and smoke-test both container architectures.
- Run `task release:check` from a clean worktree.
- A valid tag produces matching source and multi-architecture container releases.
- No SBOM, signing, provenance service, or continuous enterprise scanner is required for v1.

### Suggested pull request

`ci(release): add source checks and multi-architecture releases`

## Phase 8 — Stable `v1.0.0` release

### Objective

Verify the complete public experience and publish the stable first release.

### Work items

1. Freeze scope and move completed changelog entries into `1.0.0`.
2. Run `task release:check` from a clean worktree.
3. Complete the one-time repository-history secret scan and dependency/license review.
4. Start the demo and live containers from a clean Linux host.
5. Run `task doctor` against demo mode, one valid live workbook, and intentionally malformed configuration.
6. Review every image and SVG for originality and privacy.
7. Copy/paste every README quick-start command into a fresh Linux environment.
8. Document known limitations: link-readable Sheets, supported Tiller schema, no in-app authentication, supported image architectures, and 1.x compatibility expectations.
9. Tag `v1.0.0` only after the version and changelog commit reaches `main`.
10. Verify the GitHub Release, source archives, GHCR image tags, and container health.
11. Verify the hosted demo or static gallery and its link to the release commit.

### Acceptance

- The app is useful without access to the maintainer's files or services.
- Source and container release checks pass.
- No unresolved release-blocking findings remain.
- The documented 1.x public contract is explicit.

## Requirement traceability

| Requirement group | Design owner | Primary phase | Validation |
| --- | --- | --- | --- |
| PUB | Metadata and minimal community files | 1 | Metadata, link, privacy, and policy checks |
| CFG | `src/config.py` and TOML files | 2 | Unit, page, and privacy tests |
| DEMO | Existing spreadsheet loader, demo data, doctor | 3 | AppTest, exit-code, redaction, and no-network tests |
| NET/CTR | Taskfile, Dockerfile, Compose, Linux deployment docs | 4 | Render, build, and health tests |
| BRD/IMG | `assets/`, README, manual captures | 5 | SVG, docs, privacy, and visual reviews |
| WEB | Static gallery builder and GitHub Pages workflow | 6 | Recorded compatibility failure, canonical asset tests, and workflow contract |
| DOC/COM | README and focused public guides | 1 and 5 | Link, command, and policy review |
| CI/REL | GitHub workflows and release tasks | 7 and 8 | Clean-worktree release gate and artifact smoke |

## Aggregate verification matrix

| Gate | Phases | Command or evidence |
| --- | --- | --- |
| Privacy | All | `task privacy:check`; one-time full-history scan before public visibility |
| Lint/type | Runtime phases | `task lint` |
| Unit/integration | Runtime phases | `task test` |
| Coverage | Runtime phases | Existing source and total coverage tasks |
| Demo | 3 onward | `task demo` and all-page AppTest smoke |
| Diagnostics | 3 onward | `task doctor` and focused failure tests |
| Deployment | 4 onward | Container health and Compose checks on Linux |
| Docs/assets | 1 and 5 onward | Link checks and manual image provenance review |
| Hosted demo | 6 onward | Static artifact build, canonical asset checks, source revision validation, and deployed URL review |
| Architectures | 4 and 8 | Multi-architecture image plus clean-Linux-host container smoke |
| Release | 7–8 | `task release:check` and tag/version/changelog/image verification |

## Recommended execution order

Start with Phase 1. Phase 2 is the architectural hinge. Phases 3 and 4 can proceed independently after the settings API stabilizes. Complete demo mode before screenshots. Test browser hosting after Phase 5. Finish the hosted demo decision before locking the release workflow.
