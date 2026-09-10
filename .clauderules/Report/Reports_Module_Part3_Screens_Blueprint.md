# Reports Module — Part 3: Screens + Combined Blueprint JSON Update

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** all Reports tables, `ReportEngine`, `ReportValidator`, `ReportQueryExecutor`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/report_runner_screen.py` — the ONE generic report screen

```python
"""
screens/report_runner_screen.py

Report Runner Screen - Medical ERP V2

THE single screen that renders ANY report_definition row -- this is
the entire point of the data-driven architecture (confirmed scope):
one file instead of 200+.

Responsibilities:
    - Left panel: Category tree (from ReportCategoryModel.list_active())
      -> report list per category (ReportDefinitionModel.list_by_category()).
    - On report selected: builds a filter panel DYNAMICALLY from that
      report's applicable_filters list -- each standard filter maps to
      a known widget type (date_from/date_to -> date pickers,
      customer_id -> searchable customer combo, item_id -> searchable
      item combo, ...), via a small fixed lookup table in this Screen
      (STANDARD_FILTER_WIDGETS), NOT per-report custom code.
    - Run button -> engine.run_report(report_code, filters, user_role).
    - Results grid: columns built from ReportResultDTO.columns_definition
      (label/type per column -- 'currency' type right-aligns and
      formats with thousands separator, 'number' plain, 'text' left).
    - Row click: if drill_down_report_code is set, recursively opens
      ANOTHER instance of this same ReportRunnerScreen for that code
      (with a sensible default filter carried over, e.g. the clicked
      row's customer_id). If drill_down_source_type is set instead,
      opens that transaction type's own EXISTING View screen (Sale
      Invoice's view, Journal's view, etc.) -- this screen never builds
      a duplicate detail view, it reuses what each module already has.
    - Export Excel / Export PDF / Print buttons -> call
      engine.build_export_metadata() then hand off to the project's
      existing ReportLab/openpyxl export utility (already used
      elsewhere in the app) with the grid's current rows + that
      metadata.
    """
    def __init__(self, parent, engine: "ReportEngine", initial_report_code: Optional[str] = None): ...
    def _load_categories(self) -> None: ...
    def _on_report_selected(self, report_code: str) -> None: ...
    def _build_filter_panel(self, applicable_filters: list[str]) -> None:
        """Maps each filter key to a widget via STANDARD_FILTER_WIDGETS
        (a fixed dict: 'date_from'->QDateEdit, 'customer_id'->searchable
        combo backed by CustomerModel.search, 'item_id'->ItemModel.search,
        etc.) -- one lookup table, reused for every report."""
        ...
    def _on_run_clicked(self) -> None: ...
    def _render_results_grid(self, result: "ReportResultDTO") -> None: ...
    def _on_row_clicked(self, row_index: int) -> None: ...
    def _on_export_excel_clicked(self) -> None: ...
    def _on_export_pdf_clicked(self) -> None: ...
    def _on_print_clicked(self) -> None: ...
```

### 1.2 `screens/management_dashboard_screen.py`

```python
class ManagementDashboardScreen(QWidget):
    """The Reports module's own landing page (distinct from Module 01's
    main app Dashboard). Calls engine.get_management_dashboard(filters)
    and renders each widget by its widget_type:
        - 'KPI' -> a single-number tile (Gross Profit, Net Profit,
          Receivable, Payable, Cash, Bank, Expired Stock).
        - 'List' -> a small ranked table (Top Selling Items, Top
          Profitable Items, Top Customers, Top Suppliers, Top
          Manufacturers, Outstanding Customers, Outstanding Suppliers).
        - 'Trend' -> a simple line/bar chart (Sales Trend, Purchase
          Trend, Profit Trend) using the same charting approach already
          used elsewhere in the app, if any -- otherwise a basic
          Qt-native chart widget.
    A period selector (This Month / This FY / Custom Range) at the top
    re-runs every widget with new date_from/date_to. Every tile is
    clickable and opens the matching detailed report via
    ReportRunnerScreen where a natural one exists (e.g. clicking Gross
    Profit opens the P&L report)."""
    def __init__(self, parent, engine: "ReportEngine"): ...
    def refresh(self, filters: dict) -> None: ...
    def _render_kpi_tile(self, widget_data: dict) -> None: ...
    def _render_list_widget(self, widget_data: dict) -> None: ...
    def _render_trend_chart(self, widget_data: dict) -> None: ...
