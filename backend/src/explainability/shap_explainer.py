"""
Stage 5.1 — SHAP Explainability Service
Updated: Clearer human-readable reasons, removed vague 'risk factor' phrasing.
"""
import os
import sqlite3
import json
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Human-readable reason codes ──────────────────────────────────────────────
REASON_CODES = {
    "txn_count":           "High transaction frequency for this user increases fraud risk",
    "amt_sum":             "Unusually high cumulative spending by this user",
    "amt_mean":            "High average transaction amount detected",
    "velocity":            "High transaction amount relative to account balance",
    "time_gap":            "Recent transactions occurring in rapid succession",
    "unique_merchants":    "User interacting with a high number of distinct merchants",
    "merchant_frequency":  "Merchant has an unusually high volume of transactions",
    "merchant_risk":       "Merchant has a high historical fraud rate",
    "amount":              "High transaction amount increases fraud risk",
    "oldbalanceOrg":       "Originating account balance is unusual for this transaction",
    "is_burst":            "Transaction is part of a high-frequency burst",
}

DEFAULT_REASON = "Suspicious behavioral pattern detected"

def get_reason_code(feature_name: str, shap_value: float) -> str:
    """Map a feature + its SHAP value sign to a customer-friendly reason."""
    base = REASON_CODES.get(feature_name, DEFAULT_REASON)
    # We only show the reason if it's contributing POSITIVELY to the fraud prediction
    if shap_value > 0:
        return base
    return None

def init_audit_db(db_path: str = "output/audit/shap_audit.db"):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shap_audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id      TEXT    NOT NULL,
            ts          TEXT    NOT NULL,
            fraud_prob  REAL    NOT NULL,
            top_reasons TEXT    NOT NULL,
            shap_json   TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn

def log_to_audit(conn: sqlite3.Connection, txn_id: str, fraud_prob: float,
                 top_reasons: list, shap_dict: dict):
    from datetime import datetime
    conn.execute(
        "INSERT INTO shap_audit (txn_id, ts, fraud_prob, top_reasons, shap_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (txn_id, datetime.utcnow().isoformat(), fraud_prob,
         json.dumps(top_reasons), json.dumps(shap_dict))
    )
    conn.commit()

def explain_single_prediction(model, X_row: pd.DataFrame,
                               feature_names: list,
                               top_n: int = 5) -> dict:
    try:
        import shap
    except ImportError:
        logger.error("shap not installed.")
        return {}

    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X_row)

    if shap_vals.ndim == 2:
        shap_vals = shap_vals[0]

    shap_dict  = dict(zip(feature_names, shap_vals.tolist()))

    # Top N features by absolute SHAP value
    sorted_feats = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)
    
    top_reasons = []
    for feat, val in sorted_feats:
        reason = get_reason_code(feat, val)
        if reason:
            top_reasons.append({
                "feature": feat,
                "shap_value": val,
                "reason": reason
            })
            if len(top_reasons) >= top_n:
                break

    return {"shap_values": shap_dict, "top_reasons": top_reasons}

def plot_shap_summary(model, X: pd.DataFrame, feature_names: list,
                      output_path: str = "output/plots/shap_summary.png"):
    try:
        import shap
    except ImportError:
        return
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X)
    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_vals, X, feature_names=feature_names, show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    logger.info("SHAP summary plot saved to %s", output_path)
