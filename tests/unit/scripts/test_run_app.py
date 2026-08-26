from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from scripts.run_app import main


@pytest.mark.parametrize("address", ["127.0.0.1", "::1", "localhost"])
def test_loopback_launch_has_no_network_warning(address: str, capsys: pytest.CaptureFixture[str]) -> None:
    completed: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(args=[], returncode=0)

    with patch("scripts.run_app.subprocess.run", return_value=completed) as run:
        assert main(["--address", address, "--port", "8601", "--data-source", "demo"]) == 0

    command = run.call_args.args[0]
    environment = run.call_args.kwargs["env"]
    assert "--server.port=8601" in command
    assert environment["TILLER_DATA_SOURCE"] == "demo"
    assert capsys.readouterr().err == ""


def test_non_loopback_launch_prints_warning(capsys: pytest.CaptureFixture[str]) -> None:
    completed: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(args=[], returncode=0)

    with patch("scripts.run_app.subprocess.run", return_value=completed):
        assert main(["--address", "0.0.0.0"]) == 0

    assert "no login screen" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        ["--address", "example.com"],
        ["--port", "0"],
        ["--port", "65536"],
        ["--port", "not-a-port"],
    ],
)
def test_invalid_network_values_exit_with_usage_error(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(arguments)

    assert error.value.code == 2


def test_streamlit_status_passes_through() -> None:
    completed: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(args=[], returncode=7)

    with patch("scripts.run_app.subprocess.run", return_value=completed) as run:
        assert main([]) == 7

    assert run.call_args.kwargs["env"]["TILLER_DATA_SOURCE"] == "google_sheets"
