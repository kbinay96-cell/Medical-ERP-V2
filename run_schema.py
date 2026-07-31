# run_schema.py — temporary, one-time-use script
from database.db import get_connection

with open("database/schema_auth.sql", "r", encoding="utf-8") as f:
    sql = f.read()

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

print("schema_auth.sql executed successfully — settings/settings_history tables ready.")