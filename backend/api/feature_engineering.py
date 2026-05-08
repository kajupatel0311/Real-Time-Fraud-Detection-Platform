import logging
from datetime import datetime
from collections import deque
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class FeatureStore:
    """In-memory behavioral state management and feature extraction."""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.user_history: Dict[str, deque] = {}
        self.merchant_history: Dict[str, deque] = {}

    def extract_features(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates behavioral and contextual features for a given transaction."""
        amount = float(txn.get("amount", 0))
        user_id = txn.get("nameOrig", "UNKNOWN")
        merchant_id = txn.get("nameDest", "UNKNOWN")
        
        # 1. Behavioral Burst Detection
        history = self.user_history.get(user_id, deque())
        burst_count = len(history)
        
        # 2. Risk Context
        is_night = 1 if 0 <= datetime.now().hour <= 5 else 0
        
        # 3. Entity Risk Profiling
        merchant_txns = self.merchant_history.get(merchant_id, deque())
        merchant_risk = 0.0
        if merchant_txns:
            fraud_count = sum(1 for t in merchant_txns if t.get("is_fraud"))
            merchant_risk = fraud_count / len(merchant_txns)

        # Baseline features for XGBoost compatibility
        return {
            "amount": amount,
            "oldbalanceOrg": float(txn.get("oldbalanceOrg", 0)),
            "newbalanceOrig": float(txn.get("newbalanceOrig", 0)),
            "oldbalanceDest": float(txn.get("oldbalanceDest", 0)),
            "newbalanceDest": float(txn.get("newbalanceDest", 0)),
            "type_TRANSFER": 1 if txn.get("type") == "TRANSFER" else 0,
            "type_CASH_OUT": 1 if txn.get("type") == "CASH_OUT" else 0,
            "burst": burst_count,
            "is_night": is_night,
            "merchant_risk": merchant_risk,
            "historical_risk_score": self._calculate_user_risk(user_id)
        }

    def update_memory(self, txn: Dict[str, Any], is_fraud: bool, prob: float):
        """Updates internal state with the result of an analysis."""
        user_id = txn.get("nameOrig", "UNKNOWN")
        merchant_id = txn.get("nameDest", "UNKNOWN")
        
        # Update user audit log
        if user_id not in self.user_history:
            self.user_history[user_id] = deque(maxlen=self.history_size)
        self.user_history[user_id].append({"is_fraud": is_fraud, "prob": prob, "ts": datetime.now()})
        
        # Update merchant audit log
        if merchant_id not in self.merchant_history:
            self.merchant_history[merchant_id] = deque(maxlen=self.history_size)
        self.merchant_history[merchant_id].append({"is_fraud": is_fraud, "prob": prob})

    def _calculate_user_risk(self, user_id: str) -> float:
        """Internal helper for user historical risk average."""
        history = self.user_history.get(user_id, deque())
        if not history:
            return 0.0
        return sum(t["prob"] for t in history) / len(history)

feature_store = FeatureStore()