```

### 1.3 `screens/master_search_bar_widget.py`

```python
class MasterSearchBarWidget(QWidget):
    """A single reusable search bar widget, mounted once at the top of
    the Reports module's screens (and optionally on the main app's own
    top bar, since the confirmed scope describes it as global). Calls
    engine.get_master_search_results(search_text) as the user types
    (debounced), shows a grouped dropdown (Reports / Invoices /
    Customers / Items / Accounts / ...), and on click:
        - A report name result -> opens ReportRunnerScreen for that code.
        - Any other result (invoice, customer, item, account, journal,
          ...) -> opens THAT thing's own existing View/Detail screen
          from its own module -- this widget never builds new detail
          views, purely a navigation aid."""
    def __init__(self, parent, engine: "ReportEngine"): ...
    def _on_text_changed(self, text: str) -> None: ...
    def _render_grouped_results(self, results: dict[str, list[dict]]) -> None: ...
    def _on_result_clicked(self, group_key: str, row: dict) -> None: ...
```

### 1.4 `screens/reconciliation_exceptions_screen.py`

```python
class ReconciliationExceptionsScreen(QWidget):
    """Runs the four confirmed live checks and shows ONLY the
    mismatches found (a clean check shows nothing for that section --
    "no news is good news"):
        - Trial Balance: engine.check_trial_balance_exception(date_from,
          date_to) -- one global check.
        - Stock: loops every active item_batch (or a selected subset via
          a Manufacturer/Category filter to keep it fast) calling
          engine.check_stock_exception(...) per batch, lists only the
          ones that returned non-None.
        - Receivable / Payable: same loop pattern over active customers/
          suppliers via engine.check_receivable_exception(...) /
          check_payable_exception(...).
    A 'Scan Now' button triggers the run (these are NOT run
    automatically on every screen open, since scanning every batch/
    customer/supplier live can be a heavier query set -- an explicit,
    on-demand action, same spirit as any other audit/reconciliation
    tool)."""
    def __init__(self, parent, engine: "ReportEngine", opening_balance_lookup_fn): ...
    def _on_scan_clicked(self) -> None: ...
    def _render_exceptions(self, exceptions: list[dict]) -> None: ...
```

### 1.5 Dashboard Wiring

`screens/dashboard_screen.py` — add a **top-level "Reports" sidebar item** (a new group, sitting alongside "Sale", "Purchase", "Accounts", not nested under any of them) containing: **"Management Dashboard"** (opens `ManagementDashboardScreen`, this becomes the Reports section's own landing page), **"Browse Reports"** (opens `ReportRunnerScreen` with no `initial_report_code`, showing the category tree first), **"Reconciliation Exceptions"** (opens `ReconciliationExceptionsScreen`). `MasterSearchBarWidget` is mounted once in the main app's top bar (not inside the Reports sidebar group), since the confirmed scope treats it as a global, always-visible tool.

---

## 2. Wiring Checklist

```python
from models.report_definition_model import ReportDefinitionModel
from models.report_category_model import ReportCategoryModel
from models.report_query_executor import ReportQueryExecutor
from models.management_dashboard_model import ManagementDashboardModel
from models.report_permission_model import ReportPermissionModel
from engines.report_engine import ReportEngine

