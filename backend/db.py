"""
SQLite Caching Layer for GST Reconciliation
Caches Gemini AI batch responses so repeat reconciliation runs cost zero API tokens.
"""

import sqlite3
import json
import os
import hashlib
from typing import Optional, Dict, Any, List

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "gst_reconcile.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates a connection with row factory enabled."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the SQLite cache table if not already created."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                cache_key TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_cache_key ON ai_cache (cache_key)
        """)
        conn.commit()


def compute_cache_key(query_data: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    """
    Computes a deterministic SHA-256 hash from the query row and its candidate rows.
    Only relevant fields are included so formatting differences don't create false misses.
    """
    payload = {
        "query": {
            "gstin": query_data.get("gstin", ""),
            "inv_num": query_data.get("normalized_invoice_number", query_data.get("invoice_number", "")),
            "amount": round(float(query_data.get("total_amount", 0.0) or 0.0), 2),
            "tax": round(float(query_data.get("total_tax", 0.0) or 0.0), 2),
            "name": query_data.get("clean_name", query_data.get("supplier_name", "")),
            "date": str(query_data.get("invoice_date", ""))
        },
        "candidates": [
            {
                "id": c.get("id"),
                "gstin": c.get("gstin", ""),
                "inv_num": c.get("normalized_invoice_number", c.get("invoice_number", "")),
                "amount": round(float(c.get("total_amount", 0.0) or 0.0), 2),
                "tax": round(float(c.get("total_tax", 0.0) or 0.0), 2),
                "name": c.get("clean_name", c.get("supplier_name", "")),
                "date": str(c.get("invoice_date", ""))
            }
            for c in candidates
        ]
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_cached_match(cache_key: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves a cached AI decision by cache key, or None if not cached."""
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT result_json FROM ai_cache WHERE cache_key = ?", (cache_key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["result_json"])
    except Exception as e:
        # DB read failure should never crash the app
        print(f"[CACHE] Error reading cache: {e}")
    return None


def set_cached_match(cache_key: str, result: Dict[str, Any], model_name: str = "", db_path: str = DEFAULT_DB_PATH) -> None:
    """Saves an AI decision into the cache."""
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ai_cache (cache_key, result_json, model_used)
                VALUES (?, ?, ?)
            """, (cache_key, json.dumps(result), model_name))
            conn.commit()
    except Exception as e:
        print(f"[CACHE] Error writing to cache: {e}")


# Initialize DB on module import
init_db()
