"""
tests/manual_run_manufacturer_screen.py

Manual, standalone launcher for ManufacturerListScreen -- opens just this
one screen in its own window, without needing the full app/login flow.
Run this, click around (Add/Edit/Delete/Restore), close the window when done.
"""

import sys
from PySide6.QtWidgets import QApplication

from screens.manufacturer_list_screen import ManufacturerListScreen

app = QApplication(sys.argv)
window = ManufacturerListScreen()
window.setWindowTitle("Manufacturer Master - Manual Test")
window.resize(900, 600)
window.show()
sys.exit(app.exec())