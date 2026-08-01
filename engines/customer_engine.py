"""
=========================================================
Medical ERP V2
Customer Engine
---------------------------------------------------------
Rule: no Screen ever queries the `customers` table (or
areas/routes/price_levels) directly - only through this
Engine. No SQL here, no Qt here - see models.customer_model
for SQL and screens.customer_list_screen /
screens.customer_form_screen for UI.

Responsibilities:
    - create_customer / update_customer  - validate + persist
    - list_customers / search_customers   - read, with filters
    - soft_delete_customer                 - Soft Delete only,
                                              per spec (no
                                              physical delete)
    - set_active_status                     - Active/Inactive toggle
    - get_active_customers                  - selection list for
                                              Sales/Receipt/Order
                                              Entry (Active only)
    - get_lookup_data                       - Area/Route/Price
                                              Level dropdowns
    - photo handling                        - via utils.image_manager,
                                              the same reusable
                                              component future
                                              modules will use
=========================================================
"""

from datetime import date

from utils.app_logger import get_logger
from utils import image_manager
from models import customer_model
from engines.customer_validator import validate_customer
from engines import settings_engine
from engines.date_engine import ad_to_bs, DateEngineError

logger = get_logger()

DEFAULT_CODE_PREFIX = "CUS-"
PHOTO_SUBFOLDER = "customers"


def get_lookup_data() -> dict:
    """
    Returns the Area / Route / Price Level options the Customer
    Form's dropdowns are built from. Never fabricated - these
    are the actual master rows in the database.
    """
    try:
        return {
            "areas": customer_model.get_areas(),
            "routes": customer_model.get_routes(),
            "price_levels": customer_model.get_price_levels(),
        }
    except Exception as e:
        logger.exception(f"get_lookup_data: database error: {e}")
        return {"areas": [], "routes": [], "price_levels": []}


def create_customer(data: dict, created_by: str) -> tuple[bool, str, int | None]:
    """
    Validates and creates a new Customer. `data` may include:
        - all columns customer_model expects
        - "_photo_source_path": path to a picked image file
          (not a DB column - consumed here, then discarded)

    Returns (success, message, new_customer_id).
    """
    data = dict(data)  # never mutate the caller's dict
    photo_source = data.pop("_photo_source_path", None)

    try:
        prefix = settings_engine.get_setting("customer.code_prefix", default=DEFAULT_CODE_PREFIX)
    except Exception as e:
        logger.exception(f"create_customer: could not read code prefix setting: {e}")
        prefix = DEFAULT_CODE_PREFIX

    manual_code = (data.get("customer_code") or "").strip()

    try:
        if manual_code:
            if customer_model.customer_code_exists(manual_code):
                return False, f"Customer Code '{manual_code}' already exists.", None
            data["customer_code"] = manual_code
        else:
            data["customer_code"] = customer_model.get_next_customer_code(prefix)
    except Exception as e:
        logger.exception(f"create_customer: database error generating/checking code: {e}")
        return False, "Could not generate Customer Code - please try again.", None

    is_valid, error_message = validate_customer(data)
    if not is_valid:
        return False, error_message, None

    try:
        if customer_model.customer_name_exists(data["customer_name"]):
            return False, f"Customer Name '{data['customer_name']}' already exists.", None
    except Exception as e:
        logger.exception(f"create_customer: database error checking name uniqueness: {e}")
        return False, "Could not verify Customer Name uniqueness - please try again.", None

    if photo_source:
        photo_ok, photo_result = image_manager.save_image(photo_source, PHOTO_SUBFOLDER, data["customer_code"])
        if photo_ok:
            data["photo_path"] = photo_result
        else:
            logger.warning(f"create_customer: photo not saved for '{data['customer_code']}': {photo_result}")
            data["photo_path"] = None

    created_at_bs = _today_bs()

    try:
        customer_id = customer_model.create_customer(data, created_by, created_at_bs)
    except Exception as e:
        logger.exception(f"create_customer: database error creating '{data.get('customer_name')}': {e}")
        return False, "Could not create customer - please try again.", None

    logger.info(f"Customer '{data['customer_code']}' created by {created_by}.")
    return True, f"Customer '{data['customer_code']}' created successfully.", customer_id


