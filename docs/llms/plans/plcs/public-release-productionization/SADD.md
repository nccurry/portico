# Public Release Productionization — Architecture and Design

Status: Proposed

Companion requirements: `SRD.md`

## 1. Goals

- Let a visitor run a complete demo before configuring private services.
- Preserve the current Google Sheets workflow.
- Provide one documented Linux container runtime path for amd64 and ARM64.
- Replace scattered household policy with one small validated settings surface.
- Default all network entry points to loopback.
- Make documentation, branding, screenshots, diagnostics, and release artifacts reproducible from public data.
- Keep the application architecture simple enough for a small open-source project.

## 2. Constraints

- Streamlit owns page routing and runtime state.
- Existing spreadsheet scrubbers and analyses should not know whether raw data came from Google Sheets or demo CSVs.
- Existing synthetic fixtures already exercise the real scrub pipeline and should be reused.
- `.streamlit/secrets.toml` remains the home for sensitive connector and webhook values.
- The application is distributed as source and a container image; no Python package publication is required.
- New production behavior must be testable without a live Google account or Discord webhook.
- Google Sheets is the only live provider. Demo CSVs are not a general import feature.
- Container builds must not require or copy local secrets.

## 3. Context

```text
                       +----------------------+
                       |  config/defaults.toml|
                       +----------+-----------+
                                  |
                       +----------v-----------+
                       | optional local config|
                       +----------+-----------+
                                  |
 +---------------+      +---------v---------+      +------------------+
 | Task / Compose|----->| validated settings|<-----| environment flags|
 +-------+-------+      +---------+---------+      +------------------+
         |                        |
         |              +---------v---------+
         +------------->| Streamlit pages   |
                        +---------+---------+
                                  |
                       +----------v-----------+
                       | raw sheet reader seam|
                       +-----+-----------+----+
                             |           |
                   +---------v--+     +--v----------------+
                   | demo CSVs  |     | Google Sheets     |
                   +------------+     +-------------------+
```

## 4. Building blocks

### 4.1 `src/config.py`

Owns application settings and precedence. Use frozen dataclasses or typed dictionaries with explicit validation; do not add Pydantic solely for configuration.

Proposed groups:

- `DataSettings`: source mode and demo-data path
- `IncomeSavingsDefaults`: thresholds, target rate, default exclusions
- `SpendingDefaults`: category/group exclusions and large-transaction threshold
- `SubscriptionDefaults`: category exclusions and detection exclusions
- `FinancialIndependenceDefaults`: rates, horizon, lookback, account-selection patterns
- `NetworkSettings`: address and port when invoked outside Streamlit config
- `NotificationDefaults`: schedule and non-secret notifier behavior

Values that remain in code:

- Required source column names
- Internal session-state keys
- Chart and table construction
- Supported page options where users are choosing interactively
- Color tokens already owned by `.streamlit/config.toml`

### 4.2 Configuration files

Proposed files:

```text
config/defaults.toml       tracked public defaults
config/local.example.toml  tracked override documentation
config/local.toml          ignored maintainer/user overrides
.streamlit/secrets.toml    ignored connection URLs and webhook secrets
```

Precedence, lowest to highest:

1. `config/defaults.toml`
2. `config/local.toml` when present
3. explicit environment or Task variables for deployment-only settings

Do not merge arbitrary environment variables into household settings. Support a small named set such as data mode, config path, address, and port.

The loader must report unknown keys. This catches misspellings and removed settings instead of silently ignoring them.

### 4.3 Spreadsheet loading

Keep loading in the existing `Spreadsheet.load()` path. Add one explicit mode branch:

- live mode reads link-readable Google Sheets through the existing Streamlit connection
- demo mode reads the matching synthetic CSV under `demo/data/`

Do not add provider interfaces, factories, or registration. Google Sheets is the only live provider. Existing scrubbers, joins, caches, and analyses remain unchanged.

### 4.4 Demo data

