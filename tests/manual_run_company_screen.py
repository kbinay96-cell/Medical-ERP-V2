"""
Manual/visual test runner for the Company Master screen.
Run standalone (outside the full app) to sanity-check the UI:

    python tests/manual_run_company_screen.py
"""

import sys
from PySide6.QtWidgets import QApplication
from screens.company_master_screen import CompanyMasterScreen

app = QApplication(sys.argv)
screen = CompanyMasterScreen(logged_in_user="admin")
screen.show()
app.exec()
