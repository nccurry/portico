"""Tests for shared page helpers."""

from types import SimpleNamespace

from pytest import MonkeyPatch

from src.page_helpers import extract_merchant_name, render_demo_banner, render_time_frame_control


def test_demo_banner_identifies_synthetic_data(monkeypatch: MonkeyPatch) -> None:
    messages: list[str] = []
    settings = SimpleNamespace(is_demo=True)
    monkeypatch.setattr("src.page_helpers.get_settings", lambda: settings)
    monkeypatch.setattr("src.page_helpers.st.info", lambda message, **kwargs: messages.append(message))

    render_demo_banner()

    assert messages == [
        "Demo data is active. The dashboard uses committed synthetic records and does not contact a remote spreadsheet."
    ]


def test_time_frame_control_uses_the_shared_presentation(monkeypatch: MonkeyPatch) -> None:
    call: dict[str, object] = {}

    def segmented_control(label: str, **kwargs: object) -> str:
        call["label"] = label
        call.update(kwargs)
        return "1Y"

    monkeypatch.setattr("src.page_helpers.st.segmented_control", segmented_control)

    selected = render_time_frame_control(["3M", "1Y", "All"], default="1Y", key="page_lookback")

    assert selected == "1Y"
    assert call == {
        "label": "Time frame",
        "options": ["3M", "1Y", "All"],
        "default": "1Y",
        "required": True,
        "key": "page_lookback",
        "help": "Controls the time period shown on this page.",
        "persist_state": "page",
        "width": "content",
    }


class TestExtractMerchantName:
    def test_single_word_with_multi_word_method(self) -> None:
        """A single-word description with first_three should return that word."""
        assert extract_merchant_name("NETFLIX", "first_three") == "NETFLIX"

    def test_unknown_method_falls_back_to_first_word(self) -> None:
        """An unrecognized method returns the first word."""
        assert extract_merchant_name("FOO BAR BAZ", "bad_method") == "FOO"

    def test_nan_input_returns_unknown(self) -> None:
        """NaN description returns 'Unknown'."""
        assert extract_merchant_name(float("nan")) == "Unknown"
        assert extract_merchant_name(None) == "Unknown"

    def test_empty_string_returns_unknown(self) -> None:
        """Empty string returns 'Unknown' (split produces empty list)."""
        assert extract_merchant_name("") == "Unknown"
        assert extract_merchant_name("   ") == "Unknown"

    def test_first_two_method(self) -> None:
        """first_two returns the first two words."""
        assert extract_merchant_name("WHOLE FOODS MARKET", "first_two") == "WHOLE FOODS"

    def test_first_three_method(self) -> None:
        """first_three returns the first three words."""
        assert extract_merchant_name("THE HOME DEPOT STORE", "first_three") == "THE HOME DEPOT"

    def test_first_word_default(self) -> None:
        """Default method returns first word."""
        assert extract_merchant_name("AMAZON MARKETPLACE") == "AMAZON"

    def test_unicode_characters(self) -> None:
        """Unicode characters in description don't crash."""
        assert extract_merchant_name("CAFÉ MOCHA HOUSE") == "CAFÉ"

    def test_special_characters(self) -> None:
        """Special characters are preserved."""
        assert extract_merchant_name("7-ELEVEN #12345") == "7-ELEVEN"
