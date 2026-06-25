import sqlite3
from pathlib import Path


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn
