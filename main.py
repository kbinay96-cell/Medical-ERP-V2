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
    load_application_fonts()
    apply_theme("Black")

    from engines.audit_cleanup_engine import cleanup_old_audit_data
    cleanup_old_audit_data()

    while True:
        login_screen = LoginScreen()
        login_screen.show()
        app.exec()

        if not (login_screen.login_result and login_screen.login_result.success):
            logger.info("Application closed without a successful login.")
            return

        dashboard_screen = DashboardScreen(login_screen.login_result)
        dashboard_screen.show()
        app.exec()

        # Dashboard closed (logout, timeout-logout, or window closed) -
        # loop back to a fresh login screen instead of terminating.
        logger.info("Returned to login screen after dashboard session ended.")


if __name__ == "__main__":
    main()
