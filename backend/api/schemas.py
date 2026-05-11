"""
app/schemas.py — Pydantic v2 Request / Response Models
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ─────────────────────────────────────────────
# REQUEST
# ─────────────────────────────────────────────

class TransactionRequest(BaseModel):
    step: int = Field(..., description="Time step of the transaction (1 step = 1 hour)")
    amount: float = Field(..., gt=0, description="Transaction amount")
    type: str = Field(..., description="Transaction type: CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER")
    oldbalanceOrg: float = Field(default=0.0, description="Sender's balance before transaction")
    newbalanceOrig: float = Field(default=0.0, description="Sender's balance after transaction")
    oldbalanceDest: float = Field(default=0.0, description="Receiver's balance before transaction")
    newbalanceDest: float = Field(default=0.0, description="Receiver's balance after transaction")
    nameOrig: str = Field(default="C_UNKNOWN", description="Sender account ID")
    nameDest: str = Field(default="M_UNKNOWN", description="Receiver / merchant ID")

    model_config = {"json_schema_extra": {
        "example": {
            "step": 1,
            "amount": 181.0,
            "type": "PAYMENT",
            "oldbalanceOrg": 181.0,
            "newbalanceOrig": 0.0,
            "oldbalanceDest": 0.0,
            "newbalanceDest": 0.0,
            "nameOrig": "C1305486145",
            "nameDest": "M1979787155"
        }
    }}


# ─────────────────────────────────────────────
# RESPONSE
# ─────────────────────────────────────────────

class PredictionResponse(BaseModel):
    transaction_id: str
    amount: float = 0.0
    ml_probability: float
    behavioral_score: float
    final_risk_score: float
    fraud_probability: float  # Alias for final_risk_score for backward compatibility
    confidence_score: int     # Normalized 0-100 score
    scoring_mode: str = "Hybrid"
    risk_level: str
    action: str
    reasons: List[str]
    indicators: List[str]
    pattern_summary: str
    timestamp: str
    features: Optional[dict] = None


class AlertItem(BaseModel):
    transaction_id: str
    fraud_probability: float
    risk_level: str
    action: str
    reasons: List[str]
    indicators: List[str]
    amount: float
    nameOrig: str
    nameDest: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_type: str
    uptime_seconds: float
    total_predictions: int
    total_alerts: int
    version: str = "1.0.0"


# ─────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    prediction: PredictionResponse
    parsed_data: dict
