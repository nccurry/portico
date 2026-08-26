from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _section(document: str, start: str, end: str | None = None) -> str:
    section = document.split(start, maxsplit=1)[1]
    return section.split(end, maxsplit=1)[0] if end else section


def test_dockerfile_uses_locked_non_root_runtime_with_healthcheck() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "python:3.14.6-slim-bookworm" in dockerfile
    assert "ghcr.io/astral-sh/uv:0.12.1" in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "chown tiller:tiller /app/.local" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8501/_stcore/health" in dockerfile
    assert 'org.opencontainers.image.licenses="Apache-2.0"' in dockerfile
    assert not any(line.startswith("COPY . ") for line in dockerfile.splitlines())


def test_compose_live_mode_has_safe_network_and_mounts() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    app = _section(compose, "x-app: &app", "services:")
    live = _section(compose, "  live:", "  notifier:")

    assert "read_only: true" in app
    assert "no-new-privileges:true" in app
    assert "cap_drop:" in app
    assert "TILLER_DATA_SOURCE: google_sheets" in live
    assert '"${HOST_ADDRESS:-127.0.0.1}:${PORT:-8501}:8501"' in live
    assert "target: /app/.streamlit/secrets.toml" in live
    assert "target: /app/config" in live
    assert "read_only: true" in live
    assert "create_host_path: false" in live
    assert "TZ: ${TZ:-Etc/UTC}" in live


def test_demo_profile_needs_no_secret_mount() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    demo = _section(compose, "  demo:", "  live:")

    assert "TILLER_DATA_SOURCE: demo" in demo
    assert "secrets.toml" not in demo


def test_notifier_is_one_shot_with_persistent_state() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    notifier = _section(compose, "  notifier:", "\nvolumes:\n")

    assert "entrypoint: [python, scripts/weekly-discord-summary.py]" in notifier
    assert "command: [check]" in notifier
    assert "target: /app/.local" in notifier
    assert "restart:" not in notifier


def test_task_network_and_container_commands_are_explicit() -> None:
    taskfile = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")

    assert "ADDRESS: '{{default \"127.0.0.1\" .ADDRESS}}'" in taskfile
    assert "run:lan:" in taskfile
    assert "--address=0.0.0.0" in taskfile
    assert "container:demo:" in taskfile
    assert "container:live:" in taskfile
    assert "systemd" not in taskfile
    assert "service:install" not in taskfile
