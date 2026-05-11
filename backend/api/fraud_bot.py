import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from .schemas import PredictionResponse

logger = logging.getLogger(__name__)

# Scoring Weights
ML_WEIGHT = 0.5
HEURISTIC_WEIGHT = 0.5

# Classification Thresholds
RISK_THRESHOLD_MEDIUM = 0.30
RISK_THRESHOLD_HIGH = 0.60

class FraudBot:
    """Decision engine combining ML predictions and behavioral heuristics."""
    
    def __init__(self):
        self.total_processed = 0

    def evaluate_heuristics(self, txn: dict, features: dict) -> float:
        """Computes a behavioral risk score (0.0 to 1.0) based on red-flag triggers."""
        score = 0.0
        amount = float(txn.get("amount", 0))
        txn_type = str(txn.get("type", "")).upper()
        
        # 1. Transaction magnitude flags
        if amount > 1000000: score += 0.8
        elif amount > 500000: score += 0.6
        elif amount > 100000: score += 0.4
        
        # 2. Channel risk (TRANSFER and CASH_OUT are common fraud paths)
        if txn_type in ("TRANSFER", "CASH_OUT"):
            score += 0.2
            
        # 3. Account depletion markers
        old_balance = float(txn.get("oldbalanceOrg", 0))
        if old_balance > 0 and (amount / old_balance) > 0.90:
            score += 0.6
            
        # 4. Velocity and frequency
        burst_count = features.get("burst", 0)
        if burst_count > 3: score += 0.5
        elif burst_count > 1: score += 0.3
            
        # 5. Entity-level risk
        if features.get("merchant_risk", 0) > 0.2: score += 0.4
        
        # 6. NLP/Intent triggers
        intents = txn.get("behavioral_intents", [])
        if "urgency" in intents: score += 0.4
        if "depletion" in intents: score += 0.3
        
        if features.get("is_night", 0) == 1: 
            score += 0.1

        return min(1.0, score)

    def generate_meta(self, txn: dict, features: dict, final_score: float) -> tuple[str, List[str], List[str]]:
        """Generates contextual explanations and risk indicators."""
        reasons = []
        indicators = []
        amount = float(txn.get("amount", 0))
        
        if amount > 500000: indicators.append("Extreme transaction volume")
        if txn.get("type") in ("TRANSFER", "CASH_OUT"): indicators.append("High-risk transfer channel")
        if features.get("burst", 0) > 3: indicators.append("Burst transaction pattern")
        if features.get("merchant_risk", 0) > 0.2: indicators.append("Suspicious merchant activity")
        if "urgency" in txn.get("behavioral_intents", []): indicators.append("Urgent social engineering markers")
        
        old_bal = float(txn.get("oldbalanceOrg", 0))
        if old_bal > 0 and (amount / old_bal) > 0.9: 
            indicators.append("Balance depletion pattern")

        if final_score < RISK_THRESHOLD_MEDIUM:
            summary = "Activity aligns with standard operational baselines."
            reasons = ["Verified sender profile", "Typical transaction volume"]
        elif final_score < RISK_THRESHOLD_HIGH:
            summary = "Unusual behavioral signature detected. Secondary review recommended."
            reasons = ["Atypical transfer volume", "Behavioral anomaly"]
        else:
            summary = "High-risk indicators identified. Transaction restricted for security review."
            reasons = ["Suspicious intent markers", "Multiple risk triggers"]
            if "Balance depletion pattern" in indicators: 
                reasons.append("Potential account takeover (ATO)")

        return summary, reasons[:3], indicators

    def analyze(self, txn: dict, features: dict, ml_prob: float) -> PredictionResponse:
        """Main entry point for transaction analysis."""
        from .model_loader import model_loader
        
        self.total_processed += 1
        amount = float(txn.get("amount", 0))
        
        h_score = self.evaluate_heuristics(txn, features)
        
        if model_loader.is_loaded:
            final_score = (ML_WEIGHT * ml_prob) + (HEURISTIC_WEIGHT * h_score)
            scoring_mode = "Hybrid"
        else:
            final_score = h_score  # 100% heuristic weight
            scoring_mode = "Heuristic-Only"
            
        if final_score >= RISK_THRESHOLD_HIGH:
            risk_level = "High"
            action = "Restrict transaction"
        elif final_score >= RISK_THRESHOLD_MEDIUM:
            risk_level = "Medium"
            action = "Verify identity"
        else:
            risk_level = "Low"
            action = "Allow"

        summary, reasons, indicators = self.generate_meta(txn, features, final_score)
        
        return PredictionResponse(
            transaction_id=str(uuid.uuid4())[:12].upper(),
            amount=amount,
            ml_probability=round(ml_prob, 4),
            behavioral_score=round(h_score, 4),
            final_risk_score=round(final_score, 4),
            fraud_probability=round(final_score, 4),
            confidence_score=int(final_score * 100),
            scoring_mode=scoring_mode,
            risk_level=risk_level,
            action=action,
            reasons=reasons,
            indicators=indicators,
            pattern_summary=summary,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            features={k: round(v, 4) if isinstance(v, float) else v for k, v in features.items()}
        )

fraud_bot = FraudBot()
