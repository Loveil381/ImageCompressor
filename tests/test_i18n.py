"""Tests for src.i18n.strings."""

from __future__ import annotations

import pytest

from src.i18n import strings
from src.i18n.strings import T, get_language, set_language, supported_languages


@pytest.fixture(autouse=True)
def _restore_language() -> None:
    original = get_language()
    try:
        yield
    finally:
        set_language(original)


class TestTranslations:
    def test_all_registered_keys_return_non_empty_strings(self) -> None:
        for lang in supported_languages():
            set_language(lang)
            for key in strings._STRINGS:
                assert T(key) != ""

    def test_unknown_key_returns_key_itself(self) -> None:
        assert T("missing_key") == "missing_key"

    def test_format_parameters_are_applied(self) -> None:
        set_language("en")
        assert T("log_target", sz="500KB") == "Target size: 500KB"


class TestLanguageState:
    def test_invalid_language_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            set_language("xx")

    def test_get_language_returns_current_language(self) -> None:
        set_language("ja")
        assert get_language() == "ja"

    def test_supported_languages_are_declared_in_order(self) -> None:
        assert supported_languages() == ["zh", "en", "ja"]
