import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

from pymongo import MongoClient

from backend.config import DATABASE_URL, IS_MONGODB, DATA_DIR

logger = logging.getLogger(__name__)

class BaseDatabase:
    """Abstract interface for database operations."""
    def store_record(self, prediction: Dict[str, Any], raw_data: Dict[str, Any], source: str):
        raise NotImplementedError

    def fetch_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        raise NotImplementedError


class SQLiteDatabase(BaseDatabase):
    """SQLite implementation for local fallback persistence."""
    
    def __init__(self, db_path: str):
        # Handle SQLite connection string prefixes safely
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_schema()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

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
            logger.error("SQLite - Failed to persist transaction record: %s", e)

    def fetch_history(self, limit: int = 50) -> List[Dict[str, Any]]:
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
            logger.error("SQLite - Error fetching history: %s", e)
            return []

    def fetch_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
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
            logger.error("SQLite - Error fetching alerts: %s", e)
            return []


class MongoDatabase(BaseDatabase):
    """MongoDB implementation for scalable production persistence."""
    
    def __init__(self, uri: str):
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.client.server_info() # Validate connection
            self.db = self.client.get_database("fraud_sentinel")
            self.transactions = self.db.get_collection("transactions")
            self.alerts = self.db.get_collection("alerts")
            self.behavioral_logs = self.db.get_collection("behavioral_logs")
            logger.info("Successfully connected to MongoDB.")
        except Exception as e:
            logger.error("MongoDB Connection Failed: %s", e)
            self.client = None

    def store_record(self, prediction: Dict[str, Any], raw_data: Dict[str, Any], source: str):
        if not self.client:
            return
            
        try:
            # Construct document
            doc = {
                "transaction_id": prediction["transaction_id"],
                "timestamp": prediction["timestamp"],
                "input_text": source,
                "amount": prediction.get("amount", 0.0),
                "type": raw_data.get("type", "UNKNOWN"),
                "ml_probability": prediction.get("ml_probability", 0.0),
                "behavioral_score": prediction.get("behavioral_score", 0.0),
                "final_risk_score": prediction.get("final_risk_score", 0.0),
                "risk_level": prediction["risk_level"],
                "action": prediction["action"],
                "reasons": prediction["reasons"],
                "indicators": prediction["indicators"],
                "pattern_summary": prediction.get("pattern_summary", ""),
                "metadata": raw_data
            }
            self.transactions.insert_one(doc)
            
            # Additional behavioral logging for the bot engine if needed
            self.behavioral_logs.insert_one({
                "transaction_id": prediction["transaction_id"],
                "timestamp": prediction["timestamp"],
                "entity": raw_data.get("nameOrig", "UNKNOWN"),
                "merchant": raw_data.get("nameDest", "UNKNOWN")
            })

            if prediction["risk_level"] == "High":
                alert_doc = {
                    "transaction_id": prediction["transaction_id"],
                    "timestamp": prediction["timestamp"],
                    "amount": prediction.get("amount", 0.0),
                    "risk_level": prediction["risk_level"],
                    "reasons": prediction["reasons"]
                }
                self.alerts.insert_one(alert_doc)
                
        except Exception as e:
            logger.error("MongoDB - Failed to persist transaction record: %s", e)

    def fetch_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.client:
            return []
            
        try:
            cursor = self.transactions.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            results = []
            for doc in cursor:
                # Add computed fields required by frontend that were virtual in SQLite
                doc["fraud_probability"] = doc.get("final_risk_score", 0.0)
                doc["confidence_score"] = int(doc.get("final_risk_score", 0.0) * 100)
                results.append(doc)
            return results
        except Exception as e:
            logger.error("MongoDB - Error fetching history: %s", e)
            return []

    def fetch_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.client:
            return []
            
        try:
            # We fetch alerts and join metadata from transactions
            alerts_cursor = self.alerts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            results = []
            
            for alert in alerts_cursor:
                txn = self.transactions.find_one({"transaction_id": alert["transaction_id"]}, {"_id": 0})
                if txn:
                    meta = txn.get("metadata", {})
                    alert["fraud_probability"] = txn.get("final_risk_score", 0.0)
                    alert["action"] = txn.get("action", "UNKNOWN")
                    alert["indicators"] = txn.get("indicators", [])
                    alert["nameOrig"] = meta.get("nameOrig", "UNKNOWN")
                    alert["nameDest"] = meta.get("nameDest", "UNKNOWN")
                else:
                    # Fallbacks if transaction document is inexplicably missing
                    alert["fraud_probability"] = 0.0
                    alert["action"] = "UNKNOWN"
                    alert["indicators"] = []
                    alert["nameOrig"] = "UNKNOWN"
                    alert["nameDest"] = "UNKNOWN"
                
                results.append(alert)
                
            return results
        except Exception as e:
            logger.error("MongoDB - Error fetching alerts: %s", e)
            return []

# Initialize singleton database instance based on environment configuration
if IS_MONGODB:
    db = MongoDatabase(DATABASE_URL)
else:
    db = SQLiteDatabase(DATABASE_URL)
