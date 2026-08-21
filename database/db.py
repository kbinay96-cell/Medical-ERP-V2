"""
=========================================================
Medical ERP V2
Database Connection
---------------------------------------------------------
Purpose:
    Single, centralized PostgreSQL connection provider.
    No business logic here. No validation here.
    Uses environment variables for configuration.
=========================================================
"""

import os
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "medical_erp_v2"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


def get_connection():
    """
    Returns a new PostgreSQL connection.
    Rows are returned as dict-like objects (access by column
    name, e.g. row["username"]), matching the rest of the
    codebase's convention.
    """
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    return conn
