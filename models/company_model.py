"""
=========================================================
Medical ERP V2
Company Model
---------------------------------------------------------
Responsibilities:
- All SQL for the `company` table lives here and ONLY here.
- No business logic, no validation, no UI concerns.
- Every write operation is transaction-safe: commit on
  success, rollback on any exception.

NOTE: The real `company` table (confirmed via psql "\d company")
uses a TEXT `status` column ('Active'/'Inactive'), not a
boolean isactive. `isdeleted` was added separately (Option A)
so deactivating a company is never confused with deleting one.
`users.companyid` has a FK to this table - never drop a row,
only soft-delete it.
=========================================================
"""

from typing import Optional, List, Dict, Any
import psycopg2
import psycopg2.extras

from database.db import get_connection
from utils.app_logger import get_logger

logger = get_logger()


class CompanyModelError(Exception):
    """Raised when a database operation on `company` fails."""
    pass


def get_active_companies() -> list:
    """
    Used by the Login screen's cmbCompany dropdown.
    Kept exactly as it existed before Company Master was added -
    do not change its signature or query.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT companyid, companyname FROM company WHERE status = 'Active' ORDER BY companyname"
            )
            return cur.fetchall()
    finally:
        conn.close()


def generate_next_company_id(cursor) -> str:
    """
    Generates the next sequential companyid in the form COM001, COM002...
    """
    cursor.execute("""
        SELECT companyid FROM company
        WHERE companyid LIKE 'COM%%'
        ORDER BY companyid DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if not row:
        return "COM001"
    last_id = row["companyid"]
    try:
        num = int(last_id.replace("COM", "")) + 1
    except ValueError:
        num = 1
    return f"COM{num:03d}"


