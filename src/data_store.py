from __future__ import annotations

from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_FILE = ROOT / "telco_ops.duckdb"

TABLES = [
    "network_nodes",
    "network_links",
    "alarms",
    "link_telemetry",
    "services",
    "service_paths",
    "changes",
    "restoration_candidates",
]

def ensure_database() -> Path:
    con = duckdb.connect(str(DB_FILE))
    try:
        for table in TABLES:
            csv_file = DATA_DIR / f"{table}.csv"
            con.execute(
                f"""
                CREATE OR REPLACE TABLE {table} AS
                SELECT * FROM read_csv_auto(?, HEADER=TRUE)
                """,
                [str(csv_file)],
            )
    finally:
        con.close()
    return DB_FILE

def connect(read_only: bool = True):
    ensure_database()
    return duckdb.connect(str(DB_FILE), read_only=read_only)

def load_frames() -> dict[str, pd.DataFrame]:
    con = connect()
    try:
        return {t: con.execute(f"SELECT * FROM {t}").df() for t in TABLES}
    finally:
        con.close()

def schema_text() -> str:
    con = connect()
    try:
        parts = []
        for table in TABLES:
            desc = con.execute(f"DESCRIBE {table}").fetchall()
            cols = ", ".join(f"{r[0]} {r[1]}" for r in desc)
            parts.append(f"{table}({cols})")
        return "\n".join(parts)
    finally:
        con.close()
