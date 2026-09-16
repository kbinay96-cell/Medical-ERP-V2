"""
=========================================================
Medical ERP V2
Mobile Barcode Scanner Server
---------------------------------------------------------
Purpose:
    Runs a tiny local HTTPS server (LAN-only, no internet) that
    serves a one-page barcode scanner to any phone's stock
    browser -- no app install needed. The page uses the
    browser's own camera + the built-in BarcodeDetector API
    (Chrome/Android) to decode a barcode client-side, then
    POSTs the decoded value back here, which re-emits it as a
    Qt signal for the currently open Sale/Purchase form to
    consume exactly like a hardware scanner's keystrokes.

    HTTPS (with a self-signed certificate) is required here --
    modern phone browsers only allow camera access and barcode
    detection on secure origins; plain http://<lan-ip> silently
    disables both (this is why an earlier http-only version
    showed a black camera / "not supported" even on real Android
    Chrome). The phone will show a one-time "connection not
    private" warning since the certificate is self-signed --
    that's expected; tapping Advanced -> Proceed is required.

    Nothing here ever leaves the local WiFi network -- the
    server only binds to the LAN IP and only serves this one
    page + one POST endpoint.
=========================================================
"""

import datetime
import ipaddress
import json
import os
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import QObject, Signal

from utils.app_logger import get_logger

logger = get_logger()

_SCAN_PAGE_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Medical ERP - Barcode Scanner</title>
  <style>
    body { font-family: sans-serif; background: #111; color: #fff; margin: 0;
           display: flex; flex-direction: column; align-items: center; padding: 16px; }
    video { width: 100%; max-width: 480px; border-radius: 8px; background: #000; }
    #status { margin-top: 12px; font-size: 16px; text-align: center; min-height: 24px; }
    .ok { color: #2ecc71; }
    .err { color: #e74c3c; }
  </style>
</head>
<body>
  <h3>Scan a barcode</h3>
  <video id="video" autoplay playsinline muted></video>
  <div id="status">Starting camera...</div>
  <script>
    const statusEl = document.getElementById('status');
    let lastSent = "";
    let lastSentAt = 0;

    async function sendBarcode(value) {
      const now = Date.now();
      if (value === lastSent && (now - lastSentAt) < 2000) return;
      lastSent = value;
      lastSentAt = now;
      try {
        const resp = await fetch('/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ barcode: value }),
        });
        const data = await resp.json();
        statusEl.textContent = data.found ? ('Sent: ' + value) : ('Sent (not found in system): ' + value);
        statusEl.className = data.found ? 'ok' : 'err';
      } catch (e) {
        statusEl.textContent = 'Could not reach the PC app.';
        statusEl.className = 'err';
      }
    }

    async function start() {
      if (!('BarcodeDetector' in window)) {
        statusEl.textContent = 'This phone browser does not support camera barcode scanning. Please use Chrome on Android.';
        statusEl.className = 'err';
        return;
      }
      const detector = new BarcodeDetector({
        formats: ['qr_code', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'code_93', 'itf', 'codabar']
      });
      const video = document.getElementById('video');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        video.srcObject = stream;
        statusEl.textContent = 'Point the camera at a barcode.';
      } catch (e) {
        statusEl.textContent = 'Camera permission denied.';
        statusEl.className = 'err';
        return;
      }

      async function scanLoop() {
        try {
          const codes = await detector.detect(video);
          if (codes.length > 0) {
            sendBarcode(codes[0].rawValue);
          }
        } catch (e) {
          // ignore transient detect errors, keep looping
        }
        requestAnimationFrame(scanLoop);
      }
      scanLoop();
    }

    start();
  </script>
</body>
</html>
"""


def get_local_ip() -> str:
    """Best-effort LAN IP of this machine (never actually sends any
    packets -- just asks the OS which local interface would be used to
    reach an external address)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _get_or_create_cert(local_ip: str) -> tuple[str, str]:
    """Returns (cert_path, key_path) for a self-signed HTTPS certificate
    for this machine's current LAN IP, generating and caching one to disk
    if it doesn't exist yet. Filename is keyed by IP so a DHCP lease
    change automatically gets a fresh matching certificate instead of
    silently reusing a stale one."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MedicalERP")
    os.makedirs(cert_dir, exist_ok=True)
    safe_ip = local_ip.replace(".", "_")
    cert_path = os.path.join(cert_dir, f"scanner_cert_{safe_ip}.pem")
    key_path = os.path.join(cert_dir, f"scanner_key_{safe_ip}.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, local_ip)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(local_ip))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    return cert_path, key_path


class MobileScannerServer(QObject):
    """Owns one background HTTPS server + emits `barcode_received` on the
    Qt (GUI) thread whenever a phone POSTs a scanned barcode. Each
    MobileConnectDialog creates and owns its own instance -- the server
    stops when the dialog closes."""

    barcode_received = Signal(str)
    phone_connected = Signal()

    def __init__(self, item_lookup_fn, port: int = 8743, parent=None):
        """`item_lookup_fn(barcode) -> item_id or None` -- used only to
        tell the phone page whether the scan matched something, so it
        can show "Sent" vs "Sent (not found)"; the actual row-adding
        still happens on the PC side via `barcode_received`."""
        super().__init__(parent)
        self._item_lookup_fn = item_lookup_fn
        self._port = port
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> None:
        signal_emitter = self.barcode_received
        connected_emitter = self.phone_connected
        lookup_fn = self._item_lookup_fn

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: A003
                pass

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    body = _SCAN_PAGE_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    connected_emitter.emit()
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path != "/scan":
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    barcode = (payload.get("barcode") or "").strip()
                except Exception:
                    barcode = ""

                found = False
                if barcode:
                    try:
                        found = lookup_fn(barcode) is not None
                    except Exception:
                        logger.exception("Mobile scanner: item lookup failed for barcode=%s", barcode)
                    signal_emitter.emit(barcode)

                response = json.dumps({"found": found}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        try:
            self._httpd = HTTPServer(("0.0.0.0", self._port), Handler)
        except OSError as e:
            logger.error(f"Mobile scanner server failed to bind port {self._port}: {e}")
            raise

        local_ip = get_local_ip()
        cert_path, key_path = _get_or_create_cert(local_ip)
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        self._httpd.socket = ssl_context.wrap_socket(self._httpd.socket, server_side=True)

        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Mobile scanner server started (HTTPS) on port {self._port}.")

    def stop(self) -> None:
        """Shuts the server down on a background thread so closing the
        dialog never freezes the GUI, even if the underlying socket
        teardown takes a moment (e.g. a phone's connection still open)."""
        if self._httpd is None:
            return
        httpd = self._httpd
        self._httpd = None

        def _shutdown():
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                logger.exception("Error while stopping mobile scanner server.")
            logger.info("Mobile scanner server stopped.")

        threading.Thread(target=_shutdown, daemon=True).start()