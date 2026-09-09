"""
Backup engine — creates a PostgreSQL backup file via pg_dump.

No UI here — this module is UI-agnostic. Screens handle folder
selection / dialogs and call run_backup() with a resolved folder path.
"""

import os
import subprocess
from datetime import datetime

from database.db import DB_CONFIG
from engines.audit_logger import write_audit_log
from config.settings import AUDIT_BACKUP


def run_backup(target_folder: str, userid: int | None = None, username: str | None = None) -> tuple[bool, str]:
    """
    Runs pg_dump against the configured database, saving a timestamped
    .backup file (pg_restore-compatible custom format) into target_folder.

    Returns (success: bool, message: str).
    """
    if not target_folder or not os.path.isdir(target_folder):
        return False, "Backup folder is not set or does not exist. Please choose a valid folder."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"medicalerp_{timestamp}.backup"
    filepath = os.path.join(target_folder, filename)

    cmd = [
        "pg_dump",
        "--host", str(DB_CONFIG["host"]),
        "--port", str(DB_CONFIG["port"]),
        "--username", str(DB_CONFIG["user"]),
        "--dbname", str(DB_CONFIG["dbname"]),
        "--format", "custom",
        "--file", filepath,
    ]

    env = {**os.environ, "PGPASSWORD": str(DB_CONFIG["password"])}

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        return False, "pg_dump was not found. Make sure PostgreSQL's bin folder is in your system PATH."
    except subprocess.TimeoutExpired:
        return False, "Backup timed out after 10 minutes."
    except Exception as exc:
        return False, f"Backup failed to start: {exc}"

    if result.returncode != 0:
        error_detail = (result.stderr or "").strip() or "Unknown pg_dump error."
        try:
            write_audit_log(
                AUDIT_BACKUP, userid=userid, username=username,
                details=f"Backup FAILED: {error_detail}",
            )
        except Exception:
            pass
        return False, f"Backup failed: {error_detail}"

    try:
        write_audit_log(
            AUDIT_BACKUP, userid=userid, username=username,
            details=f"Database backup saved to {filepath}",
        )
    except Exception:
        pass

    return True, f"Backup saved successfully:\n{filepath}"