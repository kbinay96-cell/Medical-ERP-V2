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
from PySide6.QtGui import QShortcut, QKeySequence, QIcon, QFont
from utils.icon_utils import themed_icon
from PySide6.QtWidgets import QMainWindow, QTreeWidgetItem, QApplication, QHeaderView

from ui.ui_dashboard import Ui_MainWindow
from utils.message import show_info, confirm
from utils.app_logger import get_logger
from utils.ui_standards import standardize_action_buttons, apply_action_button_style
from engines.authentication_engine import logout
from engines.dashboard_engine import build_dashboard, SIDEBAR_MODULES
from screens.password_reset_requests_screen import PasswordResetRequestsScreen
from screens.audit_log_screen import AuditLogScreen
from engines.theme_engine import toggle_theme, get_current_theme
from engines import settings_engine
from engines.date_engine import ad_to_bs, DateEngineError
from engines import session_manager
from utils.idle_activity_filter import IdleActivityFilter
from screens.lock_screen_dialog import LockScreenDialog, LockOverlay

from screens.supplier_list_screen import SupplierListScreen
from screens.supplier_form_screen import SupplierFormScreen
from screens.manufacturer_list_screen import ManufacturerListScreen
from screens.manufacturer_form_screen import ManufacturerFormScreen
from screens.supplier_manufacturer_discount_list_screen import SupplierManufacturerDiscountListScreen
from screens.supplier_manufacturer_discount_form_screen import SupplierManufacturerDiscountFormScreen
from screens.country_tax_list_screen import CountryTaxListScreen
from screens.country_tax_form_screen import CountryTaxFormScreen

from screens.company_list_screen import CompanyListScreen
from screens.company_form_screen import CompanyFormScreen
from screens.item_list_screen import ItemListScreen
from screens.item_form_screen import ItemFormScreen

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
from engines import customer_engine
from engines.sale_item_free_scheme_engine import SaleItemFreeSchemeEngine
from screens.item_free_scheme_list_screen import ItemFreeSchemeListScreen
from screens.stock_ledger_screen import StockLedgerScreen
from screens.stock_master_screen import StockMasterScreen
from utils.window_chrome import apply_standard_window_chrome

# Purchase engines
from engines.purchase_order_engine import PurchaseOrderEngine
from engines.purchase_engine import PurchaseEngine
from engines.sale_engine import SaleEngine
from engines.item_free_scheme_engine import ItemFreeSchemeEngine
from engines.supplier_engine import SupplierEngine
from engines.item_engine import ItemEngine
from engines.manufacturer_engine import ManufacturerEngine
from engines.item_lookup_registry import manufacturer_lookup, country_tax_lookup

# Models
from models.purchase_order_model import PurchaseOrderModel
from models.purchase_invoice_model import PurchaseInvoiceModel
from models.sale_invoice_model import SaleInvoiceModel
from models.sale_item_free_scheme_model import SaleItemFreeSchemeModel
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

SCREEN_ICONS = {
    "Company": "building",
    "Supplier": "truck",
    "Manufacturer": "building",
    "Customer": "customer",
    "Item": "box",
    "Supplier-Mfg Discount": "money",
    "Country Tax": "globe",
    "Purchase": "cart",
    "Purchase Order": "cart",
    "Purchase Return": "refresh",
    "New Sale": "money",
    "Sale List": "list",
    "Sale Free Scheme": "star",
    "Stock Ledger": "report",
    "Stock Master": "box",
    "Payment": "money",
    "Receipt": "money",
    "Reports": "report",
    "Audit Log": "list",
    "Settings": "settings",
    "User Master": "user",
    "Password Reset Requests": "reset_password",
    "Change Password": "key",
}

SIDEBAR_MODULE_FONT_SIZE = 11.5
SIDEBAR_SCREEN_FONT_SIZE = 10.0
SIDEBAR_ARROW_COLUMN_WIDTH = 28
SIDEBAR_ICON_SIZE = 18