Move the canonical synthetic files from `tests/data/fixtures/` to `demo/data/`. Update tests to load that location. Retain provenance documentation, the reference date, and injected-edge-case notes.

Demo mode is explicit through `TILLER_DATA_SOURCE=demo` or an equivalent narrowly scoped variable set by `task demo`. Normal `task run` uses configured live data and provides a setup error when unavailable. It must not silently show demo data.

All pages render a shared demo banner. The banner must be derived from validated settings, not inferred from a missing secrets file.

### 4.5 Diagnostics

Add `scripts/doctor.py` as a focused command rather than a general management CLI.

Human mode:

```text
task doctor
```

The command prints a short pass/fail list and exits non-zero when a required check fails. It never prints complete URLs, webhook values, account names, transaction values, or dataframe samples. No JSON protocol is required for the first release.

### 4.6 Task command surface

Keep Task as the public command index:

| Command | Behavior |
| --- | --- |
| `task demo` | Start the app on loopback with synthetic data. |
| `task run` | Start on loopback with configured live data. |
| `task run:lan` | Explicitly bind to all interfaces and print a security warning. |
| `task doctor` | Validate live configuration in human-readable form. |
| `task config:init` | Copy the local settings example only when the target is absent. |
| `task container:build` | Build the local production image without secrets. |
| `task container:demo` | Run demo mode from the image and publish only to host loopback. |
| `task container:run` | Run live mode with read-only secrets and a writable state mount. |
| `task release:check` | Run the bounded release gate without prompts. |

Commands that mutate local files must fail instead of overwriting. No public command should require an interactive prompt in CI.

### 4.7 Network profiles

Use safe behavior rather than a complex profile engine:

- `task run` and `task demo`: `127.0.0.1:8501`
- `task run:lan`: `0.0.0.0:8501`, explicit warning
- Containers: Streamlit binds to `0.0.0.0` inside the network namespace, while default host publication is `127.0.0.1:8501:8501`
- Reverse proxy: documented example with authentication and TLS, but not installed automatically

Remove the existing device-specific and systemd deployment surface once the container supports live data, demo mode, health checks, upgrades, and writable notifier state. Do not retain an undocumented second deployment path.

Do not add application authentication in this change. Public exposure remains unsupported unless an authenticated reverse proxy or private VPN owns access control.

### 4.8 Container image

Add these root artifacts:

```text
Dockerfile
.dockerignore
compose.yaml
```

Image design:

- Use a pinned Python 3.14 slim base compatible with the project's lockfile.
- Use a build stage to install locked runtime dependencies only.
- Copy only runtime source, public configuration, demo data, and required assets into the final stage.
- Run as a dedicated non-root user with a fixed home and work directory.
- Expose container port 8501 and include a non-sensitive health check.
- Set the image entrypoint to the production Streamlit command.
- Keep `.streamlit/secrets.toml`, `config/local.toml`, `.local/`, tests, screenshots tooling, Git data, virtual environments, and caches outside image layers.
- Accept demo/live selection through the validated data-mode setting.
- Mount `.streamlit/secrets.toml` read-only for live mode.
- Mount `.local/` separately when Discord delivery state or other writable state is required.

`compose.yaml` is the primary Linux operator experience. It publishes to host loopback by default and uses an explicit environment variable or override for LAN exposure. Demo mode must run with no mounts. Live mode must fail clearly when the secret mount is absent.

Publish only to GitHub Container Registry as `ghcr.io/nccurry/tiller-streamlit`. Required platforms are `linux/amd64` and `linux/arm64`.

Tag policy:

- Immutable: `1.0.0` and the release commit SHA
- Moving: `1.0` and `latest`
- Pull-request builds: never pushed to the public release tags

Add basic OCI source, revision, and version labels.

### 4.9 Brand assets

Create an original logo family under `assets/`:

- `logo.svg`: square primary mark
- `logo-wordmark.svg`: optional horizontal lockup if the square mark is insufficient
- `logo-preview.png`: optional generated preview, never the canonical source

