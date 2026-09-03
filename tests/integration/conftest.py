"""Integration-test configuration for the committed synthetic workbook."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from src.config import clear_settings_cache

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEMO_CONFIG = _PROJECT_ROOT / "portico-demo.toml"


@pytest.fixture(autouse=True)
def use_committed_demo_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep synthetic-data tests on the committed demo configuration."""
    monkeypatch.setenv("PORTICO_CONFIG_PATH", str(_DEMO_CONFIG))
    clear_settings_cache()
    yield
    clear_settings_cache()