class DashboardScreen(QMainWindow):

    def __init__(self, login_result):
        super().__init__()

        self.login_result = login_result

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        
        standardize_action_buttons(self)
        apply_action_button_style(self.ui.btnBackupDatabase)  # "backup" isn't a keyword match

        # lblDashboardClock is defined inside the statusbar in the .ui file,
        # which pyside6-uic wires up as a normal (left-aligned) status bar
        # widget by default. Move it to the permanent (right-aligned) slot
        # here in code, since that placement isn't expressible in the .ui
        # XML itself — the widget object and all its existing
        # setText()/clock-update code elsewhere stay unchanged.
        self.ui.statusbar.removeWidget(self.ui.lblDashboardClock)
        self.ui.statusbar.addPermanentWidget(self.ui.lblDashboardClock)

        self._is_locked = False
        self._session_ended = False

        self.initialize()

        session_manager.reset_activity_tracking()
        self._idle_filter = IdleActivityFilter(self)
        QApplication.instance().installEventFilter(self._idle_filter)

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

            self._item_free_scheme_engine = SaleItemFreeSchemeEngine(model=SaleItemFreeSchemeModel())

            from models.receipt_model import ReceiptModel
            from engines.receipt_engine import ReceiptEngine

            self._receipt_engine = ReceiptEngine(model=ReceiptModel())

            sale_invoice_model = SaleInvoiceModel()
            self._sale_engine = SaleEngine(
                model=sale_invoice_model,
                item_engine=self._item_engine,
                item_free_scheme_engine=self._item_free_scheme_engine,
                country_tax_lookup_fn=country_tax_lookup,
                manufacturer_lookup_fn=manufacturer_lookup,
                receipt_engine=self._receipt_engine,
            )

            from models.sale_return_model import SaleReturnModel
            from engines.sale_return_engine import SaleReturnEngine

            self._sale_return_engine = SaleReturnEngine(
                model=SaleReturnModel(),
                sale_invoice_model=sale_invoice_model,
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
            self._receipt_engine = None
            self._sale_return_engine = None

    # -----------------------------------------------------
    # SETUP
    # -----------------------------------------------------

    def initialize(self):
        # ---- INITIALIZE PURCHASE ENGINES (must happen before sidebar/menu
        #      actions can safely reference self._purchase_order_engine /
        #      self._purchase_engine) ----
        self._init_purchase_engines()

        # ---- Content-area navigation state (QStackedWidget-based) ----
        # self._nav_history holds the *previous* widget each time we
        # navigate forward, so Back always returns to exactly where the
        # user came from. Page 0 of stackedContentArea (the original
        # scrollMainArea / dashboard home) is never removed.
        self._nav_history = []

        self._show_user_context()
        self._apply_icons()
        self._build_sidebar_menu()

        if getattr(self.login_result, "mustchangepassword", False):
            from screens.change_password_screen import ChangePasswordScreen
            ChangePasswordScreen(self, user_id=self.login_result.userid).exec()

        self._check_pending_password_resets(show_alert=True)

        # Restoring the saved width has to wait until AFTER the window's
        # initial layout pass finishes -- calling it immediately here
        # (before show()) reads bodySplitter.width() while it still has
        # its designer-time placeholder size, so setSizes() gets computed
        # against the wrong total and Qt's real layout then overrides it
        # once the window actually appears. singleShot(0, ...) defers it
        # to right after that first layout/show, once the real size is known.
        QTimer.singleShot(0, self._restore_sidebar_width)

        # Debounced save -- splitterMoved fires continuously while
        # dragging, so we only persist ~400ms after the user stops
        # moving it (same debounce pattern used elsewhere, e.g. Item
        # Master's search box).
        self._sidebar_width_save_timer = QTimer(self)
        self._sidebar_width_save_timer.setSingleShot(True)
        self._sidebar_width_save_timer.timeout.connect(self._save_sidebar_width)
        self.ui.bodySplitter.splitterMoved.connect(self._on_sidebar_splitter_moved)

        self._apply_tooltips_and_status_tips()
        self._setup_shortcuts()
        self._start_clock()
        self.load_dashboard_data()

        self.ui.btnLogout.clicked.connect(self.handle_logout)
        self.ui.btnAddSupplier.clicked.connect(self.open_supplier_form)
        self.ui.btnAddCustomer.clicked.connect(self.open_customer_form)
        self.ui.treeSidebarMenu.itemClicked.connect(self.open_module_from_sidebar)
        self.ui.btnTheme.clicked.connect(self._handle_theme_toggle)
        self.ui.txtSearchMenu.textChanged.connect(self._filter_sidebar_menu)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_dashboard_data)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

        self.idle_check_timer = QTimer(self)
        self.idle_check_timer.timeout.connect(self._check_idle_timeout)
        self.idle_check_timer.start(30_000)  # check every 30 sec

    def _apply_icons(self):
        icon_size = QSize(18, 18)

        self.ui.txtSearchMenu.addAction(
            themed_icon("search"), self.ui.txtSearchMenu.ActionPosition.LeadingPosition
        )

        self.ui.btnNotifications.setIconSize(icon_size)
        self.ui.btnLogout.setIconSize(icon_size)

        theme_icon = "moon" if get_current_theme() == "Light" else "sun"
        self.ui.btnTheme.setIcon(themed_icon(theme_icon))
        self.ui.btnTheme.setIconSize(icon_size)

        self.ui.lblCompanyLogoSmall.setPixmap(themed_icon("building").pixmap(QSize(28, 28)))

    def _apply_tooltips_and_status_tips(self):
        self.ui.btnLogout.setToolTip("Logout (Ctrl+Q)")
        self.ui.btnTheme.setToolTip("Switch between Light and Dark theme (Ctrl+T)")
        self.ui.btnNotifications.setStatusTip("View current alerts.")
        self.ui.txtSearchMenu.setToolTip("Type to search the module menu.")
        self.ui.btnNewSale.setStatusTip("Open a new Sale entry.")
        self.ui.btnNewSale.clicked.connect(self._handle_new_sale_quick_action)
        self.ui.btnNewPurchase.setStatusTip("Open a new Purchase entry (module not yet built).")
        self.ui.btnAddCustomer.setStatusTip("Add a new Customer.")
        self.ui.btnAddSupplier.setStatusTip("Add a new Supplier.")
        self.ui.btnAddItem.setStatusTip("Add a new Item (module not yet built).")
        self.ui.btnBackupDatabase.setStatusTip("Backup the database.")
        self.ui.btnBackupDatabase.clicked.connect(self._handle_backup_database)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.handle_logout)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._handle_theme_toggle)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.ui.txtSearchMenu.setFocus)

    def _handle_theme_toggle(self):
        new_theme = toggle_theme()
        self._apply_icons()
        self._build_sidebar_menu()
        self._check_pending_password_resets()
        self.statusBar().showMessage(f"Theme switched to {new_theme}", 3000)

    def _handle_backup_database(self):
        if not session_manager.is_current_user_admin():
            show_error(self, "Backup Database", "Only an administrator can run a database backup.")
            return

        from engines.settings_engine import get_setting
        folder = get_setting("backup.folder_path", "")

        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "Choose Backup Folder")
            if not folder:
                return

        from engines.backup_engine import run_backup
        success, message = run_backup(
            folder,
            userid=self.login_result.userid,
            username=self.login_result.username,
        )
        if success:
            self.statusBar().showMessage(message.replace("\n", " — "), 5000)
        else:
            show_error(self, "Backup Database", message)

    def _auto_backup_on_exit(self):
        from engines.settings_engine import get_setting

        enabled = get_setting("backup.auto_backup_enabled", False)
        folder = get_setting("backup.folder_path", "")

        if not enabled or not folder:
            return

        self.statusBar().showMessage("Running auto-backup before exit…")
        QApplication.processEvents()

        from engines.backup_engine import run_backup
        success, message = run_backup(
            folder,
            userid=self.login_result.userid,
            username=self.login_result.username,
        )

        if success:
            self.statusBar().showMessage(message.replace("\n", " — "), 3000)
        else:
            logger.error(f"Auto-backup on exit failed: {message}")

    def _show_user_context(self):
        self.ui.lblLoggedInUser.setText(self.login_result.fullname or self.login_result.username)
        self.ui.lblUserRole.setText(self.login_result.rolename or "")
        self.ui.lblCurrentFinancialYearHeader.setText(f"FY: {self.login_result.financialyear or ''}")
        self.ui.lblCompanyNameHeader.setText(self.login_result.companyid or "")
        self.statusBar().showMessage(
            f"Logged in as {self.login_result.username} | Machine: {self.login_result.machine_name}"
        )

    def _build_sidebar_menu(self):
        tree = self.ui.treeSidebarMenu
        tree.clear()

        # Two columns: column 0 = icon + label (stretches to fill the
        # sidebar width), column 1 = a narrow fixed-width column that
        # holds a down-arrow, module rows only. Native branch decoration
        # is turned off because Qt's built-in expand arrow cannot be
        # repositioned or theme-tinted via QSS (no ::branch/::down-arrow
        # rule exists anywhere in this project) - so it's replaced with
        # our own themed icon instead.
        tree.setColumnCount(2)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIconSize(QSize(SIDEBAR_ICON_SIZE, SIDEBAR_ICON_SIZE))
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        tree.header().resizeSection(1, SIDEBAR_ARROW_COLUMN_WIDTH)

        # Font weight/size hierarchy is set per-row here rather than in
        # QSS, since QTreeWidgetItem has no depth-based CSS selector -
        # module (parent) rows are bold, child rows regular + smaller.
        module_font = QFont()
        module_font.setBold(True)
        module_font.setPointSizeF(SIDEBAR_MODULE_FONT_SIZE)

        screen_font = QFont()
        screen_font.setBold(False)
        screen_font.setPointSizeF(SIDEBAR_SCREEN_FONT_SIZE)

        for module_name, screen_names in SIDEBAR_MODULES.items():
            module_item = QTreeWidgetItem([module_name, ""])
            icon_name = MODULE_ICONS.get(module_name, "list")
            module_item.setIcon(0, themed_icon(icon_name))
            module_item.setIcon(1, themed_icon("chevron_down"))
            module_item.setTextAlignment(1, Qt.AlignCenter)
            module_item.setFont(0, module_font)

            for screen_name in screen_names:
                child_item = QTreeWidgetItem([screen_name, ""])
                child_icon_name = SCREEN_ICONS.get(screen_name, "list")
                child_item.setIcon(0, themed_icon(child_icon_name))
                child_item.setFont(0, screen_font)
                module_item.addChild(child_item)

            tree.addTopLevelItem(module_item)

    def _check_pending_password_resets(self, show_alert: bool = False) -> None:
        if not getattr(self.login_result, "is_admin", False):
            return
        try:
            from engines.password_reset_engine import get_pending_requests
            count = len(get_pending_requests())
        except Exception:  # noqa: BLE001
            logger.exception("Failed to check pending password reset requests.")
            return

        from PySide6.QtGui import QColor
        from PySide6.QtCore import Qt as _Qt

        for i in range(self.ui.treeSidebarMenu.topLevelItemCount()):
            module_item = self.ui.treeSidebarMenu.topLevelItem(i)
            for j in range(module_item.childCount()):
                child = module_item.child(j)
                if child.text(0).startswith("Password Reset Requests"):
                    if count:
                        child.setText(0, f"Password Reset Requests ({count})")
                        child.setForeground(0, QColor("#e74c3c"))
                    else:
                        child.setText(0, "Password Reset Requests")
                        child.setData(0, _Qt.ForegroundRole, None)
                    break

        if show_alert and count:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Pending Password Reset Requests",
                f"There {'is' if count == 1 else 'are'} {count} pending password reset "
                f"request{'s' if count != 1 else ''} waiting for approval.\n\n"
                "Go to Settings → Password Reset Requests to review.",
            )

        # Collapsed by default -- only module headers (Masters/Purchase/
        # Sales/...) show; user clicks a header to expand its screens.

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

    def _restore_sidebar_width(self):
        try:
            width = int(settings_engine.get_setting("dashboard.sidebar_width", 260))
        except (TypeError, ValueError):
            width = 260
        total = self.ui.bodySplitter.width() or 1200
        self.ui.bodySplitter.setSizes([width, max(total - width, 200)])

    def _on_sidebar_splitter_moved(self, pos, index):
        self._sidebar_width_save_timer.start(400)

    def _save_sidebar_width(self):
        sizes = self.ui.bodySplitter.sizes()
        if not sizes:
            return
        width = sizes[0]
        updated_by = self.login_result.username or "system"
        settings_engine.save_setting("dashboard.sidebar_width", str(width), updated_by,
                                      reason="Dashboard sidebar resized by user")

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
    # CONTENT-AREA NAVIGATION (QStackedWidget)
    # -----------------------------------------------------

    def _navigate_to(self, widget):
        """Push `widget` onto the content-area stack and show it."""
        if widget is self.ui.stackedContentArea.currentWidget():
            # Already the visible page (e.g. a repeat sidebar click on the
            # same already-open embedded module, reused via
            # _get_or_create_screen's alive branch) - nothing to do. Without
            # this guard we'd push a self-referential entry onto
            # _nav_history on every repeat click, so leaving the screen
            # would require pressing Back once per extra click before it
            # actually returned to the real previous screen.
            return
        self._nav_history.append(self.ui.stackedContentArea.currentWidget())
        self.ui.stackedContentArea.addWidget(widget)
        self.ui.stackedContentArea.setCurrentWidget(widget)

    def _navigate_back(self):
        """Return to the previous screen and dispose of the one we leave."""
        if not self._nav_history:
            return
        leaving = self.ui.stackedContentArea.currentWidget()
        previous = self._nav_history.pop()
        self.ui.stackedContentArea.setCurrentWidget(previous)
        if leaving is not previous:
            self.ui.stackedContentArea.removeWidget(leaving)
            leaving.deleteLater()
            if leaving is getattr(self, "sale_return_list", None):
                self.sale_return_list = None
            if leaving is getattr(self, "sale_return_form", None):
                self.sale_return_form = None

    def _open_item_form(self, item_id=None):
        """Open the Item form embedded in the content-area stack."""
        form = ItemFormScreen(self, item_id=item_id, engine=self._item_engine, embedded=True)
        form.saved.connect(lambda: self._on_item_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_item_form_saved(self, form):
        self._navigate_back()
        if getattr(self, "item_list", None) is not None:
            self.item_list.refresh()

    def _open_sale_return_list(self):
        from screens.sale_return_list_screen import SaleReturnListScreen

        def factory():
            screen = SaleReturnListScreen(
                sale_return_engine=self._sale_return_engine,
                current_user_id=self.login_result.userid,
                embedded=True,
                parent=self,
            )
            screen.close_requested.connect(self._navigate_back)
            screen.form_requested.connect(self._open_sale_return_form)
            screen.view_requested.connect(self._view_sale_return_form)
            return screen

        self._get_or_create_screen("sale_return_list", factory, mode="navigate")

    def _open_sale_return_form(self, _unused=None):
        """Always opens in CREATE mode — sale_return_list only emits form_requested(None)."""
        from screens.sale_return_form_screen import SaleReturnFormScreen

        self.sale_return_form = SaleReturnFormScreen(
            sale_return_engine=self._sale_return_engine,
            sale_engine=self._sale_engine,
            current_user_id=self.login_result.userid,
            sale_return_id=None,
            embedded=True,
            parent=self,
        )
        self.sale_return_form.saved.connect(self._on_sale_return_form_saved)
        self.sale_return_form.close_requested.connect(self._navigate_back)
        self._navigate_to(self.sale_return_form)

    def _view_sale_return_form(self, sale_return_id: int):
        from screens.sale_return_form_screen import SaleReturnFormScreen

        self.sale_return_form = SaleReturnFormScreen(
            sale_return_engine=self._sale_return_engine,
            sale_engine=self._sale_engine,
            current_user_id=self.login_result.userid,
            sale_return_id=sale_return_id,
            embedded=True,
            parent=self,
        )
        self.sale_return_form.saved.connect(self._on_sale_return_form_saved)
        self.sale_return_form.close_requested.connect(self._navigate_back)
        self._navigate_to(self.sale_return_form)

    def _on_sale_return_form_saved(self):
        self._navigate_back()
        if getattr(self, "sale_return_list", None) is not None:
            self.sale_return_list._refresh()

    def _open_receipt_form(self, receipt_id=None):
        """Open the Receipt form (Add or Edit) embedded in the content-area stack."""
        from screens.receipt_form_screen import ReceiptFormScreen
        from engines import customer_engine

        form = ReceiptFormScreen(
            self,
            receipt_id=receipt_id,
            engine=self._receipt_engine,
            current_user_id=self.login_result.userid,
            customer_engine=customer_engine,
            embedded=True,
        )
        form.saved.connect(lambda: self._on_receipt_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _view_receipt_form(self, receipt_id):
        """Open the Receipt form in read-only View mode, embedded."""
        from screens.receipt_form_screen import ReceiptFormScreen
        from engines import customer_engine

        form = ReceiptFormScreen(
            self,
            receipt_id=receipt_id,
            engine=self._receipt_engine,
            current_user_id=self.login_result.userid,
            customer_engine=customer_engine,
            embedded=True,
            read_only=True,
        )
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_receipt_form_saved(self, form):
        self._navigate_back()
        if getattr(self, "receipt_list", None) is not None:
            self.receipt_list.refresh()

    def _open_manufacturer_form(self, manufacturer_id=None):
        """Open the Manufacturer form embedded in the content-area stack."""
        form = ManufacturerFormScreen(self, manufacturer_id=manufacturer_id, embedded=True)
        form.saved.connect(lambda: self._on_manufacturer_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_manufacturer_form_saved(self, form):
        self._navigate_back()
        if getattr(self, "manufacturer_list", None) is not None:
            self.manufacturer_list.refresh()

    def _open_company_form(self, company_id=None):
        """Open the Company form embedded in the content-area stack."""
        form = CompanyFormScreen(self, company_id=company_id, engine=self.company_list._engine, embedded=True)
        form.saved.connect(lambda: self._on_company_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_company_form_saved(self, form):
        self._navigate_back()
        if getattr(self, "company_list", None) is not None:
            self.company_list.refresh()

    def _open_country_tax_form(self, country_tax_id=None):
        """Open the Country Tax form embedded in the content-area stack."""
        form = CountryTaxFormScreen(
            self,
            country_tax_id=country_tax_id,
            engine=self.country_tax_list._engine,
            manufacturer_engine=ManufacturerEngine(),
            embedded=True,
        )
        form.saved.connect(lambda: self._on_country_tax_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_country_tax_form_saved(self, form):
        # No _navigate_back() here on purpose — create-mode stays open (multi-add);
        # close_requested (emitted only on edit-mode save, or Back/Close) handles navigation.
        if getattr(self, "country_tax_list", None) is not None:
            self.country_tax_list.refresh()

    def _open_supplier_form(self, supplier_id=None):
        """Open the Supplier form embedded in the content-area stack."""
        form = SupplierFormScreen(self, supplier_id=supplier_id, engine=self._supplier_engine, embedded=True)
        form.saved.connect(lambda: self._on_supplier_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_supplier_form_saved(self, form):
        # No _navigate_back() here on purpose — create-mode stays open (multi-add);
        # close_requested (emitted only on edit-mode save, or Back/Escape) handles navigation.
        if getattr(self, "supplier_list", None) is not None:
            self.supplier_list.refresh()

    def _open_supplier_manufacturer_discount_form(self, payload):
        """Open the Supplier-Manufacturer Discount form embedded in the content-area stack."""
        discount_id, initial_supplier_id = payload
        form = SupplierManufacturerDiscountFormScreen(
            self,
            discount_id=discount_id,
            engine=self.supplier_manufacturer_discount_list._engine,
            supplier_engine=self._supplier_engine,
            manufacturer_engine=ManufacturerEngine(),
            initial_supplier_id=initial_supplier_id,
            embedded=True,
        )
        form.saved.connect(lambda: self._on_supplier_manufacturer_discount_form_saved(form))
        form.close_requested.connect(self._navigate_back)
        self._navigate_to(form)

    def _on_supplier_manufacturer_discount_form_saved(self, form):
        # No _navigate_back() here on purpose — create-mode stays open (multi-add);
        # close_requested (emitted only on edit-mode save, or Back/Escape) handles navigation.
        if getattr(self, "supplier_manufacturer_discount_list", None) is not None:
            self.supplier_manufacturer_discount_list._reload_current_level()

    def _handle_new_sale_quick_action(self):
        """Handle the New Sale quick-action button -- same engine guard as
        the sidebar's 'new sale' dispatch before opening the form."""
        if self._sale_engine is None or self._item_engine is None:
            from utils.integration_adapters import show_error
            show_error(self, "Sales", "Sales engines not initialized. Please restart the application.")
            return
        self._open_sale_invoice_form()

    def _open_sale_invoice_form(self, existing_invoice_id=None):
        """Open the Sale Invoice form embedded in the content-area stack.
        Sale Invoice is full-screen -- it also reclaims the sidebar's screen
        area, restored again when the form closes or saves."""

        def factory():
            form = SaleInvoiceFormScreen(
                self,
                self._sale_engine,
                customer_engine,
                self._item_engine,
                self._item_free_scheme_engine,
                self.login_result.userid,
                current_username=self.login_result.username or "system",
                embedded=True,
                existing_invoice_id=existing_invoice_id,
            )
            form.saved.connect(lambda: self._on_sale_invoice_form_saved(form))
            form.close_requested.connect(self._navigate_back)
            form.close_requested.connect(self._restore_sidebar_width)
            form.saved.connect(self._restore_sidebar_width)
            return form

        if existing_invoice_id is None:
            # Blank "New Sale" - reuse-guarded like other sidebar screens.
            self._get_or_create_screen("sale_invoice_form", factory, mode="navigate")
        else:
            # Editing a specific invoice must always get its own fresh form -
            # reuse-guard here would risk showing a different invoice's data,
            # and must not overwrite the tracked blank "New Sale" instance.
            form = factory()
            self._navigate_to(form)

        total = self.ui.bodySplitter.width() or 1200
        self.ui.bodySplitter.setSizes([0, total])

    def _on_sale_invoice_form_saved(self, form):
        self._navigate_back()
        if getattr(self, "sale_invoice_list", None) is not None:
            self.sale_invoice_list.refresh()

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

    def _get_or_create_screen(self, attr_name, factory, mode="navigate"):
        """
        Reuse-guard for sidebar-launched screens (see open_module_from_sidebar).
        Without this, every sidebar click unconditionally built a brand new
        screen instance and stacked/opened it on top of any previous one -
        repeated clicks without using Back (embedded screens) or closing the
        window (top-level windows) piled up duplicate instances indefinitely.

        mode="navigate": screen lives in the embedded navigation stack and
        is (re)shown via self._navigate_to(...).
        mode="window": screen is an independent top-level window shown via
        apply_standard_window_chrome(...) + .show() (chrome is applied only
        once, at creation - not on every re-show).

        `factory` is a zero-argument callable that constructs and fully
        wires (signal connections, etc.) a new screen instance, but does
        NOT navigate to it / show it / apply chrome - this method owns that
        last step so it can be skipped on reuse.
        """
        existing = getattr(self, attr_name, None)
        alive = False
        if existing is not None:
            try:
                if mode == "navigate":
                    # QStackedWidget hides every page except the one
                    # currently shown, so a widget we navigated away
                    # from reports isVisible() == False even though it
                    # is still perfectly alive - checking isVisible()
                    # here would wrongly treat "not the current page"
                    # as "destroyed" and rebuild a duplicate. Checking
                    # membership in the stack (indexOf != -1) correctly
                    # distinguishes "still alive, just not the current
                    # page" from "underlying Qt object was destroyed"
                    # (which raises RuntimeError below, same as before).
                    alive = self.ui.stackedContentArea.indexOf(existing) != -1
                else:
                    # Cheap call that raises RuntimeError if the underlying
                    # Qt C++ object was already destroyed - e.g. the user
                    # closed a top-level window via its title-bar X button,
                    # leaving a dangling Python reference on self.<attr_name>.
                    existing.isVisible()
                    alive = True
            except RuntimeError:
                alive = False

        if alive:
            if mode == "navigate":
                self._navigate_to(existing)
            else:
                existing.show()
                existing.raise_()
                existing.activateWindow()
            return

        screen = factory()
        setattr(self, attr_name, screen)
        if mode == "navigate":
            self._navigate_to(screen)
        else:
            apply_standard_window_chrome(screen)
            screen.show()

    def open_module_from_sidebar(self, item, column):
        """
        Opens modules from Sidebar.
        Currently Supplier and Company are enabled.
        """
        if item.parent() is None:
            # Native branch decoration is disabled (see
            # _build_sidebar_menu), so clicking a module row no longer
            # auto-expands/collapses it - toggle it manually here.
            item.setExpanded(not item.isExpanded())
            return

        module_name = item.text(0).strip().lower()

        if module_name == "supplier":
            def _make_screen():
                screen = SupplierListScreen(self, engine=self._supplier_engine, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_supplier_form)
                return screen
            self._get_or_create_screen("supplier_list", _make_screen, mode="navigate")

        elif module_name == "company":
            def _make_screen():
                screen = CompanyListScreen(self, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_company_form)
                return screen
            self._get_or_create_screen("company_list", _make_screen, mode="navigate")

        elif module_name == "manufacturer":
            def _make_screen():
                screen = ManufacturerListScreen(self, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_manufacturer_form)
                return screen
            self._get_or_create_screen("manufacturer_list", _make_screen, mode="navigate")

        elif module_name == "supplier-mfg discount":
            def _make_screen():
                screen = SupplierManufacturerDiscountListScreen(
                    self, supplier_engine=self._supplier_engine, item_engine=self._item_engine, embedded=True,
                )
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(
                    self._open_supplier_manufacturer_discount_form
                )
                return screen
            self._get_or_create_screen("supplier_manufacturer_discount_list", _make_screen, mode="navigate")

        elif module_name == "country tax":
            def _make_screen():
                screen = CountryTaxListScreen(self, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_country_tax_form)
                return screen
            self._get_or_create_screen("country_tax_list", _make_screen, mode="navigate")

        elif module_name == "customer":
            def _make_screen():
                return CustomerListScreen(self.login_result, parent=self)
            self._get_or_create_screen("customer_list", _make_screen, mode="window")

        elif module_name == "sale free scheme":
            if self._item_free_scheme_engine is None or self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Sales", "Sales engines not initialized. Please restart the application.")
                return
            def _make_screen():
                return ItemFreeSchemeListScreen(
                    self,
                    engine=self._item_free_scheme_engine,
                    item_engine=self._item_engine,
                    current_user_id=self.login_result.userid,
                )
            self._get_or_create_screen("sale_free_scheme_list", _make_screen, mode="window")

        elif module_name == "item":
            def _make_screen():
                screen = ItemListScreen(self, engine=self._item_engine, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_item_form)
                return screen
            self._get_or_create_screen("item_list", _make_screen, mode="navigate")

        elif module_name == "user master":
            def _make_screen():
                return UserListScreen(self, current_user_id=self.login_result.userid)
            self._get_or_create_screen("user_list", _make_screen, mode="window")

        elif module_name.startswith("password reset requests"):
            from engines.session_manager import is_current_user_admin
            if not is_current_user_admin():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Access Denied", "Only administrators can access this screen.")
                return
            def _make_screen():
                screen = PasswordResetRequestsScreen(self, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                return screen
            self._get_or_create_screen("password_reset_requests_screen", _make_screen, mode="navigate")

        elif module_name == "audit log":
            from engines.session_manager import is_current_user_admin
            if not is_current_user_admin():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Access Denied", "Only administrators can access this screen.")
                return
            def _make_screen():
                screen = AuditLogScreen(self, embedded=True)
                screen.close_requested.connect(self._navigate_back)
                return screen
            self._get_or_create_screen("audit_log_screen", _make_screen, mode="navigate")

        elif module_name == "settings":
            def _make_screen():
                return SettingsScreen(
                    current_username=self.login_result.username or "system",
                    is_admin=self.login_result.is_admin,
                    parent=self,
                )
            self._get_or_create_screen("settings_screen", _make_screen, mode="window")

        elif module_name == "change password":
            from screens.change_password_screen import ChangePasswordScreen
            ChangePasswordScreen(self, user_id=self.login_result.userid).exec()

        # ---- PURCHASE MODULE ----
        elif module_name == "purchase order":
            if self._purchase_order_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Order", "Purchase engines not initialized. Please restart the application.")
                return
            def _make_screen():
                return PurchaseOrderFormScreen(
                    parent=self,
                    engine=self._purchase_order_engine,
                    supplier_engine=self._supplier_engine,
                    item_engine=self._item_engine,
                    current_user_id=self.login_result.userid,
                )
            self._get_or_create_screen("purchase_order_form", _make_screen, mode="window")

        elif module_name == "purchase":
            if self._purchase_engine is None or self._purchase_order_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Invoice", "Purchase engines not initialized. Please restart the application.")
                return
            def _make_screen():
                return PurchaseInvoiceFormScreen(
                    parent=self,
                    engine=self._purchase_engine,
                    purchase_order_engine=self._purchase_order_engine,
                    supplier_engine=self._supplier_engine,
                    item_engine=self._item_engine,
                    current_user_id=self.login_result.userid,
                )
            self._get_or_create_screen("purchase_invoice_form", _make_screen, mode="window")

        elif module_name == "purchase list":
            if self._purchase_order_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Order", "Purchase engines not initialized. Please restart the application.")
                return
            def _make_screen():
                return PurchaseOrderListScreen(
                    parent=self,
                    engine=self._purchase_order_engine,
                    supplier_engine=self._supplier_engine,
                    item_engine=self._item_engine,
                    current_user_id=self.login_result.userid,
                )
            self._get_or_create_screen("purchase_order_list", _make_screen, mode="window")

        elif module_name == "new sale":
            if self._sale_engine is None or self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Sales", "Sales engines not initialized. Please restart the application.")
                return
            self._open_sale_invoice_form()

        elif module_name == "sale list":
            if self._sale_engine is None or self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Sales", "Sales engines not initialized. Please restart the application.")
                return
            def _make_screen():
                screen = SaleInvoiceListScreen(
                    self,
                    self._sale_engine,
                    customer_engine,
                    self._item_engine,
                    self._item_free_scheme_engine,
                    self.login_result.userid,
                    embedded=True,
                )
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_sale_invoice_form)
                screen.edit_requested.connect(self._open_sale_invoice_form)
                return screen
            self._get_or_create_screen("sale_invoice_list", _make_screen, mode="navigate")

        elif module_name == "stock ledger":
            if self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Inventory", "Item engine not initialized. Please restart the application.")
                return
            def _make_screen():
                return StockLedgerScreen(self, self._item_engine)
            self._get_or_create_screen("stock_ledger_screen", _make_screen, mode="window")

        elif module_name == "stock master":
            if self._item_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Inventory", "Item engine not initialized. Please restart the application.")
                return
            def _make_screen():
                return StockMasterScreen(self, self._item_engine)
            self._get_or_create_screen("stock_master_screen", _make_screen, mode="window")

        elif module_name == "purchase invoice list":
            if self._purchase_engine is None or self._supplier_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Purchase Invoice", "Purchase engines not initialized. Please restart the application.")
                return
            def _make_screen():
                return PurchaseInvoiceListScreen(
                    parent=self,
                    engine=self._purchase_engine,
                    supplier_engine=self._supplier_engine,
                    item_engine=self._item_engine,
                    current_user_id=self.login_result.userid,
                )
            self._get_or_create_screen("purchase_invoice_list", _make_screen, mode="window")

        # ---- ACCOUNTS MODULE ----
        elif module_name == "receipt":
            if self._receipt_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Receipt", "Receipt engine not initialized. Please restart the application.")
                return
            def _make_screen():
                from screens.receipt_list_screen import ReceiptListScreen
                screen = ReceiptListScreen(
                    parent=self,
                    engine=self._receipt_engine,
                    current_user_id=self.login_result.userid,
                    embedded=True,
                )
                screen.close_requested.connect(self._navigate_back)
                screen.form_requested.connect(self._open_receipt_form)
                screen.view_requested.connect(self._view_receipt_form)
                return screen
            self._get_or_create_screen("receipt_list", _make_screen, mode="navigate")

        elif module_name == "sale return":
            if self._sale_return_engine is None or self._sale_engine is None:
                from utils.integration_adapters import show_error
                show_error(self, "Sale Return", "Sale Return engines not initialized. Please restart the application.")
                return
            self._open_sale_return_list()
    # -----------------------------------------------------
    # LOGOUT
    # -----------------------------------------------------

    def handle_logout(self):
        if not confirm("Are you sure you want to logout?"):
            return

        self._perform_logout(show_message=True)

    def _perform_logout(self, show_message: bool = True):
        if self._session_ended:
            return
        self._session_ended = True

        logout(self.login_result.userid, self.login_result.username, self.login_result.session_id)
        if show_message:
            show_info("You have been logged out.")
        self.close()

    def _check_idle_timeout(self):
        if self._session_ended:
            return

        idle_minutes = session_manager.minutes_since_last_activity()

        if not self._is_locked:
            if session_manager.is_auto_lock_enabled() and idle_minutes >= session_manager.get_auto_lock_minutes():
                self._show_lock_screen()
            return

        # Already locked - check the full session-timeout threshold for auto-logout
        if session_manager.is_session_timeout_enabled() and idle_minutes >= session_manager.get_session_timeout_minutes():
            logger.info(f"Session timed out due to inactivity: user='{self.login_result.username}'")
            self._perform_logout(show_message=False)
            show_info("You have been logged out due to inactivity.")

    def _show_lock_screen(self):
        self._is_locked = True

        overlay = LockOverlay()
        overlay.fade_in()

        dialog = LockScreenDialog(self.login_result.username, parent=None)
        overlay.attach_dialog(dialog)
        overlay.start_keeping_on_top()

        result = dialog.exec()

        overlay.stop_keeping_on_top()
        overlay.hide()
        overlay.deleteLater()

        if result == LockScreenDialog.Accepted:
            self._is_locked = False
        elif getattr(dialog, "force_logout", False):
            self._perform_logout(show_message=False)
            show_info("Your account has been locked due to too many failed attempts. You have been logged out.")
        else:
            # Dialog was force-closed some other way - treat as still locked,
            # will be re-shown on the next idle-check tick.
            self._is_locked = True

    def closeEvent(self, event):
        if not self._session_ended and self.login_result and self.login_result.session_id:
            self._auto_backup_on_exit()
            try:
                logout(self.login_result.userid, self.login_result.username, self.login_result.session_id)
                self._session_ended = True
            except Exception:
                logger.exception("Failed to invalidate session on dashboard close.")
        super().closeEvent(event)