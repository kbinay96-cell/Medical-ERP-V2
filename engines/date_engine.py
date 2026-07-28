"""
=========================================================
Medical ERP V2
Date Engine (Centralized - LOCKED)
---------------------------------------------------------
This is the ONLY module in the entire ERP allowed to
perform BS <-> AD conversion. No Screen, Model, or other
Engine may do this conversion itself.

BS (Bikram Sambat) is the PRIMARY business date. AD is the
secondary/internal date (used for PostgreSQL storage,
sorting, calculations, reports).

Why this needs a reference table:
    The Nepali (BS) calendar does not have a fixed number
    of days per month - month lengths vary irregularly
    from year to year according to the official calendar.
    A day-count formula cannot be accurate. This engine
    therefore uses the `bscalendar` reference table (the
    same real, verified data already built and populated
    in the V1 project) rather than an invented formula.
    See migrate_bscalendar.py for how to copy that data
    into this V2 database.

Functions this Engine provides (per Blueprint):
    - bs_to_ad
    - ad_to_bs
    - validate_bs_date
    - get_financial_year
    - date_diff
    - calculate_age
    - get_month_name
    - format_for_report
=========================================================
"""

import re
from datetime import date

from database.db import get_connection
from utils.app_logger import get_logger

logger = get_logger()

MONTH_NAMES_EN = [
    "Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
]


class DateEngineError(Exception):
    """Raised when a date operation cannot be completed."""


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def validate_bs_date(bs_date_text: str) -> tuple[bool, str]:
    """
    Validates a BS date string typed by the user. Accepts any
    common separator (/, -, .) - e.g. "2083/4/5", "2083-04-05".

    Returns
    -------
    (is_valid, normalized_or_error) : tuple[bool, str]
        On success, normalized_or_error is the date in the
        standard "YYYY-MM-DD" form. On failure, it is the
        error message.
    """
    if not bs_date_text or not bs_date_text.strip():
        return False, "Date is required."

    parts = [p for p in re.split(r"[^0-9]+", bs_date_text.strip()) if p != ""]

    if len(parts) != 3:
        return False, "Date must have Year, Month, and Day (e.g. 2083-04-05)."

    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return False, "Date must contain only numbers and separators."

    if not (1900 <= year <= 2200):
        return False, "Year looks invalid."

    if not (1 <= month <= 12):
        return False, "Month must be between 1 and 12."

    if not (1 <= day <= 32):
        return False, "Day must be between 1 and 32."

    normalized = f"{year:04d}-{month:02d}-{day:02d}"

    # If the bscalendar reference table has been imported,
    # also confirm this exact BS date actually exists in it.
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM bscalendar WHERE bsdate = %s", (normalized,))
                if cur.fetchone() is None:
                    return False, "This BS date does not exist in the calendar reference table."
    except Exception as e:
        # If bscalendar isn't populated yet, don't block the user
        # over infrastructure - just log it and accept the
        # syntactically-valid date.
        logger.error(f"validate_bs_date: could not check bscalendar ({e}). Accepting date syntactically.")

    return True, normalized


# ---------------------------------------------------------
# CONVERSION (bscalendar-backed)
# ---------------------------------------------------------

def bs_to_ad(bs_date_text: str) -> date:
    """
    Converts a BS date string to a Python `date` (AD).
    Raises DateEngineError if not found in the reference table.
    """
    is_valid, normalized = validate_bs_date(bs_date_text)
    if not is_valid:
        raise DateEngineError(normalized)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT addate FROM bscalendar WHERE bsdate = %s", (normalized,))
                row = cur.fetchone()
    except Exception as e:
        logger.error(f"bs_to_ad: database error ({e})")
        raise DateEngineError("Could not convert BS date - calendar data unavailable.") from e

    if row is None:
        raise DateEngineError(
            "This BS date was not found in the calendar reference table. "
            "Has bscalendar been imported for this year?"
        )

    return row["addate"]


def ad_to_bs(ad_date: date) -> str:
    """
    Converts an AD `date` to its BS date string ("YYYY-MM-DD").
    Raises DateEngineError if not found in the reference table.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bsdate FROM bscalendar WHERE addate = %s", (ad_date,))
                row = cur.fetchone()
    except Exception as e:
        logger.error(f"ad_to_bs: database error ({e})")
        raise DateEngineError("Could not convert AD date - calendar data unavailable.") from e

    if row is None:
        raise DateEngineError(
            "This AD date was not found in the calendar reference table. "
            "Has bscalendar been imported for this year?"
        )

    return row["bsdate"]


# ---------------------------------------------------------
# FINANCIAL YEAR
# ---------------------------------------------------------

def get_financial_year(bs_year: int, bs_month: int) -> str:
    """
    Nepal's fiscal year runs Shrawan (month 4) to Ashadh
    (month 3 of the following year).
    """
    if bs_month <= 3:
        return f"{bs_year - 1}/{bs_year}"
    return f"{bs_year}/{bs_year + 1}"


def get_financial_year_from_bs_date(bs_date_text: str) -> str:
    is_valid, normalized = validate_bs_date(bs_date_text)
    if not is_valid:
        raise DateEngineError(normalized)

    year, month, _ = (int(p) for p in normalized.split("-"))
    return get_financial_year(year, month)


# ---------------------------------------------------------
# DATE DIFFERENCE / AGE (calendar-agnostic - operate on AD)
# ---------------------------------------------------------

def date_diff_days(ad_date_1: date, ad_date_2: date) -> int:
    """
    Returns the absolute number of days between two AD dates.
    (Kept in AD internally, per the BS-first rule: AD is used
    for calculations.)
    """
    return abs((ad_date_2 - ad_date_1).days)


def calculate_age(birth_ad_date: date, as_of_ad_date: date | None = None) -> int:
    """
    Returns age in completed years, given an AD birth date.
    """
    if as_of_ad_date is None:
        as_of_ad_date = date.today()

    years = as_of_ad_date.year - birth_ad_date.year
    had_birthday_yet = (as_of_ad_date.month, as_of_ad_date.day) >= (birth_ad_date.month, birth_ad_date.day)

    if not had_birthday_yet:
        years -= 1

    return years


# ---------------------------------------------------------
# MONTH / YEAR UTILITIES
# ---------------------------------------------------------

def get_month_name(bs_month: int) -> str:
    if not (1 <= bs_month <= 12):
        raise DateEngineError("Month must be between 1 and 12.")
    return MONTH_NAMES_EN[bs_month - 1]


# ---------------------------------------------------------
# REPORT FORMATTING
# ---------------------------------------------------------

def format_for_report(bs_date_text: str) -> str:
    """
    Formats a BS date for display on reports, e.g.
    "2083-04-05" -> "5 Shrawan 2083"
    """
    is_valid, normalized = validate_bs_date(bs_date_text)
    if not is_valid:
        raise DateEngineError(normalized)

    year, month, day = (int(p) for p in normalized.split("-"))
    return f"{day} {get_month_name(month)} {year}"
