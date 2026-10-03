"""
=========================================================
Medical ERP V2
Login Screen
---------------------------------------------------------
UI event handling ONLY. No SQL here, no business rules
here - everything goes through the Authentication Engine.
=========================================================
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QDate, QTime, QSize, QEvent
from PySide6.QtGui import QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import QMainWindow, QLineEdit

from ui.ui_login import Ui_MainWindow
from utils.message import show_warning, show_info
from utils.app_logger import get_logger
from utils.ui_standards import apply_action_button_style
from engines.authentication_engine import login
from engines.license_manager import validate_license
from engines.subscription_manager import validate_subscription
from engines.theme_engine import toggle_theme
from utils.icon_utils import themed_icon
from engines.date_engine import ad_to_bs, DateEngineError
from models import company_model, user_model
from models.financialyear_model import get_all_financial_years
from screens.language_dialog import LanguageDialog
from utils.company_branding import set_company_logo

logger = get_logger()

ICON_DIR = "resources/icons"

from screens.forgot_password_dialog import ForgotPasswordDialog


class LoginScreen(QMainWindow):

    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.login_result = None  # set on successful login, read by main.py
        self._lockout_countdown_timer = None
        self._lockout_end_time = None
        self._lockout_username = None

        self.initialize()

    # -----------------------------------------------------
    # SETUP
    # -----------------------------------------------------

    def initialize(self):
        # Login CTAs previously had their own hardcoded 40px standard
        # (Designer's setMinimumSize) — now folded into the app-wide
        # adjustable control-height system so they scale with the
        # ui.control_height setting like every other action button.
        apply_action_button_style(self.ui.btnLogin)
        apply_action_button_style(self.ui.btnExit)

        self.ui.txtPassword.textChanged.connect(self._update_caps_lock_hint)

        self.ui.btnLogin.clicked.connect(self.handle_login)
        self.ui.btnExit.clicked.connect(self.close)
        self.ui.btnTheme.clicked.connect(self._handle_theme_toggle)
        self.ui.btnForgotPassword.clicked.connect(self._handle_forgot_password)
        self._inject_first_time_setup_button()
        self.ui.btnChangeLanguage.clicked.connect(self._handle_change_language)
        self.ui.chkShowPassword.toggled.connect(self._toggle_password_visibility)
        self.ui.cmbCompany.currentIndexChanged.connect(self._on_company_changed)

        self._apply_icons()
        self._apply_tooltips_and_status_tips()
        self._setup_shortcuts()
        self._start_clock()
        self._load_companies()
        self._load_financial_years()
        self._show_license_and_subscription_status()
        self._setup_remember_me()

        self.ui.txtUsername.setFocus()

    def _apply_icons(self):
        icon_size = QSize(18, 18)

        self.ui.lblLoginIcon.setPixmap(themed_icon("login").pixmap(QSize(40, 40)))
        set_company_logo(self.ui.lblCompanyLogo, None, QSize(112, 112))
        self.ui.lblErpLogo.hide()

        self.ui.txtUsername.addAction(themed_icon("user"), QLineEdit.ActionPosition.LeadingPosition)
        self.ui.txtPassword.addAction(themed_icon("lock"), QLineEdit.ActionPosition.LeadingPosition)

        self.ui.btnLogin.setIcon(themed_icon("login"))
        self.ui.btnLogin.setIconSize(icon_size)
        self.ui.btnExit.setIcon(themed_icon("exit"))
        self.ui.btnExit.setIconSize(icon_size)
        self.ui.btnTheme.setIcon(themed_icon("sun"))
        self.ui.btnTheme.setIconSize(icon_size)
        self.ui.btnForgotPassword.setIcon(themed_icon("key"))
        self.ui.btnForgotPassword.setIconSize(icon_size)
        self.ui.btnChangeLanguage.setIcon(themed_icon("globe"))
        self.ui.btnChangeLanguage.setIconSize(icon_size)

    def _apply_tooltips_and_status_tips(self):
        self.ui.txtUsername.setToolTip("Enter your username (max 50 characters).")
        self.ui.txtUsername.setStatusTip("Your Medical ERP username.")

        self.ui.txtPassword.setToolTip("Enter your password.")
        self.ui.txtPassword.setStatusTip("Your Medical ERP password.")

        self.ui.chkShowPassword.setToolTip("Show the password in plain text while typing.")
        self.ui.chkRememberMe.setToolTip("Remember my username, company, and financial year next time.")

        self.ui.btnLogin.setToolTip("Login (Enter)")
        self.ui.btnLogin.setStatusTip("Sign in to Medical ERP.")
        self.ui.btnExit.setToolTip("Exit (Esc)")
        self.ui.btnTheme.setToolTip("Switch between Light and Dark theme (Ctrl+T)")
        self.ui.btnForgotPassword.setStatusTip("Reset your password (contact your administrator).")
        self.ui.btnChangeLanguage.setToolTip("Change interface language")
        self.ui.btnChangeLanguage.setStatusTip("English, हिन्दी, नेपाली")

    def _setup_shortcuts(self):
        self._login_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.handle_login)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.ui.txtUsername.setFocus)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.ui.txtPassword.setFocus)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._handle_theme_toggle)

    def _handle_theme_toggle(self):
        new_theme = toggle_theme()
        self.statusBar().showMessage(f"Theme switched to {new_theme}", 3000)

    def _handle_forgot_password(self):
        dialog = ForgotPasswordDialog(self)
        dialog.exec()

    def _handle_change_language(self):
        dialog = LanguageDialog(self)
        dialog.exec()

    def _start_clock(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        now_time = QTime.currentTime().toString("hh:mm:ss")
        today_ad = QDate.currentDate().toPython()

        self.ui.lblCurrentTime.setText(now_time)

        # BS Date is the PRIMARY business date (LOCKED rule) -
        # always shown first; AD is shown as secondary/internal
        # reference. Conversion goes ONLY through the Date Engine.
        try:
            today_bs = ad_to_bs(today_ad)
            self.ui.lblTodayDate.setText(f"Today (BS): {today_bs}  |  AD: {today_ad.isoformat()}")
        except DateEngineError:
            # bscalendar not yet imported for this date - show AD
            # only rather than crash; see database/migrate_bscalendar.py
            self.ui.lblTodayDate.setText(f"Today (AD): {today_ad.isoformat()} (BS unavailable - import bscalendar)")

    def _toggle_password_visibility(self, checked: bool):
        if checked:
            self.ui.txtPassword.setEchoMode(self.ui.txtPassword.EchoMode.Normal)
        else:
            self.ui.txtPassword.setEchoMode(self.ui.txtPassword.EchoMode.Password)

    def _update_caps_lock_hint(self):
        """
        Shows a warning under the password field when Caps Lock
        is ON, since that is a common cause of failed logins.
        Uses the Windows API directly (this application's
        target OS, per the project's stated environment).
        """
        if self._is_caps_lock_on():
            self.ui.lblCapsLock.setText("Caps Lock is ON")
        else:
            self.ui.lblCapsLock.setText("")

    @staticmethod
    def _is_caps_lock_on() -> bool:
        try:
            import ctypes
            VK_CAPITAL = 0x14
            return bool(ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 1)
        except (AttributeError, OSError):
            # Not running on Windows (e.g. during development on
            # another OS) - Caps Lock hint simply stays off.
            return False

    # -----------------------------------------------------
    # DATA LOADING
    # -----------------------------------------------------

    def _load_companies(self):
        self.ui.cmbCompany.clear()

        try:
            companies = company_model.get_active_companies()
        except Exception as e:
            logger.error(f"Failed to load companies: {e}")
            self.ui.lblConnectionStatus.setText("Database: Not Connected")
            return

        self.ui.lblConnectionStatus.setText("Database: Connected")

        for company in companies:
            self.ui.cmbCompany.addItem(company["companyname"], company["companyid"])
        self._on_company_changed(self.ui.cmbCompany.currentIndex())

    def _on_company_changed(self, _index: int) -> None:
        company_id = self.ui.cmbCompany.currentData()
        if not company_id:
            set_company_logo(self.ui.lblCompanyLogo, None, QSize(112, 112))
            return
        try:
            branding = company_model.get_company_branding(company_id)
        except Exception:
            logger.exception("Failed to load selected company branding for Login.")
            set_company_logo(self.ui.lblCompanyLogo, None, QSize(112, 112))
            return

        if branding is None:
            logger.warning("Selected company '%s' has no active branding record.", company_id)
            set_company_logo(self.ui.lblCompanyLogo, None, QSize(112, 112))
            return
        set_company_logo(self.ui.lblCompanyLogo, branding.get("logopath"), QSize(112, 112))

    def _load_financial_years(self):
        self.ui.cmbFinancialYear.clear()

        try:
            years = get_all_financial_years()
        except Exception as e:
            logger.error(f"Failed to load financial years: {e}")
            return

        for year in years:
            self.ui.cmbFinancialYear.addItem(year["financialyear"], year["financialyear"])

            if year["isactive"]:
                self.ui.cmbFinancialYear.setCurrentText(year["financialyear"])
                self.ui.lblCurrentFinancialYear.setText(f"Financial Year: {year['financialyear']}")

    def _show_license_and_subscription_status(self):
        try:
            license_ok, license_message = validate_license()
            self.ui.lblLicense.setText(f"License: {'Active' if license_ok else 'Invalid'}")
            self.ui.lblLicenseStatus.setText(f"License: {license_message}")
        except Exception as e:
            logger.error(f"License check failed: {e}")

        try:
            sub_ok, sub_message = validate_subscription()
            self.ui.lblSubscriptionStatus.setText(f"Subscription: {sub_message}")
        except Exception as e:
            logger.error(f"Subscription check failed: {e}")

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    def _setup_remember_me(self):
        """Offer active accounts as username suggestions and retain saved-login autofill."""
        from PySide6.QtWidgets import QCompleter

        try:
            usernames = user_model.get_active_usernames()
        except user_model.UserModelError:
            logger.exception("Failed to load active usernames for Login suggestions.")
            usernames = []

        self._remember_me_completer = QCompleter(usernames, self)
        self._remember_me_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._remember_me_completer.setFilterMode(Qt.MatchStartsWith)
        self._remember_me_completer.setMaxVisibleItems(10)
        self.ui.txtUsername.setCompleter(self._remember_me_completer)
        self._remember_me_completer.activated.connect(self._on_remembered_username_selected)
        self.ui.txtUsername.installEventFilter(self)

    def eventFilter(self, watched, event):
        if (
            watched is self.ui.txtUsername
            and event.type() == QEvent.Type.MouseButtonPress
            and self._remember_me_completer.completionCount()
        ):
            QTimer.singleShot(0, self._show_active_username_suggestions)
        return super().eventFilter(watched, event)

    def _show_active_username_suggestions(self):
        completer = self._remember_me_completer
        completer.setCompletionPrefix(self.ui.txtUsername.text())
        completer.complete()

    def _on_remembered_username_selected(self, username):
        from utils.remembered_logins import load_remembered_login

        entry = load_remembered_login(username)
        if entry is None:
            return
        self.ui.txtPassword.setText(entry.get("password", ""))
        if entry.get("company_id") is not None:
            idx = self.ui.cmbCompany.findData(entry["company_id"])
            if idx >= 0:
                self.ui.cmbCompany.setCurrentIndex(idx)
        if entry.get("financial_year"):
            idx = self.ui.cmbFinancialYear.findText(entry["financial_year"])
            if idx >= 0:
                self.ui.cmbFinancialYear.setCurrentIndex(idx)
        self.ui.chkRememberMe.setChecked(True)

    def handle_login(self):
        username = self.ui.txtUsername.text().strip()

        if self._lockout_end_time is not None:
            if username == self._lockout_username:
                return
            self._end_lockout_countdown(clear_message=True)
        password = self.ui.txtPassword.text()
        company_id = self.ui.cmbCompany.currentData()
        financial_year = self.ui.cmbFinancialYear.currentData()

        self.ui.lblLoginMessage.setText("")

        result = login(username, password, company_id, financial_year)

        if not result.success:
            locked_until = getattr(result, "locked_until", None)
            if locked_until is not None:
                self._start_lockout_countdown(locked_until, username)
                logger.info(f"Failed login attempt for username='{username}': account locked until {locked_until}")
                return

            self.ui.lblLoginMessage.setText(result.message)
            show_warning(result.message, "Login Failed")
            logger.info(f"Failed login attempt for username='{username}': {result.message}")
            return

        logger.info(f"User '{username}' logged in successfully. Session={result.session_id}")

        from engines import session_manager
        session_manager.reset_activity_tracking()
        session_manager.set_current_role(result.roleid, result.is_admin)

        from utils.remembered_logins import save_remembered_login, remove_remembered_login
        if self.ui.chkRememberMe.isChecked():
            save_remembered_login(username, password, company_id, financial_year)
        else:
            remove_remembered_login(username)

        self.login_result = result
        self.close()

    def _start_lockout_countdown(self, end_time, username) -> None:
        self._lockout_end_time = end_time
        self._lockout_username = username

        if self._lockout_countdown_timer is None:
            self._lockout_countdown_timer = QTimer(self)
            self._lockout_countdown_timer.timeout.connect(self._tick_lockout_countdown)

        self._tick_lockout_countdown()
        self._lockout_countdown_timer.start(1000)

    def _tick_lockout_countdown(self) -> None:
        if self._lockout_end_time is None:
            return

        remaining = self._lockout_end_time - datetime.now()
        total_seconds = int(remaining.total_seconds())

        if total_seconds <= 0:
            self._end_lockout_countdown(clear_message=False)
            self.ui.lblLoginMessage.setText("Account unlocked. You can try logging in again.")
            return

        if self.ui.txtUsername.text().strip() == self._lockout_username:
            minutes, seconds = divmod(total_seconds, 60)
            self.ui.lblLoginMessage.setText(f"Account locked. Try again in {minutes}:{seconds:02d}.")

    def _end_lockout_countdown(self, clear_message: bool = True) -> None:
        if self._lockout_countdown_timer is not None:
            self._lockout_countdown_timer.stop()
        self._lockout_end_time = None
        self._lockout_username = None
        if clear_message:
            self.ui.lblLoginMessage.setText("")

    def _inject_first_time_setup_button(self) -> None:
        from PySide6.QtWidgets import QPushButton

        self.ui.btnFirstTimeSetup = QPushButton("+ First-Time Setup", self)
        self.ui.btnFirstTimeSetup.setFlat(True)
        self.ui.btnFirstTimeSetup.setStyleSheet(
            "QPushButton { font-weight: bold; font-size: 15px; color: #e67e22; border: none; padding: 4px; }"
        )

        container_layout = self.ui.lblConnectionStatus.parentWidget().layout()
        container_layout.replaceWidget(self.ui.lblConnectionStatus, self.ui.btnFirstTimeSetup)
        self.ui.lblConnectionStatus.hide()

        self.ui.btnFirstTimeSetup.clicked.connect(self._handle_first_time_setup)
        self._refresh_first_time_setup_visibility()

    def _refresh_first_time_setup_visibility(self) -> None:
        from engines.bootstrap_engine import is_bootstrap_needed
        try:
            needed = is_bootstrap_needed()
        except Exception:
            needed = False
        self.ui.btnFirstTimeSetup.setVisible(needed)

    def _handle_first_time_setup(self) -> None:
        from screens.first_time_setup_dialog import FirstTimeSetupDialog
        dialog = FirstTimeSetupDialog(self)
        if dialog.exec():
            self._load_companies()
            self._load_financial_years()
            self._refresh_first_time_setup_visibility()