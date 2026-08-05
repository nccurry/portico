from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_SCRIPT = REPO_ROOT / "scripts" / "systemd-service.sh"

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="systemd service rendering is Linux-only")


def render_unit(**overrides: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "ADDRESS": "0.0.0.0",
            "PORT": "8501",
            "REPO_ROOT": str(REPO_ROOT),
            "SERVICE_HOME": "/home/tiller",
            "SERVICE_USER": "tiller",
            **overrides,
        }
    )
    result = subprocess.run(
        ["sh", str(SERVICE_SCRIPT), "render"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_render_uses_checkout_runtime_and_security_settings() -> None:
    unit = render_unit()

    assert "User=tiller" in unit
    assert f"WorkingDirectory={REPO_ROOT}" in unit
    assert f'ExecStart="{REPO_ROOT}/.venv/bin/streamlit" run "{REPO_ROOT}/Home.py"' in unit
    assert "uv run" not in unit
    assert '--server.address="0.0.0.0"' in unit
    assert '--server.port="8501"' in unit
    assert "--server.headless=true" in unit
    assert "--server.runOnSave=false" in unit
    assert "--client.showErrorDetails=false" in unit
    assert 'Environment="HOME=/home/tiller"' in unit
    assert "Restart=on-failure" in unit
    assert "NoNewPrivileges=true" in unit
    assert "PrivateTmp=true" in unit
    assert "UMask=0077" in unit


def test_render_accepts_address_and_port_overrides() -> None:
    unit = render_unit(ADDRESS="127.0.0.1", PORT="8601")

    assert '--server.address="127.0.0.1"' in unit
    assert '--server.port="8601"' in unit


def test_render_escapes_systemd_path_specifiers() -> None:
    unit = render_unit(REPO_ROOT="/srv/Tiller App%prod")

    assert r"WorkingDirectory=/srv/Tiller\x20App%%prod" in unit
    assert 'ExecStart="/srv/Tiller App%%prod/.venv/bin/streamlit"' in unit
