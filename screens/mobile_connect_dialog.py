"""
=========================================================
Medical ERP V2
Mobile Connect Dialog
---------------------------------------------------------
Purpose:
    Shows a QR code the user scans with their phone's normal
    camera app to open the barcode-scanner page (see
    utils/mobile_scanner_server.py) in the phone's own browser
    -- no app install needed. Starts the local server when
    opened, stops it when closed.
=========================================================
"""

import io

import qrcode
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from utils.app_logger import get_logger
from utils.mobile_scanner_server import MobileScannerServer, get_local_ip

logger = get_logger()


class MobileConnectDialog(QDialog):
    barcode_scanned = Signal(str)

    def __init__(self, parent, item_lookup_fn=None):
        super().__init__(parent)
        self.setWindowTitle("Connect Mobile Scanner")
        self._server: MobileScannerServer | None = None
        self._build_ui()
        self._start_server(item_lookup_fn)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.qr_label = QLabel("Starting...")
        self.qr_label.setFixedSize(280, 280)
        self.qr_label.setScaledContents(True)
        layout.addWidget(self.qr_label)

        self.instructions_label = QLabel(
            "1. Make sure your phone is on the SAME WiFi as this PC.\n"
            "2. Open your phone's normal Camera app and scan this QR code.\n"
            "3. Tap the link that appears, allow camera access, then scan a barcode."
        )
        self.instructions_label.setWordWrap(True)
        layout.addWidget(self.instructions_label)

        self.status_label = QLabel("Waiting for a scan from the phone...")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

    def _start_server(self, item_lookup_fn) -> None:
        lookup = item_lookup_fn or (lambda barcode: None)
        self._server = MobileScannerServer(item_lookup_fn=lookup, parent=self)
        self._server.barcode_received.connect(self._on_barcode_received)
        self._server.phone_connected.connect(self._on_phone_connected)
        try:
            self._server.start()
        except OSError:
            self.qr_label.setText("Could not start the mobile scanner server.")
            return

        url = f"https://{get_local_ip()}:{self._server.port}/"
        self._render_qr(url)
        self.instructions_label.setText(
            f"1. Make sure your phone is on the SAME WiFi as this PC.\n"
            f"2. Open your phone's normal Camera app and scan this QR code\n"
            f"   (or open this link manually: {url}).\n"
            f"3. The browser will show a 'connection not private' warning --\n"
            f"   this is expected (the certificate is self-signed). Tap\n"
            f"   'Advanced' then 'Proceed' to continue.\n"
            f"4. Allow camera access, then scan a barcode."
        )

    def _render_qr(self, url: str) -> None:
        img = qrcode.make(url)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        self.qr_label.setPixmap(pixmap)

    def _on_barcode_received(self, barcode: str) -> None:
        self.status_label.setText(f"Last scanned: {barcode}")
        self.barcode_scanned.emit(barcode)

    def _on_phone_connected(self) -> None:
        from PySide6.QtCore import QTimer

        self.status_label.setText("Phone connected! Closing...")
        QTimer.singleShot(800, self.close)

    def closeEvent(self, event) -> None:
        if self._server is not None:
            self._server.stop()
        super().closeEvent(event)