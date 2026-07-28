"""
=========================================================
Medical ERP V2
Message Engine
---------------------------------------------------------
Single place for all application messages (Information,
Warning, Error, Confirmation, Success) - unified style.
=========================================================
"""

from PySide6.QtWidgets import QMessageBox

APP_TITLE = "Medical ERP"


def show_info(message: str, title: str = APP_TITLE) -> None:
    QMessageBox.information(None, title, message)


def show_success(message: str, title: str = APP_TITLE) -> None:
    QMessageBox.information(None, title, message)


def show_warning(message: str, title: str = APP_TITLE) -> None:
    QMessageBox.warning(None, title, message)


def show_error(message: str, title: str = APP_TITLE) -> None:
    QMessageBox.critical(None, title, message)


def confirm(message: str, title: str = APP_TITLE) -> bool:
    reply = QMessageBox.question(
        None, title, message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
