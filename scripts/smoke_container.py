#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14.6,<3.15"
# dependencies = []
# ///
"""Build and health-test the Portico demo container."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from contextlib import suppress
from urllib.request import urlopen

DEFAULT_IMAGE = "portico:smoke"


def run(command: Sequence[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a Docker command."""
    return subprocess.run(command, check=True, capture_output=capture_output, text=True)


def published_port(output: str) -> int:
    """Return the host port from Docker's port output."""
    lines = output.strip().splitlines()
    if not lines:
        raise ValueError("Docker did not publish a port")
    first_line = lines[0]
    try:
        return int(first_line.rsplit(":", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"Unexpected docker port output: {first_line}") from error


def wait_until_healthy(port: int, timeout: float) -> None:
    """Wait until Streamlit reports healthy and serves the app."""
    deadline = time.monotonic() + timeout
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    app_url = f"http://127.0.0.1:{port}/"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=3) as response:
                if response.status != 200:
                    raise RuntimeError(f"Health endpoint returned {response.status}")
            with urlopen(app_url, timeout=3) as response:
                if response.status != 200:
                    raise RuntimeError(f"App endpoint returned {response.status}")
            return
        except Exception as error:
            last_error = error
            time.sleep(1)

    raise TimeoutError(f"Portico did not become healthy within {timeout:g} seconds") from last_error


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--image", default=DEFAULT_IMAGE)
    result.add_argument("--platform", default=None)
    result.add_argument("--skip-build", action="store_true")
    result.add_argument("--timeout", type=float, default=90)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Build, start, probe, and stop a demo container."""
    args = parser().parse_args(argv)
    name = f"portico-smoke-{uuid.uuid4().hex[:12]}"
    container_attempted = False

    try:
        if not args.skip_build:
            command = ["docker", "build", "--tag", args.image]
            if args.platform:
                command.extend(("--platform", args.platform))
            run((*command, "."))

        container_attempted = True
        run(
            (
                "docker",
                "run",
                "--detach",
                "--name",
                name,
                "--read-only",
                "--tmpfs",
                "/tmp:size=64m,mode=1777",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--env",
                "PORTICO_CONFIG_PATH=/app/config/demo.toml",
                "--publish",
                "127.0.0.1::8501",
                args.image,
            ),
            capture_output=True,
        )
        port_result = run(("docker", "port", name, "8501/tcp"), capture_output=True)
        wait_until_healthy(published_port(port_result.stdout), args.timeout)
        print(f"Container {args.image} passed the demo health check.")
        return 0
    except (OSError, subprocess.CalledProcessError, TimeoutError, ValueError) as error:
        print(f"Container smoke test failed: {error}", file=sys.stderr)
        if container_attempted:
            with suppress(OSError):
                subprocess.run(("docker", "logs", name), check=False)
        return 1
    finally:
        with suppress(OSError):
            subprocess.run(("docker", "rm", "--force", name), check=False, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
