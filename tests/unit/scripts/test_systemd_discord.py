from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_SCRIPT = REPO_ROOT / "scripts" / "systemd-discord.sh"

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="systemd rendering is Linux-only")


def render(kind: str, **overrides: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "REPO_ROOT": str(REPO_ROOT),
            "SERVICE_HOME": "/home/tiller",
            "SERVICE_USER": "tiller",
            **overrides,
        }
    )
    result = subprocess.run(
        ["sh", str(SERVICE_SCRIPT), kind],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_service_uses_checkout_runtime_retries_and_security_settings() -> None:
    unit = render("render-service")

    assert "User=tiller" in unit
    assert f"WorkingDirectory={REPO_ROOT}" in unit
    assert f'ExecStart="{REPO_ROOT}/.venv/bin/python" "{REPO_ROOT}/scripts/weekly-discord-summary.py"' in unit
    assert "send --output=json" in unit
    assert "uv run" not in unit
    assert 'Environment="HOME=/home/tiller"' in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=5min" in unit
    assert "StartLimitBurst=3" in unit
    assert "NoNewPrivileges=true" in unit
    assert "PrivateTmp=true" in unit
    assert "UMask=0077" in unit


def test_timer_uses_local_sunday_schedule_and_persistence() -> None:
    unit = render("render-timer")

    assert "OnCalendar=Sun *-*-* 20:00:00" in unit
    assert "Persistent=true" in unit
    assert "Unit=tiller-discord-weekly.service" in unit
    assert "WantedBy=timers.target" in unit


def test_service_escapes_systemd_path_specifiers() -> None:
    unit = render("render-service", REPO_ROOT="/srv/Tiller App%prod")

    assert r"WorkingDirectory=/srv/Tiller\x20App%%prod" in unit
    assert 'ExecStart="/srv/Tiller App%%prod/.venv/bin/python"' in unit
