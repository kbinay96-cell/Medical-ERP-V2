
"""
=========================================================
Medical ERP V2
Dashboard Screen
---------------------------------------------------------
UI event handling ONLY. No SQL here, no business rules -
everything goes through engines.dashboard_engine.
=========================================================
"""

from PySide6.QtCore import Qt, QTimer, QTime, QDate, QSize
from PySide6.QtGui import QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import QMainWindow, QTreeWidgetItem

from ui.ui_dashboard import Ui_MainWindow
from utils.message import show_info, confirm
from utils.app_logger import get_logger
from engines.authentication_engine import logout
from engines.dashboard_engine import build_dashboard, SIDEBAR_MODULES
from engines.theme_engine import toggle_theme, get_current_theme
from engines.date_engine import ad_to_bs, DateEngineError

from screens.supplier_list_screen import SupplierListScreen
from screens.supplier_form_screen import SupplierFormScreen
from screens.manufacturer_list_screen import ManufacturerListScreen

from screens.company_list_screen import CompanyListScreen
from screens.item_list_screen import ItemListScreen

from screens.settings_screen import SettingsScreen

from screens.user_list_screen import UserListScreen
from screens.customer_list_screen import CustomerListScreen
from screens.customer_form_screen import CustomerFormScreen

logger = get_logger()

REFRESH_INTERVAL_MS = 60_000  # KPI auto-refresh, configurable later via Settings
ICON_DIR = "resources/icons"

MODULE_ICONS = {
    "Masters": "building",
    "Purchase": "cart",
    "Sales": "money",
    "Inventory": "box",
    "Accounts": "report",
    "Reports": "report",
    "Settings": "settings",
}