Design direction:

- Use the dashboard colors `#70A5EB`, `#57CC57`, `#F2B84B`, and the dark neutral palette.
- Explore three geometric concepts: ledger rows forming a sprout, stacked transactions forming an upward path, or four sheet tabs converging into one insight mark.
- Keep geometry distinct from Roci's faceted cube/arrows and from official Tiller marks.
- Avoid embedded raster content, fonts, filters that fail in GitHub rendering, and tiny details that disappear at favicon size.
- Include accessible SVG metadata and test light/dark README backgrounds.

The Roci influence is presentation structure: centered hero, concise tagline, high-value link row, restrained badges, strong first-success section, community links, and clear license—not copied artwork.

### 4.10 README and documentation topology

Proposed root README:

1. Centered logo, title, tagline
2. Docs/demo/setup/community link row
3. CI, Python/Streamlit, demo, and Apache-2.0 badges
4. One representative demo screenshot
5. Short product description and feature bullets
6. Two-command demo path
7. Live Tiller setup summary
8. Network/security warning
9. Documentation map
10. Development commands
11. Community, license, disclaimer, and credits

Proposed supporting docs:

```text
docs/quickstart.md
docs/configuration.md
docs/data-schema.md
docs/deployment.md
docs/discord-notifier.md
docs/security-and-privacy.md
docs/releasing.md
```

Avoid duplicating the same procedure in README and a guide. README should summarize and link.

### 4.11 Screenshots

Capture the first README images manually from explicit demo mode. Record the page, viewport, and capture date in `assets/screenshots/README.md`. Do not add Playwright or pixel-diff infrastructure solely for a few landing-page images. Add automation later only if screenshot churn becomes a real maintenance problem.

### 4.12 CI and release design

Split responsibilities without duplicating expensive work:

- Linux required lane: privacy, Ruff, mypy, unit/integration tests, coverage, demo smoke, docs/assets checks
- Container lane: build and run demo/live configuration smoke tests, inspect the runtime user and health check, and validate both amd64 and ARM64 manifests
- Dependency automation: grouped routine updates with lockfile regeneration
- Release workflow: tag/version consistency, release check, multi-architecture GHCR publish, GitHub Release

The release workflow publishes source through GitHub Releases and the runtime image through GHCR. It does not upload Python packages or deploy to any host.

### 4.13 Community files

Use the concise Roci structure as a reference, adapted to this application:

- `CONTRIBUTING.md`: bootstrap, focused checks, demo/privacy rules, docs/screenshots, merge checklist
- `SECURITY.md`: supported branch, private vulnerability reporting, no secrets in issues
- A minimal bug-report template that warns against attaching financial data
- Pull request template: behavior, validation, privacy/data provenance, screenshots when relevant

Add broader community policy files only when outside contribution volume makes them useful.

## 5. Runtime flows

### 5.1 Demo

```text
task demo
  -> Task sets explicit demo mode and loopback address
  -> config loader validates public defaults
  -> existing spreadsheet loader reads demo/data/*.csv
  -> existing spreadsheet scrubbers run
  -> pages render with demo banner
```

### 5.2 Live app

```text
task run
  -> config loader merges defaults and local overrides
  -> existing spreadsheet loader requests named Streamlit connections
  -> scrubbers validate Tiller schema
  -> pages render on loopback
```

### 5.3 Doctor

```text
task doctor
  -> load settings
  -> validate four connection URLs and gid values
  -> read each source with timeouts
  -> validate schema without emitting rows
  -> print a short result and exit
```

### 5.4 Screenshots

Run demo mode, capture the selected pages at the documented viewport, and record capture provenance beside the images.

### 5.5 Container demo

```text
task container:demo
  -> build or select the production image
  -> start as a non-root user with explicit demo mode
  -> publish container port 8501 to host 127.0.0.1 only
  -> pass the health check without secrets or writable mounts
```

