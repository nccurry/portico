"""Root pytest configuration for shared fixture plugins."""

pytest_plugins = [
    "tests.fixtures.streamlit_runtime",
    "tests.fixtures.dataframes",
    "tests.fixtures.factories",
    "tests.fixtures.page_data",
    "tests.fixtures.integration",
]
