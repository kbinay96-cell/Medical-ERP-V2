"""
=========================================================
Medical ERP V2
Lock Screen Dialog
---------------------------------------------------------
Modal dialog shown after auto-lock idle timeout. Does NOT
end the session on success - only re-verifies the CURRENT
logged-in user's password to resume. Reuses the same
failed-attempt/account-lock rules as normal login so
brute-force protection is consistent everywhere.
UI event handling only.
=========================================================
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QSequentialAnimationGroup, QRectF, QEvent
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QWidget, QGraphicsOpacityEffect,
    QApplication, QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
)

from models.user_model import (
    get_user_by_username, register_failed_attempt,
    reset_failed_attempts, auto_unlock_if_due
)
from config.settings import (
    STATUS_LOCKED, STATUS_DISABLED, STATUS_SUSPENDED,
    STATUS_EXPIRED, STATUS_DELETED,
)
from engines.audit_logger import write_failed_login
from engines.password_manager import verify_password
from engines import session_manager


class LockScreenDialog(QDialog):

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self._username = username
        self.force_logout = False  # set True if the account gets locked/disabled while unlocking

        self.setWindowTitle("Session Locked")
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(440, 380)

        screen_geo = QApplication.primaryScreen().geometry()
        self.move(screen_geo.x() + (screen_geo.width() - self.width()) // 2,
                  screen_geo.y() + (screen_geo.height() - self.height()) // 2)

        outerLayout = QVBoxLayout(self)
        outerLayout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("lockCard")
        self.card.setStyleSheet("""
            QFrame#lockCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1f2937, stop:1 #111827
                );
                border-radius: 18px;
                border: 1px solid #374151;
            }
            QLabel#lockIcon { font-size: 46px; }
            QLabel#lockTitle {
                color: #f9fafb; font-size: 21px; font-weight: 600;
            }
            QLabel#lockSubtitle { color: #9ca3af; font-size: 13px; }
            QLineEdit#lockPassword {
                background: #1f2937;
                border: 1px solid #4b5563;
                border-radius: 10px;
                padding: 11px 14px;
                color: #f9fafb;
                font-size: 14px;
            }
            QLineEdit#lockPassword:focus { border: 1px solid #6366f1; }
            QLabel#lockError { color: #f87171; font-size: 12px; }
            QPushButton#lockUnlockBtn {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #8b5cf6
                );
                color: white; border: none; border-radius: 10px;
                padding: 10px 0px; font-size: 14px; font-weight: 600;
            }
            QPushButton#lockUnlockBtn:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4f46e5, stop:1 #7c3aed
                );
            }
            QPushButton#lockUnlockBtn:pressed { background: #4338ca; }
        """)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(45)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 10)
        self.card.setGraphicsEffect(shadow)

        outerLayout.addWidget(self.card)

        cardLayout = QVBoxLayout(self.card)
        cardLayout.setContentsMargins(38, 36, 38, 32)
        cardLayout.setSpacing(10)

        self.lblIcon = QLabel("🔒")
        self.lblIcon.setObjectName("lockIcon")
        self.lblIcon.setAlignment(Qt.AlignCenter)
        cardLayout.addWidget(self.lblIcon)

        self.lblTitle = QLabel("Session Locked")
        self.lblTitle.setObjectName("lockTitle")
        self.lblTitle.setAlignment(Qt.AlignCenter)
        cardLayout.addWidget(self.lblTitle)

        self.lblSubtitle = QLabel(f"Enter password for '{username}' to resume")
        self.lblSubtitle.setObjectName("lockSubtitle")
        self.lblSubtitle.setAlignment(Qt.AlignCenter)
        self.lblSubtitle.setWordWrap(True)
        cardLayout.addWidget(self.lblSubtitle)

        cardLayout.addSpacing(16)

        self.txtPassword = QLineEdit(self.card)
        self.txtPassword.setObjectName("lockPassword")
        self.txtPassword.setEchoMode(QLineEdit.Password)
        self.txtPassword.setPlaceholderText("Password")
        self.txtPassword.returnPressed.connect(self._handle_unlock)
        cardLayout.addWidget(self.txtPassword)

        self.lblError = QLabel("")
        self.lblError.setObjectName("lockError")
        self.lblError.setAlignment(Qt.AlignCenter)
        cardLayout.addWidget(self.lblError)

        cardLayout.addSpacing(8)

        self.btnUnlock = QPushButton("Unlock")
        self.btnUnlock.setObjectName("lockUnlockBtn")
        self.btnUnlock.setCursor(Qt.PointingHandCursor)
        self.btnUnlock.setMinimumHeight(44)
        self.btnUnlock.clicked.connect(self._handle_unlock)
        cardLayout.addWidget(self.btnUnlock)

        self.txtPassword.setFocus()

        self._start_icon_pulse()
        self._fade_in()

    # ------------------------------------------------------------------
    # Visual effects
    # ------------------------------------------------------------------

    def _fade_in(self):
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._fade_anim = anim

    def _start_icon_pulse(self):
        effect = QGraphicsDropShadowEffect(self.lblIcon)
        effect.setBlurRadius(0)
        effect.setColor(QColor(99, 102, 241, 200))
        effect.setOffset(0, 0)
        self.lblIcon.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"blurRadius", self)
        anim.setDuration(1400)
        anim.setStartValue(0)
        anim.setKeyValueAt(0.5, 30)
        anim.setEndValue(0)
        anim.setLoopCount(-1)
        anim.start()
        self._pulse_anim = anim

    def _shake(self):
        base = self.pos()
        anim = QSequentialAnimationGroup(self)
        for dx in (12, -10, 8, -6, 4, 0):
            step = QPropertyAnimation(self, b"pos", self)
            step.setDuration(45)
            step.setEndValue(QPoint(base.x() + dx, base.y()))
            anim.addAnimation(step)
        anim.start(QSequentialAnimationGroup.DeleteWhenStopped)
        self._shake_anim = anim

    # ------------------------------------------------------------------
    # Behaviour (unchanged logic - brute-force protection kept as-is)
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def _reject_with_logout(self, message: str):
        write_failed_login(self._username, message)
        self.force_logout = True
        self.reject()

    def _handle_unlock(self):
        password = self.txtPassword.text()
        user = get_user_by_username(self._username)

        if user is None:
            self._show_error("Incorrect password.")
            return

        user = auto_unlock_if_due(user)

        if user["status"] == STATUS_LOCKED:
            self._reject_with_logout("Account is locked.")
            return
        if user["status"] == STATUS_DISABLED:
            self._reject_with_logout("Account is disabled.")
            return
        if user["status"] == STATUS_SUSPENDED:
            self._reject_with_logout("Account is suspended.")
            return
        if user["status"] in (STATUS_EXPIRED, STATUS_DELETED):
            self._reject_with_logout("Account is expired or deleted.")
            return

        if verify_password(password, user["passwordhash"], user["passwordsalt"]):
            reset_failed_attempts(self._username)
            session_manager.reset_activity_tracking()
            self.accept()
            return

        register_failed_attempt(self._username)
        write_failed_login(self._username, "Incorrect password (unlock attempt).")

        refreshed_user = get_user_by_username(self._username)
        if refreshed_user and refreshed_user["status"] == STATUS_LOCKED:
            self.force_logout = True
            self.reject()
            return

        self._show_error("Incorrect password.")

    def _show_error(self, message: str):
        self.lblError.setText(message)
        self.txtPassword.clear()
        self.txtPassword.setFocus()
        self._shake()


def _erp_bounding_geometry():
    """
    Union of frameGeometry() across every currently-visible
    top-level ERP window (Dashboard, plus any still-standalone
    windows like Customer/Settings). Excludes dialogs (e.g. the
    lock dialog itself) so the overlay only ever covers actual
    ERP screens - never the whole desktop/taskbar/other apps.
    """
    rect = None
    for w in QApplication.topLevelWidgets():
        if isinstance(w, QDialog) or isinstance(w, LockOverlay):
            continue
        if not w.isVisible():
            continue
        r = w.frameGeometry()
        rect = r if rect is None else rect.united(r)
    return rect


class LockOverlay(QWidget):
    """
    Semi-transparent frosted-glass overlay shown behind
    LockScreenDialog. Sized to cover only the ERP's own
    visible top-level window(s) (see _erp_bounding_geometry) -
    never the full desktop, taskbar, or other applications.
    Captures the ERP content underneath, blurs it, and paints
    a soft dark tint on top for a "dimmed, unreadable but not
    solid black" look.
    """

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._bg_pixmap = None
        self._dialog_ref = None
        self._filter_installed = False

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _blurred(self, pixmap: QPixmap, radius: int = 22) -> QPixmap:
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(pixmap)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(radius)
        item.setGraphicsEffect(blur)
        scene.addItem(item)

        result = QPixmap(pixmap.size())
        result.fill(Qt.transparent)
        painter = QPainter(result)
        scene.render(painter, QRectF(result.rect()), QRectF(pixmap.rect()))
        painter.end()
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._bg_pixmap is not None:
            painter.drawPixmap(0, 0, self._bg_pixmap)
        painter.fillRect(self.rect(), QColor(15, 17, 23, 120))

    def fade_in(self):
        rect = _erp_bounding_geometry()
        if rect is not None:
            self.setGeometry(rect)
            screen = QApplication.primaryScreen()
            raw = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
            self._bg_pixmap = self._blurred(raw)

        self.show()
        self.raise_()
        self.activateWindow()
        self._anim.start()

    def attach_dialog(self, dialog):
        self._dialog_ref = dialog

    def start_keeping_on_top(self):
        if not self._filter_installed:
            QApplication.instance().installEventFilter(self)
            self._filter_installed = True

    def stop_keeping_on_top(self):
        if self._filter_installed:
            QApplication.instance().removeEventFilter(self)
            self._filter_installed = False

    def eventFilter(self, watched, event):
        if event.type() == QEvent.WindowActivate:
            if watched is not self and watched is not self._dialog_ref:
                # Some ERP window of ours (e.g. Dashboard) was just
                # brought forward - e.g. via taskbar click. Pull the
                # overlay + lock dialog back on top of it, without
                # touching unrelated external applications.
                self.raise_()
                if self._dialog_ref is not None:
                    self._dialog_ref.raise_()
                    self._dialog_ref.activateWindow()
        return False