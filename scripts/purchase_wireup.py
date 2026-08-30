# scripts/purchase_wireup.py
# Example: how to construct engines and wire them into the app.
# Run/import this from your main startup code to create engine instances.

from models.purchase_order_model import PurchaseOrderModel
from models.purchase_invoice_model import PurchaseInvoiceModel
from models.item_model import ItemModel
from engines.purchase_order_engine import PurchaseOrderEngine
from engines.purchase_engine import PurchaseEngine

# item_engine_instance should be your real ItemEngine instance from app startup
# item_lookup_registry functions from engines.item_lookup_registry
from engines.item_lookup_registry import country_tax_lookup, manufacturer_lookup

def build_purchase_engines(item_engine_instance, settings_engine=None, date_engine=None, supplier_engine=None):
    # Create models
    po_model = PurchaseOrderModel()
    pi_model = PurchaseInvoiceModel()
    item_model = ItemModel()

    # Build PO engine
    po_engine = PurchaseOrderEngine(
        model=po_model,
        item_model=item_model,
        date_engine=date_engine,
        settings_engine=settings_engine,
    )

    # Build Purchase engine (needs po_engine + item_engine)
    purchase_engine = PurchaseEngine(
        model=pi_model,
        date_engine=date_engine,
        settings_engine=settings_engine,
        item_engine=item_engine_instance,
        purchase_order_engine=po_engine,
        country_tax_lookup_fn=country_tax_lookup,
        manufacturer_lookup_fn=manufacturer_lookup,
    )

    return po_engine, purchase_engine