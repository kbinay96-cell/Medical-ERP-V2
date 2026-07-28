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

# Each tuple: (module_path, class_name, attribute_name)
_SESSION_CANDIDATES = [
    ("engines.session_manager", "SessionManager", "get_current_user_id"),
    ("engines.session_manager", "SessionManager", "current_user_id"),
    ("engines.session_manager", "SessionManager", "get_current_user"),
    ("engines.session_engine", "SessionEngine", "get_current_user_id"),
    ("engines.session_engine", "SessionEngine", "current_user_id"),
    ("engines.session_engine", "SessionEngine", "get_current_user"),
]

_MESSAGE_CLASS_CANDIDATES = ("Message", "MessageBox", "MessageUtils", "Messages")


def get_current_user_id() -> int:
    """
    Returns the currently logged-in user's id, for stamping created_by /
    updated_by on Supplier writes. Tries the project's Session Engine under
    several common shapes; falls back to a fixed id (with a loud warning)
    if none resolve, so development is never blocked on it.
    """
    for module_name, class_name, attr_name in _SESSION_CANDIDATES:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            instance = cls()
            attr = getattr(instance, attr_name)
            value = attr() if callable(attr) else attr
            if isinstance(value, int):
                return value
            if hasattr(value, "user_id"):
                return int(value.user_id)
            if hasattr(value, "id"):
                return int(value.id)
        except Exception:  # noqa: BLE001 - deliberately broad; this is a best-effort probe
            continue

    logger.warning(
        "Session Engine not resolvable via any known interface; falling back "
        "to fixed user_id=%s. Update utils.integration_adapters.get_current_user_id() "
        "once the real Session Engine API is confirmed.",
        DEFAULT_FALLBACK_USER_ID,
    )
    return DEFAULT_FALLBACK_USER_ID


def _resolve_message_class():
    try:
        module = importlib.import_module("utils.message")
    except ImportError:
        return None
    for class_name in _MESSAGE_CLASS_CANDIDATES:
        cls = getattr(module, class_name, None)
        if cls is not None:
            return cls
    return None


def _dispatch(kind: str, parent, title: str, message: str) -> None:
    cls = _resolve_message_class()
    if cls is not None:
        method = getattr(cls, kind, None) or getattr(cls, f"show_{kind}", None)
        if method is not None:
            try:
                method(parent, title, message)
                return
            except Exception:  # noqa: BLE001
                pass  # fall through to the raw QMessageBox fallback below

    from PySide6.QtWidgets import QMessageBox

    logger.warning(
        "utils.message.%s() not resolvable; using a raw QMessageBox fallback. "
        "Update utils.integration_adapters once the real Message utility API is confirmed.",
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
    cls = _resolve_message_class()
    if cls is not None:
        for method_name in ("confirm", "question", "ask"):
            method = getattr(cls, method_name, None)
            if method is not None:
                try:
                    return bool(method(parent, title, message))
                except Exception:  # noqa: BLE001
                    break  # fall through to the raw QMessageBox fallback below

    from PySide6.QtWidgets import QMessageBox

    logger.warning(
        "utils.message confirm()/question() not resolvable; using a raw QMessageBox "
        "fallback. Update utils.integration_adapters once the real Message utility "
        "API is confirmed."
    )
    result = QMessageBox.question(
        parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    return result == QMessageBox.Yes
