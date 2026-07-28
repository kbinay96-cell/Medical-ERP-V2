"""
=========================================================
Medical ERP V2
Login Screen
---------------------------------------------------------
UI event handling ONLY. No SQL here, no business rules
here - everything goes through the Authentication Engine.
=========================================================
"""

from PySide6.QtCore import Qt, QTimer, QDate, QTime, QSize
from PySide6.QtGui import QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import QMainWindow, QLineEdit

from ui.ui_login import Ui_MainWindow
from utils.message import show_warning, show_info
from utils.app_logger import get_logger
from engines.authentication_engine import login
from engines.license_manager import validate_license
from engines.subscription_manager import validate_subscription
from engines.theme_engine import toggle_theme
from engines.date_engine import ad_to_bs, DateEngineError
from models.company_model import get_active_companies
from models.financialyear_model import get_all_financial_years
from screens.language_dialog import LanguageDialog

logger = get_logger()

ICON_DIR = "resources/icons"

FORGOT_PASSWORD_MESSAGE = "Password reset is managed by the System Administrator."


class LoginScreen(QMainWindow):

    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.login_result = None  # set on successful login, read by main.py

        self.initialize()

    # -----------------------------------------------------
    # SETUP
    # -----------------------------------------------------

    def initialize(self):
        self.ui.txtPassword.textChanged.connect(self._update_caps_lock_hint)

        self.ui.btnLogin.clicked.connect(self.handle_login)
        self.ui.btnExit.clicked.connect(self.close)
        self.ui.btnTheme.clicked.connect(self._handle_theme_toggle)
        self.ui.btnForgotPassword.clicked.connect(self._handle_forgot_password)
        self.ui.btnChangeLanguage.clicked.connect(self._handle_change_language)
        self.ui.chkShowPassword.toggled.connect(self._toggle_password_visibility)

        self._apply_icons()
        self._apply_tooltips_and_status_tips()
        self._setup_shortcuts()
        self._start_clock()
        self._load_companies()
        self._load_financial_years()
        self._show_license_and_subscription_status()

        self.ui.txtUsername.setFocus()

    def _apply_icons(self):
        icon_size = QSize(18, 18)

        self.ui.lblLoginIcon.setPixmap(QIcon(f"{ICON_DIR}/login.svg").pixmap(QSize(40, 40)))

        self.ui.txtUsername.addAction(QIcon(f"{ICON_DIR}/user.svg"), QLineEdit.ActionPosition.LeadingPosition)
        self.ui.txtPassword.addAction(QIcon(f"{ICON_DIR}/lock.svg"), QLineEdit.ActionPosition.LeadingPosition)

        self.ui.btnLogin.setIcon(QIcon(f"{ICON_DIR}/login.svg"))
        self.ui.btnLogin.setIconSize(icon_size)
        self.ui.btnExit.setIcon(QIcon(f"{ICON_DIR}/exit.svg"))
        self.ui.btnExit.setIconSize(icon_size)
        self.ui.btnTheme.setIcon(QIcon(f"{ICON_DIR}/sun.svg"))
        self.ui.btnTheme.setIconSize(icon_size)
        self.ui.btnForgotPassword.setIcon(QIcon(f"{ICON_DIR}/key.svg"))
        self.ui.btnForgotPassword.setIconSize(icon_size)
        self.ui.btnChangeLanguage.setIcon(QIcon(f"{ICON_DIR}/globe.svg"))
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
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.handle_login)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.ui.txtUsername.setFocus)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.ui.txtPassword.setFocus)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._handle_theme_toggle)

    def _handle_theme_toggle(self):
        new_theme = toggle_theme()
        self.statusBar().showMessage(f"Theme switched to {new_theme}", 3000)

    def _handle_forgot_password(self):
        show_info(FORGOT_PASSWORD_MESSAGE, "Forgot Password")

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
            companies = get_active_companies()
        except Exception as e:
            logger.error(f"Failed to load companies: {e}")
            self.ui.lblConnectionStatus.setText("Database: Not Connected")
            return

        self.ui.lblConnectionStatus.setText("Database: Connected")

        for company in companies:
            self.ui.cmbCompany.addItem(company["companyname"], company["companyid"])

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

    def handle_login(self):
        username = self.ui.txtUsername.text().strip()
        password = self.ui.txtPassword.text()
        company_id = self.ui.cmbCompany.currentData()
        financial_year = self.ui.cmbFinancialYear.currentData()

        self.ui.lblLoginMessage.setText("")

        result = login(username, password, company_id, financial_year)

        if not result.success:
            self.ui.lblLoginMessage.setText(result.message)
            show_warning(result.message, "Login Failed")
            logger.info(f"Failed login attempt for username='{username}': {result.message}")
            return

        logger.info(f"User '{username}' logged in successfully. Session={result.session_id}")

        self.login_result = result
        self.close()
