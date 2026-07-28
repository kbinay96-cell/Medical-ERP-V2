"""
=========================================================
Medical ERP V2
Language Manager
---------------------------------------------------------
Purpose:
    Central place for the app's current language and the
    list of supported languages. This is UI/presentation
    infrastructure (not business logic).

Current state:
    Only English is fully translated. Hindi and Nepali are
    registered here so the Language dialog and future
    translation work (Qt .ts/.qm files loaded via
    QTranslator) have a real, working switch to plug into -
    selecting them now simply keeps the UI in English and
    tells the user translation is coming, rather than
    silently failing or being a dead button.
=========================================================
"""

from dataclasses import dataclass

SUPPORTED_LANGUAGES = [
    ("en", "English"),
    ("hi", "हिन्दी (Hindi)"),
    ("ne", "नेपाली (Nepali)"),
]

_current_language_code = "en"


@dataclass
class LanguageChangeResult:
    applied: bool
    message: str


def get_available_languages() -> list[tuple[str, str]]:
    return SUPPORTED_LANGUAGES


def get_current_language_code() -> str:
    return _current_language_code


def set_current_language(code: str) -> LanguageChangeResult:
    """
    Switches the active language. Only English actually has
    translated text right now; other languages are accepted
    (so the architecture and dialog are real and future-ready)
    but report that the UI stays in English until translation
    files are added.
    """
    global _current_language_code

    valid_codes = [c for c, _ in SUPPORTED_LANGUAGES]
    if code not in valid_codes:
        return LanguageChangeResult(applied=False, message=f"Unknown language code: {code}")

    _current_language_code = code

    if code == "en":
        return LanguageChangeResult(applied=True, message="Language set to English.")

    language_name = dict(SUPPORTED_LANGUAGES)[code]
    return LanguageChangeResult(
        applied=True,
        message=f"{language_name} is registered, but translation is not available yet. "
                 f"The interface will remain in English until this is completed.",
    )
