import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from engines import dashboard_engine
from models import dashboard_model
from screens.dashboard_screen import DashboardScreen


class SidebarPermissionFilteringTests(unittest.TestCase):
    def test_only_accessible_screens_and_their_modules_are_returned(self):
        visible = dashboard_engine.filter_sidebar_modules(
            ["Sale", "Purchase Invoice List", "Payment"]
        )

        self.assertEqual(visible["Sales"], ["New Sale", "Sale List", "Sale Free Scheme", "Sale Return"])
        self.assertEqual(visible["Purchase"], ["Purchase Invoice List"])
        self.assertEqual(visible["Accounts"], ["Payment"])
        self.assertNotIn("Masters", visible)
        self.assertEqual(visible["Settings"], ["Settings", "Change Password"])

    def test_settings_and_change_password_are_self_service_entries(self):
        visible = dashboard_engine.filter_sidebar_modules([])

        self.assertEqual(visible, {
            "Settings": ["Settings", "Change Password"],
        })

    def test_admin_gets_a_copy_of_the_complete_sidebar(self):
        visible = dashboard_engine.filter_sidebar_modules([], is_admin=True)

        self.assertEqual(visible, dashboard_engine.SIDEBAR_MODULES)
        self.assertIsNot(visible["Sales"], dashboard_engine.SIDEBAR_MODULES["Sales"])

    def test_admin_only_entries_are_hidden_from_non_admin_roles(self):
        visible = dashboard_engine.filter_sidebar_modules(
            ["Audit Log", "Password Reset Requests", "User Master"]
        )

        self.assertEqual(visible["Settings"], ["Settings", "User Master", "Change Password"])
        self.assertNotIn("Audit Log", visible.get("Reports", []))
        self.assertNotIn("Password Reset Requests", visible["Settings"])


class DashboardUserDisplayTests(unittest.TestCase):
    def test_username_is_shown_when_full_name_only_repeats_the_role(self):
        login_result = SimpleNamespace(
            fullname="Administrator",
            username="admin",
            rolename="Administrator",
        )

        self.assertEqual(
            DashboardScreen._resolve_user_display_name(login_result),
            "admin",
        )

    def test_full_name_is_preserved_when_it_differs_from_the_role(self):
        login_result = SimpleNamespace(
            fullname="Jane Smith",
            username="jsmith",
            rolename="Administrator",
        )

        self.assertEqual(
            DashboardScreen._resolve_user_display_name(login_result),
            "Jane Smith",
        )


class DashboardKpiQueryTests(unittest.TestCase):
    def test_sales_and_purchase_totals_use_live_invoice_tables(self):
        with patch.object(dashboard_model, "_safe_scalar_query", return_value=12.5) as query:
            self.assertEqual(dashboard_model.get_today_sales_total(date(2026, 10, 3)), 12.5)
            self.assertIn("FROM sale_invoice", query.call_args.args[0])
            self.assertIn("invoice_date_ad", query.call_args.args[0])
            self.assertIn("status = 'Posted'", query.call_args.args[0])
            self.assertEqual(query.call_args.args[1], (date(2026, 10, 3),))

            self.assertEqual(dashboard_model.get_today_purchase_total(date(2026, 10, 3)), 12.5)
            self.assertIn("FROM purchase_invoice", query.call_args.args[0])

    def test_stock_queries_use_batches_and_item_reorder_levels(self):
        with patch.object(dashboard_model, "_safe_scalar_query", return_value=2) as query:
            dashboard_model.get_stock_value()
            self.assertIn("FROM item_batch", query.call_args.args[0])
            self.assertIn("batch_qty * batch_purchase_rate", query.call_args.args[0])

            dashboard_model.get_low_stock_count(7)
            self.assertIn("FROM item i", query.call_args.args[0])
            self.assertIn("minimum_stock", query.call_args.args[0])
            self.assertEqual(query.call_args.args[1], (7,))

            dashboard_model.get_expiring_medicines_count(45)
            self.assertIn("expiry_year", query.call_args.args[0])
            self.assertIn("batch_qty > 0", query.call_args.args[0])
            self.assertEqual(query.call_args.args[1], (45,))

    def test_outstanding_queries_use_invoice_allocations_and_return_adjustments(self):
        with patch.object(dashboard_model, "_safe_scalar_query", return_value=2) as query:
            dashboard_model.get_pending_payments_total()
            self.assertIn("FROM purchase_invoice pi", query.call_args.args[0])
            self.assertIn("payment_allocation", query.call_args.args[0])
            self.assertIn("purchase_return", query.call_args.args[0])
            self.assertIn("Adjust Against Payable", query.call_args.args[0])

            dashboard_model.get_pending_receipts_total()
            self.assertIn("FROM sale_invoice si", query.call_args.args[0])
            self.assertIn("receipt_allocation", query.call_args.args[0])
            self.assertIn("sale_return", query.call_args.args[0])
            self.assertIn("Adjust Against Invoice", query.call_args.args[0])

    def test_database_failure_is_not_reported_as_a_zero_balance(self):
        class BrokenCursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, *_args):
                raise RuntimeError("database unavailable")

        class BrokenConnection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def cursor(self):
                return BrokenCursor()

        with patch.object(dashboard_model, "get_connection", return_value=BrokenConnection()):
            self.assertIsNone(dashboard_model.get_stock_value())


class DashboardPresentationTests(unittest.TestCase):
    def test_failed_kpis_render_as_unavailable_instead_of_zero(self):
        self.assertEqual(DashboardScreen._format_currency_kpi(None), "Unavailable")
        self.assertEqual(DashboardScreen._format_count_kpi(None), "Unavailable")
        self.assertEqual(DashboardScreen._format_currency_kpi(1234.5), "1,234.50")

    def test_master_search_only_includes_permitted_record_groups(self):
        dashboard = SimpleNamespace(
            login_result=SimpleNamespace(
                is_admin=False,
                accessible_menus=["Supplier", "Sale", "Settings"],
            )
        )
        delegates = {
            "suppliers": object(),
            "sale_invoices": object(),
            "purchase_invoices": object(),
            "settings": object(),
        }

        filtered = DashboardScreen._filter_master_search_delegates(dashboard, delegates)

        self.assertEqual(set(filtered), {"suppliers", "sale_invoices", "settings"})


if __name__ == "__main__":
    unittest.main()
