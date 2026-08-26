"""Start Streamlit with validated network and data-source settings."""

from __future__ import annotations

import argparse
import ipaddress
import os
import subprocess
import sys
from collections.abc import Sequence


DEFAULT_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 8501


def _address(value: str) -> str:
    """Return a validated IP address or localhost name."""
    normalized = value.strip()
    if normalized.casefold() == "localhost":
        return "localhost"
    try:
        return str(ipaddress.ip_address(normalized))
    except ValueError as error:
        raise argparse.ArgumentTypeError("address must be localhost or a valid IP address") from error


def _port(value: str) -> int:
    """Return a validated TCP port."""
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer between 1 and 65535") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer between 1 and 65535")
    return port


def _is_loopback(address: str) -> bool:
    """Return whether the address accepts local connections only."""
    return address == "localhost" or ipaddress.ip_address(address).is_loopback


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start Tiller Streamlit with validated local network settings.",
        epilog="Exit code 2 means invalid command usage. Streamlit exit codes pass through unchanged.",
    )
    parser.add_argument("--address", type=_address, default=DEFAULT_ADDRESS)
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT)
    parser.add_argument("--data-source", choices=("demo", "google_sheets"), default="google_sheets")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the application and return the Streamlit process status."""
    arguments = _parser().parse_args(argv)
    if not _is_loopback(arguments.address):
        print(
            "WARNING: The app has no login screen. Use this address only on a trusted network.",
            file=sys.stderr,
        )

    environment = os.environ.copy()
    environment["TILLER_DATA_SOURCE"] = arguments.data_source

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "Home.py",
        f"--server.address={arguments.address}",
        f"--server.port={arguments.port}",
    ]
    return subprocess.run(command, check=False, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