def company_name_exists(companyname: str, exclude_companyid: Optional[str] = None) -> bool:
    """Case-insensitive duplicate check against non-deleted companies."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if exclude_companyid:
                cur.execute("""
                    SELECT 1 FROM company
                    WHERE LOWER(companyname) = LOWER(%s)
                      AND isdeleted = FALSE
                      AND companyid <> %s
                """, (companyname, exclude_companyid))
            else:
                cur.execute("""
                    SELECT 1 FROM company
                    WHERE LOWER(companyname) = LOWER(%s)
                      AND isdeleted = FALSE
                """, (companyname,))
            return cur.fetchone() is not None
    except psycopg2.Error as e:
        logger.error(f"company_name_exists failed: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def insert_company(data: Dict[str, Any], created_by: str) -> str:
    """
    Inserts a new company row inside a transaction.
    `status` defaults to 'Active'; `country` defaults to 'Nepal'
    (both via the table's own DEFAULT, so we only set them if
    the caller explicitly provided a value).
    Returns the generated companyid.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            companyid = generate_next_company_id(cur)
            cur.execute("""
                INSERT INTO company (
                    companyid, companyname, address, contactperson, mobileno,
                    phone, email, panno, registrationno, ddano, logopath, remarks,
                    status, isdeleted, createdby
                ) VALUES (
                    %(companyid)s, %(companyname)s, %(address)s, %(contactperson)s,
                    %(mobileno)s, %(phone)s, %(email)s, %(panno)s, %(registrationno)s,
                    %(ddano)s, %(logopath)s, %(remarks)s, 'Active', FALSE, %(createdby)s
                )
            """, {
                "companyid": companyid,
                "companyname": data.get("companyname"),
                "address": data.get("address"),
                "contactperson": data.get("contactperson"),
                "mobileno": data.get("mobileno"),
                "phone": data.get("phone"),
                "email": data.get("email"),
                "panno": data.get("panno"),
                "registrationno": data.get("registrationno"),
                "ddano": data.get("ddano"),
                "logopath": data.get("logopath"),
                "remarks": data.get("remarks"),
                "createdby": created_by,
            })
        conn.commit()
        logger.info(f"Company created: {companyid} by {created_by}")
        return companyid
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"insert_company failed, rolled back: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def update_company(companyid: str, data: Dict[str, Any], modified_by: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE company SET
                    companyname = %(companyname)s,
                    address = %(address)s,
                    contactperson = %(contactperson)s,
                    mobileno = %(mobileno)s,
                    phone = %(phone)s,
                    email = %(email)s,
                    panno = %(panno)s,
                    registrationno = %(registrationno)s,
                    ddano = %(ddano)s,
                    logopath = %(logopath)s,
                    remarks = %(remarks)s,
                    modifiedby = %(modifiedby)s,
                    modifiedat = CURRENT_TIMESTAMP
                WHERE companyid = %(companyid)s AND isdeleted = FALSE
            """, {
                "companyid": companyid,
                "companyname": data.get("companyname"),
                "address": data.get("address"),
                "contactperson": data.get("contactperson"),
                "mobileno": data.get("mobileno"),
                "phone": data.get("phone"),
                "email": data.get("email"),
                "panno": data.get("panno"),
                "registrationno": data.get("registrationno"),
                "ddano": data.get("ddano"),
                "logopath": data.get("logopath"),
                "remarks": data.get("remarks"),
                "modifiedby": modified_by,
            })
            updated = cur.rowcount > 0
        conn.commit()
        if updated:
            logger.info(f"Company updated: {companyid} by {modified_by}")
        return updated
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"update_company failed, rolled back: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def soft_delete_company(companyid: str, deleted_by: str) -> bool:
    """
    Soft delete only - never DELETEs the row, since `users.companyid`
    has a FK to this table. Also flips status to 'Inactive' so it
    disappears from active dropdowns (e.g. Login screen) immediately.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE company SET
                    isdeleted = TRUE,
                    status = 'Inactive',
                    deletedby = %s,
                    deletedat = CURRENT_TIMESTAMP
                WHERE companyid = %s AND isdeleted = FALSE
            """, (deleted_by, companyid))
            affected = cur.rowcount > 0
        conn.commit()
        if affected:
            logger.info(f"Company soft-deleted: {companyid} by {deleted_by}")
        return affected
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"soft_delete_company failed, rolled back: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def restore_company(companyid: str, modified_by: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE company SET
                    isdeleted = FALSE,
                    status = 'Active',
                    modifiedby = %s,
                    modifiedat = CURRENT_TIMESTAMP,
                    deletedby = NULL,
                    deletedat = NULL
                WHERE companyid = %s AND isdeleted = TRUE
            """, (modified_by, companyid))
            affected = cur.rowcount > 0
        conn.commit()
        if affected:
            logger.info(f"Company restored: {companyid} by {modified_by}")
        return affected
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"restore_company failed, rolled back: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def set_company_status(companyid: str, status: str, modified_by: str) -> bool:
    """status must be 'Active' or 'Inactive' - validated by the Engine."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE company SET
                    status = %s,
                    modifiedby = %s,
                    modifiedat = CURRENT_TIMESTAMP
                WHERE companyid = %s AND isdeleted = FALSE
            """, (status, modified_by, companyid))
            affected = cur.rowcount > 0
        conn.commit()
        return affected
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"set_company_status failed, rolled back: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def get_company_by_id(companyid: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM company WHERE companyid = %s", (companyid,))
            row = cur.fetchone()
            return dict(row) if row else None
    except psycopg2.Error as e:
        logger.error(f"get_company_by_id failed: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()


def list_companies(
    search_term: Optional[str] = None,
    status_filter: str = "active",   # 'active' | 'inactive' | 'all'
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            clauses = []
            params: List[Any] = []

            if not include_deleted:
                clauses.append("isdeleted = FALSE")

            if status_filter == "active":
                clauses.append("status = 'Active'")
            elif status_filter == "inactive":
                clauses.append("status = 'Inactive'")
            # 'all' -> no filter on status

            if search_term:
                clauses.append("""(
                    companyname ILIKE %s OR
                    contactperson ILIKE %s OR
                    mobileno ILIKE %s OR
                    email ILIKE %s
                )""")
                like = f"%{search_term}%"
                params.extend([like, like, like, like])

            where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            cur.execute(f"""
                SELECT * FROM company
                {where_sql}
                ORDER BY companyname ASC
            """, params)

            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except psycopg2.Error as e:
        logger.error(f"list_companies failed: {e}")
        raise CompanyModelError(str(e)) from e
    finally:
        conn.close()
