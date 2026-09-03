from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

from demo.pages.streamlit_compat import install_streamlit_compatibility


def test_legacy_runtime_ignores_new_widget_arguments() -> None:
    """The temporary bridge lets the old browser runtime run current widgets."""

    def toggle(*args: object, **kwargs: object) -> str:
        assert "persist_state" not in kwargs
        return "selected"

    def columns(*args: object, **kwargs: object) -> str:
        assert "wrap" not in kwargs
        return "columns"

    class LegacyContainer:
        def container(self, *args: object, **kwargs: object) -> str:
            assert "wrap" not in kwargs
            return "container"

    legacy_streamlit = SimpleNamespace(toggle=toggle, columns=columns)
    install_streamlit_compatibility(legacy_streamlit, LegacyContainer)

    container = LegacyContainer()
    assert legacy_streamlit.toggle("Visible", persist_state="page") == "selected"
    assert legacy_streamlit.columns([1, 1], wrap=False) == "columns"
    assert container.container(horizontal=True, wrap=True, vertical_alignment="bottom") == "container"
    skeleton = cast(Callable[..., LegacyContainer], object.__getattribute__(container, "skeleton"))
    assert skeleton(height=300) is container

    patched_toggle = legacy_streamlit.toggle
    patched_cache_data = legacy_streamlit.cache_data
    install_streamlit_compatibility(legacy_streamlit, LegacyContainer)
    assert legacy_streamlit.toggle is patched_toggle
    assert legacy_streamlit.cache_data is patched_cache_data


def test_legacy_runtime_recomputes_cached_functions() -> None:
    """The browser bridge avoids cache deserialization on every rerun."""

    legacy_streamlit = SimpleNamespace()
    install_streamlit_compatibility(legacy_streamlit)
    calls = 0

    def analyze_balances() -> int:
        nonlocal calls
        calls += 1
        return calls

    cached_analysis = cast(
        Callable[[], int],
        legacy_streamlit.cache_data(show_spinner=False)(analyze_balances),
    )
    assert cached_analysis() == 1
    assert cached_analysis() == 2
    legacy_streamlit.cache_data.clear()


def test_current_runtime_does_not_replace_supported_widgets() -> None:
    """The bridge leaves a runtime with native support unchanged."""

    def toggle(*args: object, persist_state: str | None = None, **kwargs: object) -> str:
        return persist_state or "default"

    def columns(*args: object, wrap: bool = True, **kwargs: object) -> bool:
        return wrap

    def cache_data(
        function: Callable[..., object] | None = None,
        **kwargs: object,
    ) -> Callable[..., object] | Callable[[Callable[..., object]], Callable[..., object]]:
        del kwargs
        if function is not None:
            return function
        return lambda decorated: decorated

    class CurrentContainer:
        def container(self, *, wrap: bool = True, **kwargs: object) -> bool:
            del kwargs
            return wrap

        def skeleton(self, **kwargs: object) -> str:
            return "native"

    current_streamlit = SimpleNamespace(
        toggle=toggle,
        columns=columns,
        cache_data=cache_data,
    )
    install_streamlit_compatibility(current_streamlit, CurrentContainer)

    assert current_streamlit.toggle("Visible", persist_state="page") == "page"
    assert current_streamlit.columns([1, 1], wrap=False) is False
    assert current_streamlit.cache_data is cache_data
    assert CurrentContainer().container(wrap=False) is False
    assert CurrentContainer().skeleton(height=300) == "native"