### 5.6 Container live mode

```text
task container:run
  -> mount .streamlit/secrets.toml read-only
  -> mount .local only when writable state is needed
  -> use link-readable Google Sheets URLs
  -> publish to host loopback unless LAN exposure is explicit
```

## 6. Security and privacy design

- Loopback is the default at every entry point.
- Live URLs and webhooks stay in ignored Streamlit secrets.
- Local household overrides stay ignored and separate from secrets.
- Demo mode never reads live secrets, even when a secrets file exists.
- Doctor output is allow-listed rather than redacted after formatting.
- Screenshots are manually captured only from an explicit demo session.
- Public logs include source/check names and failure classes, not financial rows or URLs.
- Current-file privacy scanning remains in normal CI.
- Full-history secret scanning runs once before public visibility.
- Hide-values tests continue to cover Pandas numeric dtypes and explicitly configured Streamlit `NumberColumn`/`ProgressColumn` types.
- Documentation warns that link-readable Sheets and unauthenticated Streamlit are security boundaries, not convenience details.
- Container smoke tests verify that secrets and local overrides are absent from the final filesystem.

## 7. Test architecture

| Area | Tests |
| --- | --- |
| Config | Default load, local override, unknown keys, type/range errors, missing file behavior, precedence |
| Spreadsheet loading | Demo mapping, Google connection delegation, unsupported mode, no secret access in demo |
| Doctor | Pass/fail output, non-zero failures, safe messages, and common schema/connection failures |
| Demo UI | AppTest smoke for every page, demo banner, shared canonical data, no external calls |
| Network | Task/Compose rendered address defaults, explicit LAN mode, port validation, warning text |
| Branding/docs | SVG XML parse, title/desc, internal links, image existence, README required sections |
| Screenshots | Demo-only provenance and manual review before release |
| Release | Version/tag match, changelog entry, license/community files, clean release check |
| Privacy | Current tree, one-time pre-public history scan, fixture provenance, value-hiding column configs |
| Container | Non-root user, locked runtime deps, health check, loopback host mapping, read-only secrets, and amd64/ARM64 manifests |

## 8. Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Distribution | GitHub source release plus GHCR OCI image | Source remains transparent while the image provides one documented Linux deployment path. |
| Configuration parser | Standard-library `tomllib` | Avoid a new runtime dependency for a small static schema. |
| Data loading | One mode branch in the existing loader | Demo support does not justify a provider framework. |
| Demo fallback | Explicit only | Silent fallback could cause users to mistake synthetic results for live data. |
| Public bind | Loopback | The app has no built-in authentication. |
| Personal defaults | Track anonymous values unchanged; locally override identifying strings | Preserve the maintainer's useful defaults without publishing account, employer, institution, merchant, or destination names. |
| Screenshots | Manual demo captures | A few README images do not justify a browser-automation dependency. |
| Container | Required, multi-architecture, non-root | The container is the only documented deployment path and supports common Linux amd64 and ARM64 hosts. |
| Registry | GHCR only | One registry is sufficient for the source repository and versioned container images. |
| Copyright notice | One README line | Apache-2.0 does not require repeated copyright headers; one concise ownership line provides clarity without adding file-level boilerplate. |
| Live data providers | Google Sheets only | Keep the product focused; CSV remains synthetic demo/test infrastructure. |
| Google access | Link-readable public URL | Match the personal-budget scope and current read-only workflow. Service accounts are intentionally unsupported. |
| In-app auth | Deferred | Access control belongs at a private VPN or authenticated reverse proxy for this release. |

## 9. Deferred decisions

- Whether a horizontal logo lockup is necessary
- Whether automated screenshot comparison becomes valuable if manual captures become frequent

## 10. Phase gates

Each implementation phase has a specific gate in `PLAN.md`. Fix all P1/P2 findings. Fix P3 findings when inexpensive or explicitly required; otherwise record them. Rerun affected checks after fixes and run one aggregate verification after convergence.
