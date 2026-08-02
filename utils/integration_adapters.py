"""
utils/integration_adapters.py

TEMPORARY integration shims used ONLY by the Supplier Screen/Controller
layer (screens/supplier_list_screen.py, screens/supplier_form_screen.py).

Why this file exists: the Screen layer needs two things from the rest of
the project that weren't confirmed in this session --
    1. The current logged-in user's id (for created_by / updated_by).
    2. The project's unified message-box style (Info/Warning/Error/
       Confirm/Success), per the project's UI standards.

Rather than guess a single hardcoded import path and risk it being wrong,
each function below tries several call shapes that would match common
project naming conventions, and only falls back to a minimal, explicitly
temporary behavior if none of them resolve -- logging a warning every time
that happens so it's impossible to miss in testing or production logs.

HOW TO RETIRE THIS FILE ONCE THE REAL MODULES ARE CONFIRMED:
    - Replace the body of get_current_user_id() with a direct call to the
      real Session Engine.
    - Replace the bodies of show_info/show_success/show_warning/show_error/
      confirm() with direct calls to the real utils.message module.
    - screens/supplier_list_screen.py and screens/supplier_form_screen.py
      never need to change -- they only ever call the functions in this
      file, never the underlying engines/utilities directly. That is the
      entire point of keeping this as a separate adapter module instead of
      inlining the guesses into the screens.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_USER_ID = 1

_MESSAGE_CLASS_CANDIDATES = ("Message", "MessageBox", "MessageUtils", "Messages")


def get_current_user_id() -> int:
    """
    Returns the currently logged-in user's id, for stamping created_by /
    updated_by on Supplier/Manufacturer writes.

    Real API (confirmed): engines.session_manager.get_current_session() ->
    dict | None -- this desktop app's single in-memory active session, set
    by engines.authentication_engine.login() at Login time.
    """
    try:
        from engines.session_manager import get_current_session
        session = get_current_session()
        if session and "userid" in session:
            return int(session["userid"])
    except Exception:  # noqa: BLE001 - must never break a Save because of this lookup
        logger.exception("get_current_user_id: engines.session_manager.get_current_session() failed.")

    logger.warning(
        "No active session found via engines.session_manager.get_current_session(); "
        "falling back to fixed user_id=%s. This is expected only when a screen is "
        "opened standalone (e.g. a manual test script) without going through Login.",
        DEFAULT_FALLBACK_USER_ID,
    )
    return DEFAULT_FALLBACK_USER_ID


def _dispatch(kind: str, parent, title: str, message: str) -> None:
    from utils import message as message_module

    method = getattr(message_module, f"show_{kind}", None)
    if method is not None:
        try:
            method(message, title)
            return
        except Exception:  # noqa: BLE001
            pass

    from PySide6.QtWidgets import QMessageBox

    logger.warning(
        "utils.message.show_%s() failed unexpectedly; using a raw QMessageBox fallback.",
        kind,
    )
    icon_map = {
        "info": QMessageBox.Information,
        "success": QMessageBox.Information,
        "warning": QMessageBox.Warning,
        "error": QMessageBox.Critical,
    }
    box = QMessageBox(parent)
    box.setIcon(icon_map.get(kind, QMessageBox.Information))
    box.setWindowTitle(title)
    box.setText(message)
    box.exec()


def show_info(parent, title: str, message: str) -> None:
    _dispatch("info", parent, title, message)


def show_success(parent, title: str, message: str) -> None:
    _dispatch("success", parent, title, message)


def show_warning(parent, title: str, message: str) -> None:
    _dispatch("warning", parent, title, message)


def show_error(parent, title: str, message: str) -> None:
    _dispatch("error", parent, title, message)


def confirm(parent, title: str, message: str) -> bool:
    """Returns True if the user confirmed Yes/OK."""
    from utils import message as message_module

    try:
        return bool(message_module.confirm(message, title))
    except Exception:  # noqa: BLE001
        pass

    from PySide6.QtWidgets import QMessageBox

    logger.warning("utils.message.confirm() failed unexpectedly; using a raw QMessageBox fallback.")
    result = QMessageBox.question(
        parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    return result == QMessageBox.Yes