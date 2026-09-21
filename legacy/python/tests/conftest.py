"""Root pytest configuration for shared fixture plugins."""

from collections.abc import Iterator

import pytest

from src.config import clear_settings_cache

pytest_plugins = [
    "tests.fixtures.streamlit_runtime",
    "tests.fixtures.dataframes",
    "tests.fixtures.factories",
    "tests.fixtures.page_data",
    "tests.fixtures.integration",
]


@pytest.fixture(autouse=True)
def clear_application_settings_cache() -> Iterator[None]:
    """Reset cached settings between tests."""
    clear_settings_cache()
    yield
    clear_settings_cache()
