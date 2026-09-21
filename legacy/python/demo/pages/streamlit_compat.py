"""Temporary Streamlit 1.57 support for the GitHub Pages demo."""

from collections.abc import Callable
from functools import wraps
from inspect import signature

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

# TODO(stlite-parity): Delete this module and its call in entry.py once
# @stlite/browser bundles the Streamlit version pinned in pyproject.toml (currently
# 1.62.0), cached Pandas UTC datetime data works, and the browser demo opens every
# page twice without this bridge.

PERSIST_STATE_WIDGETS = (
    "multiselect",
    "number_input",
    "pills",
    "segmented_control",
    "selectbox",
    "slider",
    "text_input",
    "toggle",
)
COMPATIBILITY_MARKER = "_portico_streamlit_compatibility_installed"


def _supports_keyword(streamlit_module: object, name: str, keyword: str) -> bool:
    """Return whether a Streamlit element accepts one argument."""
    renderer = getattr(streamlit_module, name, None)
    if not callable(renderer):
        return False
    try:
        return keyword in signature(renderer).parameters
    except TypeError:
        return False
    except ValueError:
        return False


def _without_keyword(renderer: Callable[..., object], keyword: str) -> Callable[..., object]:
    """Wrap an element so the older runtime ignores one new argument."""

    @wraps(renderer)
    def render(*args: object, **kwargs: object) -> object:
        kwargs.pop(keyword, None)
        return renderer(*args, **kwargs)

    return render


def _patch_keyword(target: object, name: str, keyword: str) -> None:
    """Make one Streamlit element accept an argument from a newer runtime."""
    renderer = getattr(target, name, None)
    if callable(renderer):
        _set_attribute(target, name, _without_keyword(renderer, keyword))


def _set_attribute(target: object, name: str, value: object) -> None:
    """Set one attribute on the browser runtime."""
    setattr(target, name, value)


def _placeholder_skeleton(container: object, **_: object) -> object:
    """Keep the loading placeholder empty before Streamlit added skeletons."""
    return container


def _no_cache_data(
    function: Callable[..., object] | None = None,
    **_: object,
) -> Callable[..., object] | Callable[[Callable[..., object]], Callable[..., object]]:
    """Return browser functions without Streamlit's serialized data cache."""
    if function is not None:
        return function
    return lambda decorated: decorated


def _clear_no_cache_data() -> None:
    """Match Streamlit's cache-clearing API when no browser cache exists."""


_set_attribute(_no_cache_data, "clear", _clear_no_cache_data)


def install_streamlit_compatibility(
    streamlit_module: object = st,
    delta_generator: type[object] = DeltaGenerator,
) -> None:
    """Install only the Streamlit 1.57 fallbacks required by Portico."""
    if not getattr(streamlit_module, COMPATIBILITY_MARKER, False):
        supports_column_wrap = _supports_keyword(streamlit_module, "columns", "wrap")
        for name in PERSIST_STATE_WIDGETS:
            if not _supports_keyword(streamlit_module, name, "persist_state"):
                _patch_keyword(streamlit_module, name, "persist_state")
        if not supports_column_wrap:
            _patch_keyword(streamlit_module, "columns", "wrap")
            _set_attribute(streamlit_module, "cache_data", _no_cache_data)
        # st.container is a bound export, so patch it as well as its class method.
        # The browser bridge always ignores container wrapping until its TODO is met.
        _patch_keyword(streamlit_module, "container", "wrap")
        _patch_keyword(delta_generator, "container", "wrap")
        _set_attribute(streamlit_module, COMPATIBILITY_MARKER, True)

    method_name = "skeleton"
    if not hasattr(delta_generator, method_name):
        _set_attribute(delta_generator, method_name, _placeholder_skeleton)
