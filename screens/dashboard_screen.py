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
from screens.supplier_manufacturer_discount_list_screen import SupplierManufacturerDiscountListScreen
from screens.country_tax_list_screen import CountryTaxListScreen

from screens.company_list_screen import CompanyListScreen
from screens.item_list_screen import ItemListScreen

from screens.settings_screen import SettingsScreen

from screens.user_list_screen import UserListScreen
from screens.customer_list_screen import CustomerListScreen
from screens.customer_form_screen import CustomerFormScreen

# Purchase module imports
from screens.purchase_order_list_screen import PurchaseOrderListScreen
from screens.purchase_order_form_screen import PurchaseOrderFormScreen
from screens.purchase_invoice_list_screen import PurchaseInvoiceListScreen
from screens.purchase_invoice_form_screen import PurchaseInvoiceFormScreen
from screens.sale_invoice_form_screen import SaleInvoiceFormScreen
from screens.sale_invoice_list_screen import SaleInvoiceListScreen
from screens.stock_ledger_screen import StockLedgerScreen
from screens.stock_master_screen import StockMasterScreen
from utils.window_chrome import apply_standard_window_chrome

# Purchase engines
from engines.purchase_order_engine import PurchaseOrderEngine
from engines.purchase_engine import PurchaseEngine
from engines.sale_engine import SaleEngine
from engines.supplier_engine import SupplierEngine
from engines.item_engine import ItemEngine
from engines.item_lookup_registry import manufacturer_lookup, country_tax_lookup

