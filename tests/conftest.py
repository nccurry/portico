"""Root pytest configuration for shared fixture plugins."""

import os
from collections.abc import Iterator

import pytest
from pytest import MonkeyPatch

from src.config import clear_settings_cache


pytest_plugins = [
    "tests.fixtures.streamlit_runtime",
    "tests.fixtures.dataframes",
    "tests.fixtures.factories",
    "tests.fixtures.page_data",
    "tests.fixtures.integration",
]


@pytest.fixture(autouse=True)
def isolate_application_settings(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Keep ignored local settings from changing test behavior."""
    monkeypatch.setenv("PORTICO_CONFIG_PATH", os.devnull)
    clear_settings_cache()
    yield
    clear_settings_cache()
