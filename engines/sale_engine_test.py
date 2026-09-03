# engines/sale_engine.py
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_validator import SaleInvoiceValidator
from models.sale_invoice_model import SaleInvoiceModel, SaleInvoiceSearchFilters

logger = logging.getLogger(__name__)


@dataclass
class SaleInvoiceLineDTO:
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    entry_mode: str
    qty: float
    free_qty: float
    rate: float
    discount_percent: float
    discount_amount: float = 0.0
    cc_percent: float = 0.0
    cc_amount: float = 0.0
    tax_percent: float = 0.0
    tax_amount: float = 0.0
    amount: float = 0.0


@dataclass
class SaleInvoiceDTO:
    sale_invoice_id: Optional[int]
    invoice_number: str
    customer_id: int
    customer_name: str
    invoice_date_bs: str
    sale_mode: str
    payment_type: str
    grand_total: float
    amount_paid_now: float
    balance_amount: float
    status: str
    area_id: Optional[int] = None
    price_level_id, Optional[int] = None
    lines: list[SaleInvoiceLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