class DashboardScreen(QMainWindow):

    def __init__(self, login_result):
        super().__init__()

        self.login_result = login_result

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.initialize()

    # -----------------------------------------------------
    # SETUP
    # -----------------------------------------------------

    def initialize(self):
        self._show_user_context()
        self._apply_icons()
        self._build_sidebar_menu()
        self._apply_tooltips_and_status_tips()
        self._setup_shortcuts()
        self._start_clock()
        self.load_dashboard_data()

        self.ui.btnLogout.clicked.connect(self.handle_logout)
        self.ui.btnAddSupplier.clicked.connect(self.open_supplier_form)
        self.ui.btnAddCustomer.clicked.connect(self.open_customer_form)
        self.ui.treeSidebarMenu.itemDoubleClicked.connect(self.open_module_from_sidebar)
        self.ui.btnTheme.clicked.connect(self._handle_theme_toggle)
        self.ui.txtSearchMenu.textChanged.connect(self._filter_sidebar_menu)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_dashboard_data)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

    def _apply_icons(self):
        icon_size = QSize(18, 18)

        self.ui.txtSearchMenu.addAction(
            QIcon(f"{ICON_DIR}/search.svg"), self.ui.txtSearchMenu.ActionPosition.LeadingPosition
        )

        self.ui.btnNotifications.setIconSize(icon_size)
        self.ui.btnLogout.setIconSize(icon_size)

        theme_icon = "moon" if get_current_theme() == "Light" else "sun"
        self.ui.btnTheme.setIcon(QIcon(f"{ICON_DIR}/{theme_icon}.svg"))
        self.ui.btnTheme.setIconSize(icon_size)

        self.ui.lblCompanyLogoSmall.setPixmap(QIcon(f"{ICON_DIR}/building.svg").pixmap(QSize(28, 28)))

    def _apply_tooltips_and_status_tips(self):
        self.ui.btnLogout.setToolTip("Logout (Ctrl+Q)")
        self.ui.btnTheme.setToolTip("Switch between Light and Dark theme (Ctrl+T)")
        self.ui.btnNotifications.setStatusTip("View current alerts.")
        self.ui.txtSearchMenu.setToolTip("Type to search the module menu.")
        self.ui.btnNewSale.setStatusTip("Open a new Sale entry (module not yet built).")
        self.ui.btnNewPurchase.setStatusTip("Open a new Purchase entry (module not yet built).")
        self.ui.btnAddCustomer.setStatusTip("Add a new Customer.")
        self.ui.btnAddSupplier.setStatusTip("Add a new Supplier.")
        self.ui.btnAddItem.setStatusTip("Add a new Item (module not yet built).")
        self.ui.btnBackupDatabase.setStatusTip("Backup the database (module not yet built).")

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.handle_logout)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._handle_theme_toggle)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.ui.txtSearchMenu.setFocus)

    def _handle_theme_toggle(self):
        new_theme = toggle_theme()
        theme_icon = "moon" if new_theme == "Light" else "sun"
        self.ui.btnTheme.setIcon(QIcon(f"{ICON_DIR}/{theme_icon}.svg"))
        self.statusBar().showMessage(f"Theme switched to {new_theme}", 3000)

    def _show_user_context(self):
        self.ui.lblLoggedInUser.setText(self.login_result.fullname or self.login_result.username)
        self.ui.lblUserRole.setText(self.login_result.rolename or "")
        self.ui.lblCurrentFinancialYearHeader.setText(f"FY: {self.login_result.financialyear or ''}")
        self.ui.lblCompanyNameHeader.setText(self.login_result.companyid or "")
        self.statusBar().showMessage(
            f"Logged in as {self.login_result.username} | Machine: {self.login_result.machine_name}"
        )

    def _build_sidebar_menu(self):
        self.ui.treeSidebarMenu.clear()

        for module_name, screen_names in SIDEBAR_MODULES.items():
            module_item = QTreeWidgetItem([module_name])
            icon_name = MODULE_ICONS.get(module_name, "list")
            module_item.setIcon(0, QIcon(f"{ICON_DIR}/{icon_name}.svg"))

            for screen_name in screen_names:
                module_item.addChild(QTreeWidgetItem([screen_name]))

            self.ui.treeSidebarMenu.addTopLevelItem(module_item)

        self.ui.treeSidebarMenu.expandAll()

    def _filter_sidebar_menu(self, search_text: str):
        """
        Filters the sidebar module tree by name as the user types.

        NOTE (future-ready): this currently only filters the
        Sidebar Menu tree. The Blueprint calls for this box to
        eventually become a Global Search across Company,
        Supplier, Customer, Item, Purchase, Sales, Invoice,
        Reports, and Settings records - once those modules
        exist. This method is the single place that behaviour
        will be added, without changing the search box itself
        or any other Screen.
        """
        search_text = search_text.strip().lower()

        root = self.ui.treeSidebarMenu.invisibleRootItem()

        for i in range(root.childCount()):
            module_item = root.child(i)
            module_matches = search_text in module_item.text(0).lower()
            any_child_matches = False

            for j in range(module_item.childCount()):
                child_item = module_item.child(j)
                child_matches = search_text in child_item.text(0).lower()
                child_item.setHidden(bool(search_text) and not child_matches and not module_matches)
                any_child_matches = any_child_matches or child_matches

            module_item.setHidden(bool(search_text) and not module_matches and not any_child_matches)

            if search_text and (module_matches or any_child_matches):
                module_item.setExpanded(True)

    def _start_clock(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        now_time = QTime.currentTime().toString("hh:mm:ss")
        today_ad = QDate.currentDate().toPython()

        try:
            today_bs = ad_to_bs(today_ad)
            self.ui.lblDashboardClock.setText(f"{today_bs} (BS)  |  {now_time}")
        except DateEngineError:
            self.ui.lblDashboardClock.setText(f"{today_ad.isoformat()} (AD)  |  {now_time}")

    # -----------------------------------------------------
    # DATA
    # -----------------------------------------------------

    def load_dashboard_data(self):
        try:
            data = build_dashboard(self.login_result.roleid, self.login_result.is_admin)
        except Exception as e:
            logger.exception(f"Dashboard failed to load data: {e}")
            return

        self.ui.lblTodaySalesValue.setText(f"{data.today_sales:,.2f}")
        self.ui.lblTodayPurchaseValue.setText(f"{data.today_purchase:,.2f}")
        self.ui.lblStockValueValue.setText(f"{data.stock_value:,.2f}")
        self.ui.lblLowStockValue.setText(str(int(data.low_stock_count)))
        self.ui.lblExpiringValue.setText(str(int(data.expiring_count)))
        self.ui.lblPendingPaymentsValue.setText(f"{data.pending_payments:,.2f}")
        self.ui.lblPendingReceiptsValue.setText(f"{data.pending_receipts:,.2f}")
        self.ui.lblActiveUsersValue.setText(str(int(data.active_users)))

        self.ui.lstAlerts.clear()
        self.ui.lstAlerts.addItems(data.alerts)
        self.ui.btnNotifications.setText(f"Alerts ({len(data.alerts)})")

        # -----------------------------------------------------
    # MODULE OPENERS
    # -----------------------------------------------------

    def open_supplier_form(self):
        """
        Opens Supplier Form directly from Dashboard Quick Action.
        """
        self.supplier_form = SupplierFormScreen(self)
        self.supplier_form.show()

    def open_customer_form(self):
        self.customer_form = CustomerFormScreen(self.login_result, parent=self)
        self.customer_form.show()

    def open_module_from_sidebar(self, item, column):
        """
        Opens modules from Sidebar.
        Currently Supplier and Company are enabled.
        """
        if item.parent() is None:
            return

        module_name = item.text(0).strip().lower()

        if module_name == "supplier":
            self.supplier_list = SupplierListScreen(self)
            self.supplier_list.setWindowFlag(Qt.Window)
            self.supplier_list.show()

        elif module_name == "company":
            
            self.company_list = CompanyListScreen(self)
            self.company_list.setWindowFlag(Qt.Window)
            self.company_list.show()

        elif module_name == "manufacturer":
            self.manufacturer_list = ManufacturerListScreen(self)
            self.manufacturer_list.setWindowFlag(Qt.Window)
            self.manufacturer_list.show()

        elif module_name == "customer":
            self.customer_list = CustomerListScreen(self.login_result, parent=self)
            self.customer_list.setWindowFlag(Qt.Window)
            self.customer_list.show()

        elif module_name == "item":
            self.item_list = ItemListScreen(self)
            self.item_list.setWindowFlag(Qt.Window)
            self.item_list.show()

        elif module_name == "user master":
            self.user_list = UserListScreen(self, current_user_id=self.login_result.userid)
            self.user_list.setWindowFlag(Qt.Window)
            self.user_list.show()

        elif module_name == "settings":
            self.settings_screen = SettingsScreen(
                current_username=self.login_result.username or "system",
                is_admin=self.login_result.is_admin,
                parent=self,
            )
            self.settings_screen.setWindowFlag(Qt.Window)
            self.settings_screen.show()
    # -----------------------------------------------------
    # LOGOUT
    # -----------------------------------------------------

    def handle_logout(self):
        if not confirm("Are you sure you want to logout?"):
            return

        logout(self.login_result.userid, self.login_result.username, self.login_result.session_id)
        show_info("You have been logged out.")
        self.close()



