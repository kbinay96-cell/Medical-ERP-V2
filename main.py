"""
=========================================================
Medical ERP V2
Application Entry Point
---------------------------------------------------------
Responsibilities:
    - Start QApplication
    - Load Login Screen
    - On successful login, open Dashboard (Part-4, next module)

No SQL here. No business logic here.
=========================================================
"""

import sys

from PySide6.QtWidgets import QApplication

from screens.login_screen import LoginScreen
from screens.dashboard_screen import DashboardScreen
from engines.theme_engine import apply_theme
from utils.font_utils import load_application_fonts
from utils.app_logger import get_logger

logger = get_logger()


def main():
    app = QApplication(sys.argv)

    # Register bundled fonts before the theme QSS is applied — font-
    # family resolution happens at stylesheet-apply time, so this must
    # come first. No re-loading needed on theme toggle; QFontDatabase
    # registrations persist for the app's lifetime.
    load_application_fonts()

    apply_theme("Black")

    login_screen = LoginScreen()
    login_screen.show()
    app.exec()

    if not (login_screen.login_result and login_screen.login_result.success):
        logger.info("Application closed without a successful login.")
        return

    logger.info(f"Proceeding to Dashboard for user '{login_screen.login_result.username}'.")

    dashboard_screen = DashboardScreen(login_screen.login_result)
    dashboard_screen.show()
    app.exec()


if __name__ == "__main__":
    main()
