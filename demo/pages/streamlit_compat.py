"""Temporary Streamlit 1.57 support for the GitHub Pages demo."""

from collections.abc import Callable
from functools import wraps
from inspect import signature

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

# TODO(stlite-1.62): Delete this file and its call in entry.py after
# @stlite/browser bundles Streamlit 1.62 and the browser smoke test opens every Portico page.

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
        setattr(target, name, _without_keyword(renderer, keyword))


def _placeholder_skeleton(container: object, **_: object) -> object:
    """Keep the loading placeholder empty before Streamlit added skeletons."""
    return container


def install_streamlit_compatibility(
    streamlit_module: object = st,
    delta_generator: type[object] = DeltaGenerator,
) -> None:
    """Install only the Streamlit 1.57 fallbacks required by Portico."""
    if not getattr(streamlit_module, COMPATIBILITY_MARKER, False):
        for name in PERSIST_STATE_WIDGETS:
            if not _supports_keyword(streamlit_module, name, "persist_state"):
                _patch_keyword(streamlit_module, name, "persist_state")
        if not _supports_keyword(streamlit_module, "columns", "wrap"):
            _patch_keyword(streamlit_module, "columns", "wrap")
        setattr(streamlit_module, COMPATIBILITY_MARKER, True)

    method_name = "skeleton"
    if not hasattr(delta_generator, method_name):
        setattr(delta_generator, method_name, _placeholder_skeleton)
