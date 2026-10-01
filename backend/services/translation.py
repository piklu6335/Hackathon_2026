"""Local article translation using the Argos Translate Python library."""

from threading import Lock

import argostranslate.package
import argostranslate.translate
import langid


_package_lock = Lock()
_available_packages = None


class LanguagePairUnavailable(Exception):
    """Raised when Argos has no installed or downloadable route for a pair."""


def _install_pair(from_code: str, to_code: str, installed_pairs: set[tuple[str, str]]) -> bool:
    global _available_packages

    if (from_code, to_code) in installed_pairs:
        return True

    if _available_packages is None:
        _available_packages = argostranslate.package.get_available_packages()

    package = next(
        (
            item
            for item in _available_packages
            if item.type == "translate"
            and item.from_code == from_code
            and item.to_code == to_code
        ),
        None,
    )
    if package is None:
        return False

    package.install()
    installed_pairs.add((from_code, to_code))
    return True


def translate_article(text: str, target_language: str) -> tuple[str, str]:
    """Detect the input language, install a model route if needed, and translate."""
    source_language, _confidence = langid.classify(text)
    target_language = "zh" if target_language == "zh-CN" else target_language

    if source_language == target_language:
        return text, source_language

    with _package_lock:
        installed_pairs = {
            (item.from_code, item.to_code)
            for item in argostranslate.package.get_installed_packages()
            if item.type == "translate"
        }

        direct_available = _install_pair(source_language, target_language, installed_pairs)
        pivot_available = False
        if not direct_available and source_language != "en" and target_language != "en":
            # Install both legs of the route and actually translate through English.
            source_to_english = _install_pair(source_language, "en", installed_pairs)
            english_to_target = _install_pair("en", target_language, installed_pairs)
            pivot_available = source_to_english and english_to_target

        if not direct_available and not pivot_available:
            raise LanguagePairUnavailable(
                f"No Argos model route is available from {source_language} to {target_language}."
            )

        if direct_available:
            translated_text = argostranslate.translate.translate(
                text, source_language, target_language
            )
        else:
            english_text = argostranslate.translate.translate(
                text, source_language, "en"
            )
            translated_text = argostranslate.translate.translate(
                english_text, "en", target_language
            )

    return translated_text, source_language