report_engine = ReportEngine(
    definition_model=ReportDefinitionModel(),
    dashboard_model=ManagementDashboardModel(),
    permission_model=ReportPermissionModel(),
    executor=ReportQueryExecutor(),
    search_delegates={
        "sale_invoices": sale_invoice_model_instance.search,
        "purchase_invoices": purchase_invoice_model_instance.search,
        "sale_returns": sale_return_model_instance.search,
        "purchase_returns": purchase_return_model_instance.search,
        "receipts": receipt_model_instance.search,
        "payments": payment_model_instance.search,
        "customers": customer_model_instance.search,
        "suppliers": supplier_model_instance.search,
        "items": item_model_instance.search,
        "manufacturers": manufacturer_model_instance.search,
        "accounts": coa_model_instance.search,
        "journals": journal_model_instance.search,
    },
)

report_runner_screen = ReportRunnerScreen(parent=dashboard, engine=report_engine)
management_dashboard_screen = ManagementDashboardScreen(parent=dashboard, engine=report_engine)
master_search_bar = MasterSearchBarWidget(parent=main_window_top_bar, engine=report_engine)
reconciliation_exceptions_screen = ReconciliationExceptionsScreen(
    parent=dashboard, engine=report_engine,
    opening_balance_lookup_fn=opening_balance_model_instance.get_balance_for_entity,  # small helper, Accounts module
)

# No cross-module hook needed for Reports -- unlike every prior money-
# moving module, this Engine never writes, so none of the six other
# Engines need a new constructor parameter for it. Reports is purely a
# CONSUMER of everything already built.
```

---

## 3. Suggested Build Order (Reports, step-by-step)

```
1. database/0019_create_reports.sql   (report_category + report_definition + management_dashboard_widget + report_permission, Part 1)
2. models/report_definition_model.py, models/report_category_model.py,
   models/report_query_executor.py, models/management_dashboard_model.py,
   models/report_permission_model.py    (Part 1)
3. engines/report_validator.py                    (Part 2)
4. engines/report_engine.py                        (Part 2)
5. Wire ReportEngine + search_delegates in main.py   (Part 3, section 2)
6. screens/report_runner_screen.py                (Part 3)
7. screens/management_dashboard_screen.py         (Part 3)
8. screens/master_search_bar_widget.py            (Part 3)
9. screens/reconciliation_exceptions_screen.py    (Part 3)
10. Wire Dashboard "Reports" top-level group + mount MasterSearchBarWidget globally (Part 3, section 1.5)
11. SEED all ~200 confirmed report_definition rows + ~13 management_dashboard_widget rows (content-authoring task, not code -- see note below)
12. End-to-end test: run Item-wise Sales -> confirm totals match a
    manual sum -> drill down to a Sale Invoice -> confirm it opens the
    real Sale Invoice view -> run Trial Balance -> confirm Debit=Credit
    -> Master Search "ABC" -> confirm it shows matching reports AND
    matching customers/items in separate groups -> Management Dashboard
    -> confirm every KPI matches its own report's total -> Scan
    Reconciliation Exceptions with a deliberately mismatched test
    record -> confirm it's caught
