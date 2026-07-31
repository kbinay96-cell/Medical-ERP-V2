"""
=========================================================
Medical ERP V2
Settings Validator
---------------------------------------------------------
Purpose:
    Validates a proposed new value for a setting against
    its data_type BEFORE it is saved. Pure logic - no DB,
    no UI.
=========================================================
"""

VALID_DATA_TYPES = (
    "string", "integer", "decimal", "boolean", "date", "time",
    "json", "color", "font", "path", "printer",
)


def validate_setting_value(data_type: str, value: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message). error_message is empty
    when is_valid is True.
    """
    if data_type not in VALID_DATA_TYPES:
        return False, f"Unknown data type: {data_type}"

    if data_type == "integer":
        return _validate_integer(value)

    if data_type == "decimal":
        return _validate_decimal(value)

    if data_type == "boolean":
        return _validate_boolean(value)

    if data_type == "color":
        return _validate_color(value)

    # string/date/time/json/font/path/printer: accept any
    # non-None text here - format-specific checks (e.g. is this
    # really a valid date) belong to the Date Engine / relevant
    # module when the value is actually used, to avoid duplicating
    # that logic here.
    if value is None:
        return False, "Value is required."

    return True, ""


def _validate_integer(value: str) -> tuple[bool, str]:
    try:
        int(value)
    except (TypeError, ValueError):
        return False, "Value must be a whole number."
    return True, ""


def _validate_decimal(value: str) -> tuple[bool, str]:
    try:
        float(value)
    except (TypeError, ValueError):
        return False, "Value must be a number."
    return True, ""


def _validate_boolean(value: str) -> tuple[bool, str]:
    if str(value).strip().lower() not in ("true", "false"):
        return False, "Value must be true or false."
    return True, ""


def _validate_color(value: str) -> tuple[bool, str]:
    text = str(value).strip()
    if not text.startswith("#") or len(text) not in (4, 7):
        return False, "Color must be a hex code like #2F6FED."
    try:
        int(text[1:], 16)
    except ValueError:
        return False, "Color must be a valid hex code like #2F6FED."
    return True, ""


def parse_setting_value(data_type: str, value: str):
    """
    Converts a stored (string) setting value into its real
    Python type, for use by callers of settings_engine.get_setting().
    """
    if value is None:
        return None

    if data_type == "integer":
        return int(value)

    if data_type == "decimal":
        return float(value)

    if data_type == "boolean":
        return str(value).strip().lower() == "true"

    return value