def update_customer(customer_id: int, data: dict, updated_by: str) -> tuple[bool, str]:
    """
    Validates and updates an existing Customer. `data` may
    additionally include:
        - "_photo_source_path": a newly picked replacement photo
        - "_remove_photo": True to remove the existing photo
    Both are consumed here and never reach customer_model.
    """
    data = dict(data)
    photo_source = data.pop("_photo_source_path", None)
    remove_photo = data.pop("_remove_photo", False)

    try:
        existing = customer_model.get_customer_by_id(customer_id)
    except Exception as e:
        logger.exception(f"update_customer: database error loading customer {customer_id}: {e}")
        return False, "Could not load customer - please try again."

    if existing is None:
        return False, "Customer not found."

    manual_code = (data.get("customer_code") or "").strip()
    if manual_code and manual_code != existing["customer_code"]:
        try:
            if customer_model.customer_code_exists(manual_code, exclude_id=customer_id):
                return False, f"Customer Code '{manual_code}' already exists."
        except Exception as e:
            logger.exception(f"update_customer: database error checking code uniqueness: {e}")
            return False, "Could not verify Customer Code uniqueness - please try again."
        data["customer_code"] = manual_code
    else:
        data["customer_code"] = existing["customer_code"]

    is_valid, error_message = validate_customer(data)
    if not is_valid:
        return False, error_message

    try:
        if customer_model.customer_name_exists(data["customer_name"], exclude_id=customer_id):
            return False, f"Customer Name '{data['customer_name']}' already exists."
    except Exception as e:
        logger.exception(f"update_customer: database error checking name uniqueness: {e}")
        return False, "Could not verify Customer Name uniqueness - please try again."

    if remove_photo:
        image_manager.delete_image(existing.get("photo_path"))
        data["photo_path"] = None
    elif photo_source:
        photo_ok, photo_result = image_manager.save_image(photo_source, PHOTO_SUBFOLDER, data["customer_code"])
        if photo_ok:
            data["photo_path"] = photo_result
        else:
            logger.warning(f"update_customer: photo not saved for '{data['customer_code']}': {photo_result}")
            data["photo_path"] = existing.get("photo_path")
    else:
        data["photo_path"] = existing.get("photo_path")

    updated_at_bs = _today_bs()

    try:
        customer_model.update_customer(customer_id, data, updated_by, updated_at_bs)
    except Exception as e:
        logger.exception(f"update_customer: database error updating customer {customer_id}: {e}")
        return False, "Could not update customer - please try again."

    logger.info(f"Customer '{data['customer_code']}' updated by {updated_by}.")
    return True, f"Customer '{data['customer_code']}' updated successfully."


def get_customer(customer_id: int) -> dict | None:
    try:
        return customer_model.get_customer_by_id(customer_id)
    except Exception as e:
        logger.exception(f"get_customer: database error for id {customer_id}: {e}")
        return None


def search_customers(
    search_text: str | None = None,
    is_active: bool | None = None,
    area_id: int | None = None,
    route_id: int | None = None,
    price_level_id: int | None = None,
) -> list[dict]:
    """
    Backs the Customer List screen's search box + filters
    (Active/Inactive, Area, Route, Price Level - per spec).
    """
    try:
        return customer_model.list_customers(
            search_text=search_text, is_active=is_active,
            area_id=area_id, route_id=route_id, price_level_id=price_level_id,
        )
    except Exception as e:
        logger.exception(f"search_customers: database error: {e}")
        return []


def get_active_customers() -> list[dict]:
    """
    Selection list for Sales/Receipt/Outstanding/Order Entry.
    Inactive customers must never appear there, per spec - this
    is the ONLY function those modules should call.
    """
    try:
        return customer_model.get_active_customers()
    except Exception as e:
        logger.exception(f"get_active_customers: database error: {e}")
        return []


def soft_delete_customer(customer_id: int, deleted_by: str) -> tuple[bool, str]:
    """Soft Delete only - no physical delete, per spec."""
    try:
        existing = customer_model.get_customer_by_id(customer_id)
    except Exception as e:
        logger.exception(f"soft_delete_customer: database error loading customer {customer_id}: {e}")
        return False, "Could not load customer - please try again."

    if existing is None:
        return False, "Customer not found."

    deleted_at_bs = _today_bs()

    try:
        customer_model.soft_delete_customer(customer_id, deleted_by, deleted_at_bs)
    except Exception as e:
        logger.exception(f"soft_delete_customer: database error deleting customer {customer_id}: {e}")
        return False, "Could not delete customer - please try again."

    logger.info(f"Customer '{existing['customer_code']}' soft-deleted by {deleted_by}.")
    return True, f"Customer '{existing['customer_code']}' deleted."


def set_active_status(customer_id: int, is_active: bool, updated_by: str) -> tuple[bool, str]:
    updated_at_bs = _today_bs()

    try:
        customer_model.set_active_status(customer_id, is_active, updated_by, updated_at_bs)
    except Exception as e:
        logger.exception(f"set_active_status: database error for customer {customer_id}: {e}")
        return False, "Could not update customer status - please try again."

    status_text = "activated" if is_active else "deactivated"
    logger.info(f"Customer {customer_id} {status_text} by {updated_by}.")
    return True, f"Customer {status_text}."


def _today_bs() -> str:
    """Today's date in BS, for audit stamping - never invented, always via the Date Engine."""
    try:
        return ad_to_bs(date.today())
    except DateEngineError as e:
        logger.exception(f"_today_bs: could not convert today's date to BS: {e}")
        return ""
