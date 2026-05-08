import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

from backend.config import DATABASE_URL

logger = logging.getLogger(__name__)

class Database:
    """Persistent storage handler for transaction audit trails and alerts."""
    
    def __init__(self):
        self._initialize_schema()

    def _get_connection(self):
        return sqlite3.connect(DATABASE_URL)

    def _initialize_schema(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    transaction_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    input_text TEXT,
                    amount REAL,
                    type TEXT,
                    ml_probability REAL,
                    behavioral_score REAL,
                    final_risk_score REAL,
                    risk_level TEXT,
                    action TEXT,
                    reasons TEXT,
                    indicators TEXT,
                    pattern_summary TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    transaction_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    amount REAL,
                    risk_level TEXT,
                    reasons TEXT,
                    FOREIGN KEY(transaction_id) REFERENCES records(transaction_id)
                )
            """)

    def store_record(self, prediction: Dict[str, Any], raw_data: Dict[str, Any], source: str):
        """Persists an analysis result and logs critical alerts if necessary."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO records (
                        transaction_id, timestamp, input_text, amount, type, 
                        ml_probability, behavioral_score, final_risk_score, 
                        risk_level, action, reasons, indicators, pattern_summary, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prediction["transaction_id"],
                    prediction["timestamp"],
                    source,
                    prediction.get("amount", 0.0),
                    raw_data.get("type", "UNKNOWN"),
                    prediction.get("ml_probability", 0.0),
                    prediction.get("behavioral_score", 0.0),
                    prediction.get("final_risk_score", 0.0),
                    prediction["risk_level"],
                    prediction["action"],
                    json.dumps(prediction["reasons"]),
                    json.dumps(prediction["indicators"]),
                    prediction.get("pattern_summary", ""),
                    json.dumps(raw_data)
                ))
                
                if prediction["risk_level"] == "High":
                    conn.execute("""
                        INSERT INTO alerts (transaction_id, timestamp, amount, risk_level, reasons)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        prediction["transaction_id"],
                        prediction["timestamp"],
                        prediction.get("amount", 0.0),
                        prediction["risk_level"],
                        json.dumps(prediction["reasons"])
                    ))
        except Exception as e:
            logger.error("Failed to persist transaction record: %s", e)

    def fetch_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves historical analysis records."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM records ORDER BY timestamp DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    item = dict(row)
                    item["reasons"] = json.loads(row["reasons"])
                    item["indicators"] = json.loads(row["indicators"])
                    item["fraud_probability"] = row["final_risk_score"]
                    item["confidence_score"] = int(row["final_risk_score"] * 100)
                    results.append(item)
                return results
        except Exception as e:
            logger.error("Error fetching history: %s", e)
            return []

    def fetch_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves active high-risk alerts with joined metadata."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                query = """
                    SELECT a.*, r.ml_probability, r.final_risk_score, 
                           r.action, r.reasons, r.indicators, r.metadata
                    FROM alerts a
                    JOIN records r ON a.transaction_id = r.transaction_id
                    ORDER BY a.timestamp DESC LIMIT ?
                """
                cursor = conn.execute(query, (limit,))
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    meta = json.loads(row["metadata"])
                    results.append({
                        "transaction_id": row["transaction_id"],
                        "timestamp": row["timestamp"],
                        "amount": row["amount"],
                        "risk_level": row["risk_level"],
                        "fraud_probability": row["final_risk_score"],
                        "action": row["action"],
                        "reasons": json.loads(row["reasons"]),
                        "indicators": json.loads(row["indicators"]),
                        "nameOrig": meta.get("nameOrig", "UNKNOWN"),
                        "nameDest": meta.get("nameDest", "UNKNOWN")
                    })
                return results
        except Exception as e:
            logger.error("Error fetching alerts: %s", e)
            return []

db = Database()