# Models
from models.purchase_order_model import PurchaseOrderModel
from models.purchase_invoice_model import PurchaseInvoiceModel
from models.sale_invoice_model import SaleInvoiceModel
from models.item_model import ItemModel

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

        # lblDashboardClock is defined inside the statusbar in the .ui file,
        # which pyside6-uic wires up as a normal (left-aligned) status bar
        # widget by default. Move it to the permanent (right-aligned) slot
        # here in code, since that placement isn't expressible in the .ui
        # XML itself — the widget object and all its existing
        # setText()/clock-update code elsewhere stay unchanged.
        self.ui.statusbar.removeWidget(self.ui.lblDashboardClock)
        self.ui.statusbar.addPermanentWidget(self.ui.lblDashboardClock)

        self.initialize()

    def _init_purchase_engines(self):
        """Initialize Purchase module engines for dashboard use.

        self._item_engine is a fresh ItemEngine() instance. Confirmed safe
        via the real engines/item_engine.py: ItemEngine holds no in-memory
        state of its own (every method is a pure pass-through to
        ItemModel/ItemBatchModel/StockTransactionModel, which are thin DB
        wrappers) — so a second instance behaves identically to whichever
        one Item Master's own screens construct. It MUST still be given
        the real manufacturer_lookup/country_tax_lookup functions from
        item_lookup_registry.py — without them, resolve_item_tax() (and
        therefore Purchase's CC%) would silently always return (0, 0),
        since ItemEngine's own defaults are no-op fallbacks.
        """
        try:
            from engines import date_engine, settings_engine

            self._supplier_engine = SupplierEngine()
            self._po_model = PurchaseOrderModel()
            self._pi_model = PurchaseInvoiceModel()
            self._item_model = ItemModel()
            self._item_engine = ItemEngine(
                country_tax_lookup_fn=country_tax_lookup,
                manufacturer_lookup_fn=manufacturer_lookup,
            )

            self._purchase_order_engine = PurchaseOrderEngine(
                model=self._po_model,
                item_model=self._item_model,
                date_engine=date_engine,
                settings_engine=settings_engine,
            )

            self._purchase_engine = PurchaseEngine(
                model=self._pi_model,
                date_engine=date_engine,
                settings_engine=settings_engine,
                item_engine=self._item_engine,
                purchase_order_engine=self._purchase_order_engine,
            )

            self._sale_engine = SaleEngine(
                model=SaleInvoiceModel(),
                date_engine=date_engine,
                item_engine=self._item_engine,
            )
        except Exception as e:
            from utils.app_logger import get_logger
            logger = get_logger()
            logger.error(f"Failed to initialize Purchase engines: {e}")
            self._purchase_order_engine = None
            self._purchase_engine = None
            self._sale_engine = None
            self._supplier_engine = None
            self._item_engine = None

    # -----------------------------------------------------
    # SETUP
    # -----------------------------------------------------

    def initialize(self):
        # ---- INITIALIZE PURCHASE ENGINES (must happen before sidebar/menu
        #      actions can safely reference self._purchase_order_engine /
        #      self._purchase_engine) ----
        self._init_purchase_engines()

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
            apply_standard_window_chrome(self.supplier_list)
            self.supplier_list.show()

        elif module_name == "company":
            
            self.company_list = CompanyListScreen(self)
            apply_standard_window_chrome(self.company_list)
            self.company_list.show()

        elif module_name == "manufacturer":
            self.manufacturer_list = ManufacturerListScreen(self)
            apply_standard_window_chrome(self.manufacturer_list)
            self.manufacturer_list.show()

        elif module_name == "supplier-mfg discount":
            self.supplier_manufacturer_discount_list = SupplierManufacturerDiscountListScreen(self)
            apply_standard_window_chrome(self.supplier_manufacturer_discount_list)
            self.supplier_manufacturer_discount_list.show()

        elif module_name == "country tax":                          # <-- NAYA BLOCK
            self.country_tax_list = CountryTaxListScreen(self)
            apply_standard_window_chrome(self.country_tax_list)
            self.country_tax_list.show()

        elif module_name == "customer":
            self.customer_list = CustomerListScreen(self.login_result, parent=self)
            apply_standard_window_chrome(self.customer_list)
            self.customer_list.show()

        elif module_name == "item":
            self.item_list = ItemListScreen(self)
            apply_standard_window_chrome(self.item_list)
            self.item_list.show()

        elif module_name == "user master":
            self.user_list = UserListScreen(self, current_user_id=self.login_result.userid)
            apply_standard_window_chrome(self.user_list)
            self.user_list.show()

        elif module_name == "settings":
            self.settings_screen = SettingsScreen(
                current_username=self.login_result.username or "system",
                is_admin=self.login_result.is_admin,
                parent=self,
            )
            apply_standard_window_chrome(self.settings_screen)
            self.settings_screen.show()

        # ---- PURCHASE MODULE ----
        elif module_name == "purchase order":
            if self._purchase_order_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Order", "Purchase engines not initialized. Please restart the application.")
                return

            self.purchase_order_form = PurchaseOrderFormScreen(
                parent=self,
                engine=self._purchase_order_engine,
                supplier_engine=self._supplier_engine,
                item_engine=self._item_engine,
                current_user_id=self.login_result.userid,
            )
            apply_standard_window_chrome(self.purchase_order_form)
            self.purchase_order_form.show()

        elif module_name == "purchase":
            if self._purchase_engine is None or self._purchase_order_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Invoice", "Purchase engines not initialized. Please restart the application.")
                return

            self.purchase_invoice_form = PurchaseInvoiceFormScreen(
                parent=self,
                engine=self._purchase_engine,
                purchase_order_engine=self._purchase_order_engine,
                supplier_engine=self._supplier_engine,
                item_engine=self._item_engine,
                current_user_id=self.login_result.userid,
            )
            apply_standard_window_chrome(self.purchase_invoice_form)
            self.purchase_invoice_form.show()

        elif module_name == "purchase list":
            if self._purchase_order_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Order", "Purchase engines not initialized. Please restart the application.")
                return

            self.purchase_order_list = PurchaseOrderListScreen(
                parent=self,
                engine=self._purchase_order_engine,
                supplier_engine=self._supplier_engine,
                item_engine=self._item_engine,
                current_user_id=self.login_result.userid,
            )
            apply_standard_window_chrome(self.purchase_order_list)
            self.purchase_order_list.show()

        elif module_name == "new sale":
            if self._sale_engine is None or self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Sales", "Sales engines not initialized. Please restart the application.")
                return
            self.sale_invoice_form = SaleInvoiceFormScreen(
                parent=self,
                engine=self._sale_engine,
                item_engine=self._item_engine,
                current_user_id=self.login_result.userid,
            )
            apply_standard_window_chrome(self.sale_invoice_form)
            self.sale_invoice_form.show()

        elif module_name == "sale list":
            if self._sale_engine is None or self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Sales", "Sales engines not initialized. Please restart the application.")
                return
            self.sale_invoice_list = SaleInvoiceListScreen(
                parent=self,
                engine=self._sale_engine,
                item_engine=self._item_engine,
                current_user_id=self.login_result.userid,
            )
            apply_standard_window_chrome(self.sale_invoice_list)
            self.sale_invoice_list.show()

        elif module_name == "stock ledger":
            if self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Inventory", "Item engine not initialized. Please restart the application.")
                return
            self.stock_ledger_screen = StockLedgerScreen(self, self._item_engine)
            apply_standard_window_chrome(self.stock_ledger_screen)
            self.stock_ledger_screen.show()

        elif module_name == "stock master":
            if self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Inventory", "Item engine not initialized. Please restart the application.")
                return
            self.stock_master_screen = StockMasterScreen(self, self._item_engine)
            apply_standard_window_chrome(self.stock_master_screen)
            self.stock_master_screen.show()

        elif module_name == "purchase invoice list":
            if self._purchase_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Invoice", "Purchase engines not initialized. Please restart the application.")
                return

            self.purchase_invoice_list = PurchaseInvoiceListScreen(
                parent=self,
                engine=self._purchase_engine,
                supplier_engine=self._supplier_engine,
                item_engine=self._item_engine,
                current_user_id=self.login_result.userid,
            )
            apply_standard_window_chrome(self.purchase_invoice_list)
            self.purchase_invoice_list.show()
    # -----------------------------------------------------
    # LOGOUT
    # -----------------------------------------------------

    def handle_logout(self):
        if not confirm("Are you sure you want to logout?"):
            return

        logout(self.login_result.userid, self.login_result.username, self.login_result.session_id)
        show_info("You have been logged out.")
        self.close()