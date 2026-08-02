"""
=========================================================
Medical ERP V2
Customer Model
---------------------------------------------------------
Purpose:
    All SQL for the Customer Master lives here and ONLY here.
    No business rules, no validation - those belong to
    engines.customer_engine and engines.customer_validator.
=========================================================
"""

from database.db import get_connection

_CUSTOMER_COLUMNS = (
    "customer_code", "customer_name", "print_name", "contact_person",
    "address", "city", "state", "country", "pincode",
    "phone", "mobile", "alternate_mobile", "email", "website",
    "pan_vat", "gst_number", "drug_license_no",
    "credit_limit", "credit_days", "opening_balance", "balance_type",
    "price_level_id", "area_id", "route_id", "remarks", "photo_path",
)


def get_next_customer_code(prefix: str) -> str:
    """
    Looks at existing codes with this prefix (including soft-
    deleted ones, so a deleted customer's number is never
    reused) and returns the next one, zero-padded to 4 digits,
    e.g. prefix "CUS-" + existing max 7 -> "CUS-0008".
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT customer_code FROM customers
                WHERE customer_code LIKE %s
                ORDER BY customer_id DESC
                LIMIT 1
                """,
                (f"{prefix}%",)
            )
            row = cur.fetchone()

    if not row:
        return f"{prefix}0001"

    existing_code = row["customer_code"]
    numeric_part = existing_code[len(prefix):]
    try:
        next_number = int(numeric_part) + 1
    except ValueError:
        next_number = 1

    return f"{prefix}{next_number:04d}"


def customer_name_exists(name: str, exclude_id: int | None = None) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if exclude_id:
                cur.execute(
                    "SELECT 1 FROM customers WHERE LOWER(customer_name) = LOWER(%s) "
                    "AND is_deleted = FALSE AND customer_id != %s",
                    (name, exclude_id)
                )
            else:
                cur.execute(
                    "SELECT 1 FROM customers WHERE LOWER(customer_name) = LOWER(%s) AND is_deleted = FALSE",
                    (name,)
                )
            return cur.fetchone() is not None


def customer_code_exists(code: str, exclude_id: int | None = None) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if exclude_id:
                cur.execute(
                    "SELECT 1 FROM customers WHERE customer_code = %s "
                    "AND is_deleted = FALSE AND customer_id != %s",
                    (code, exclude_id)
                )
            else:
                cur.execute(
                    "SELECT 1 FROM customers WHERE customer_code = %s AND is_deleted = FALSE",
                    (code,)
                )
            return cur.fetchone() is not None


def create_customer(data: dict, created_by: str, created_at_bs: str) -> int:
    columns = list(_CUSTOMER_COLUMNS)
    values = [data.get(col) for col in columns]

    columns += ["created_by", "created_at_bs"]
    values += [created_by, created_at_bs]

    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(columns)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO customers ({column_list}) VALUES ({placeholders}) RETURNING customer_id",
                values
            )
            return cur.fetchone()["customer_id"]


def update_customer(customer_id: int, data: dict, updated_by: str, updated_at_bs: str) -> None:
    columns = list(_CUSTOMER_COLUMNS)
    set_clause = ", ".join([f"{col} = %s" for col in columns])
    values = [data.get(col) for col in columns]

    values += [updated_by, updated_at_bs, customer_id]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE customers
                   SET {set_clause}, updated_by = %s, updated_at_ad = CURRENT_TIMESTAMP, updated_at_bs = %s
                 WHERE customer_id = %s
                """,
                values
            )


def get_customer_by_id(customer_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
            return cur.fetchone()


def list_customers(
    search_text: str | None = None,
    is_active: bool | None = None,
    area_id: int | None = None,
    route_id: int | None = None,
    price_level_id: int | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    conditions = []
    params: list = []

    if not include_deleted:
        conditions.append("is_deleted = FALSE")

    if search_text:
        conditions.append(
            "(customer_code ILIKE %s OR customer_name ILIKE %s OR print_name ILIKE %s "
            "OR mobile ILIKE %s OR pan_vat ILIKE %s OR contact_person ILIKE %s)"
        )
        like_text = f"%{search_text}%"
        params += [like_text] * 6

    if is_active is not None:
        conditions.append("is_active = %s")
        params.append(is_active)

    if area_id is not None:
        conditions.append("area_id = %s")
        params.append(area_id)

    if route_id is not None:
        conditions.append("route_id = %s")
        params.append(route_id)

    if price_level_id is not None:
        conditions.append("price_level_id = %s")
        params.append(price_level_id)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM customers WHERE {where_clause} ORDER BY customer_name",
                params
            )
            return cur.fetchall()


def restore_customer(customer_id: int, updated_by: str, updated_at_bs: str) -> None:
    """Reverses a soft delete - restores the customer as Active, per project's
    soft-delete-only Restore convention (see supplier_model.restore)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                   SET is_deleted = FALSE, is_active = TRUE,
                       deleted_by = NULL, deleted_at_ad = NULL, deleted_at_bs = NULL,
                       updated_by = %s, updated_at_ad = CURRENT_TIMESTAMP, updated_at_bs = %s
                 WHERE customer_id = %s
                """,
                (updated_by, updated_at_bs, customer_id)
            )

def get_area_by_name(name: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM areas WHERE LOWER(area_name) = LOWER(%s)",
                (name,)
            )
            return cur.fetchone()


def create_area(name: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO areas (area_name) VALUES (%s) RETURNING area_id",
                (name,)
            )
            return cur.fetchone()["area_id"]


def get_route_by_name(name: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM routes WHERE LOWER(route_name) = LOWER(%s)",
                (name,)
            )
            return cur.fetchone()


def create_route(name: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO routes (route_name) VALUES (%s) RETURNING route_id",
                (name,)
            )
            return cur.fetchone()["route_id"]
        
def get_active_customers() -> list[dict]:
    """
    Selection list for Sales/Receipt/Order Entry - Active,
    non-deleted customers only, per spec.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT customer_id, customer_code, customer_name FROM customers "
                "WHERE is_active = TRUE AND is_deleted = FALSE ORDER BY customer_name"
            )
            return cur.fetchall()


def soft_delete_customer(customer_id: int, deleted_by: str, deleted_at_bs: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                   SET is_deleted = TRUE, is_active = FALSE,
                       deleted_by = %s, deleted_at_ad = CURRENT_TIMESTAMP, deleted_at_bs = %s
                 WHERE customer_id = %s
                """,
                (deleted_by, deleted_at_bs, customer_id)
            )


def set_active_status(customer_id: int, is_active: bool, updated_by: str, updated_at_bs: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                   SET is_active = %s, updated_by = %s, updated_at_ad = CURRENT_TIMESTAMP, updated_at_bs = %s
                 WHERE customer_id = %s
                """,
                (is_active, updated_by, updated_at_bs, customer_id)
            )


def get_areas(active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM areas"
    if active_only:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY area_name"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def get_routes(active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM routes"
    if active_only:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY route_name"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def get_price_levels(active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM price_levels"
    if active_only:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY price_level_name"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()

def restore_customer(customer_id: int, updated_by: str, updated_at_bs: str) -> None:
    """Reverses a soft delete - restores the customer as Active."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                   SET is_deleted = FALSE, is_active = TRUE,
                       deleted_by = NULL, deleted_at_ad = NULL, deleted_at_bs = NULL,
                       updated_by = %s, updated_at_ad = CURRENT_TIMESTAMP, updated_at_bs = %s
                 WHERE customer_id = %s
                """,
                (updated_by, updated_at_bs, customer_id)
            )