```

> **Note on step 11:** authoring all ~200 `report_definition.sql_template` rows (one INSERT per report, each with its own tested SELECT) is itself a substantial body of work — comparable in size to this whole module's code — but it is DATA entry against an already-built, already-tested Engine, not new architecture. It can be done incrementally, report-by-report, post-launch, without touching a single Python file, which is exactly the payoff of the data-driven design confirmed at the start of this module.

---

## 4. Combined Blueprint JSON — Reports block (the FINAL module block)

```json
[
  { "id": "RP01", "module": "Reports", "phase": "Part-1 Database", "title": "Create report_category + report_definition + management_dashboard_widget + report_permission", "file": "database/0019_create_reports.sql", "status": "done" },
  { "id": "RP02", "module": "Reports", "phase": "Part-1 Models", "title": "Create ReportDefinitionModel (CRUD-only) + ReportCategoryModel", "file": "models/report_definition_model.py / models/report_category_model.py", "status": "done" },
  { "id": "RP03", "module": "Reports", "phase": "Part-1 Models", "title": "Create ReportQueryExecutor (shared dynamic-template execution layer)", "file": "models/report_query_executor.py", "status": "done" },
  { "id": "RP04", "module": "Reports", "phase": "Part-1 Models", "title": "Create ManagementDashboardModel + ReportPermissionModel", "file": "models/management_dashboard_model.py / models/report_permission_model.py", "status": "done" },
  { "id": "RP05", "module": "Reports", "phase": "Part-2 Engines", "title": "Create report_validator.py (filter-key, date-range, permission + financial-statement gate checks)", "file": "engines/report_validator.py", "status": "done" },
  { "id": "RP06", "module": "Reports", "phase": "Part-2 Engines", "title": "Create ReportEngine (run_report, dashboard, master search aggregation, 4 reconciliation checks, export metadata)", "file": "engines/report_engine.py", "status": "done" },
  { "id": "RP07", "module": "Reports", "phase": "Part-3 Wiring", "title": "Wire ReportEngine + all search_delegates", "file": "main.py", "status": "pending" },
  { "id": "RP08", "module": "Reports", "phase": "Part-3 Screens", "title": "Create ReportRunnerScreen (the one generic report screen)", "file": "screens/report_runner_screen.py", "status": "pending" },
  { "id": "RP09", "module": "Reports", "phase": "Part-3 Screens", "title": "Create ManagementDashboardScreen", "file": "screens/management_dashboard_screen.py", "status": "pending" },
  { "id": "RP10", "module": "Reports", "phase": "Part-3 Screens", "title": "Create MasterSearchBarWidget", "file": "screens/master_search_bar_widget.py", "status": "pending" },
  { "id": "RP11", "module": "Reports", "phase": "Part-3 Screens", "title": "Create ReconciliationExceptionsScreen", "file": "screens/reconciliation_exceptions_screen.py", "status": "pending" },
  { "id": "RP12", "module": "Reports", "phase": "Part-3 Dashboard", "title": "Add top-level 'Reports' sidebar group + mount MasterSearchBarWidget globally", "file": "screens/dashboard_screen.py", "status": "pending" },
  { "id": "RP13", "module": "Reports", "phase": "Part-3 Content", "title": "Seed all ~200 confirmed report_definition rows + ~13 management_dashboard_widget rows", "file": "database/0020_seed_report_definitions.sql", "status": "pending" },
  { "id": "RP14", "module": "Reports", "phase": "Part-3 Test", "title": "End-to-end test: report totals verified, drill-down opens real source screens, Trial Balance balances, Master Search groups results correctly, Dashboard KPIs match, reconciliation exception caught on a test mismatch", "file": null, "status": "pending" }
]
```

> **Final running total across the ENTIRE project:** 96 (through Accounts) + 14 (RP01–RP14) = **110 tasks**.

---

## 5. Every module blueprint is now complete

| # | Module | Status |
|---|---|---|
| 1 | Sale | ✅ (earlier chat) |
| 2 | Purchase | ✅ (earlier chat) |
| 3 | Sale Return | ✅ Parts 1+2+3 |
| 4 | Purchase Return | ✅ Parts 1+2+3 |
| 5 | Receipt | ✅ Parts 1+2+3 |
| 6 | Payment | ✅ Parts 1+2+3 |
| 7 | Accounts (double-entry) | ✅ Parts 1+2+3 |
| 8 | Reports | ✅ Parts 1+2+3 |

**One thing left before coding starts**, per your own plan: assembling every module's task block above into a **single combined JSON file**. I have the full Sale Return / Purchase Return / Receipt / Payment / Accounts / Reports blocks delivered in this chat — but Sale and Purchase's own original combined JSON (with the exact S01–S17 / P01–P18 task list) was generated in an earlier chat and I only have partial excerpts of it here, not its complete content. To assemble the literal single master file correctly (not guess at task IDs I haven't actually seen), please paste or upload that original Purchase+Sale combined JSON here — I'll merge every block (including today's SR/PR/RC/PY/AC/RP additions) into one final `medical_erp_v2_blueprint.json`, ready to load into your ERP-AI-Tool.
