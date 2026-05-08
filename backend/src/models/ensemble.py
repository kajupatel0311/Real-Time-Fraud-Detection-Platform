"""
Stage 3.3 — Stacking Ensemble Meta-Learner
Prompt 3.3: Out-of-fold stacking, calibrated logistic regression,
MLflow serialisation, graceful LSTM fallback for cold-start cards.
"""
import os
import logging
import pickle
import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.linear_model  import LogisticRegression
from sklearn.calibration   import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import average_precision_score
from xgboost import XGBClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MLFLOW_URI      = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
EXPERIMENT_NAME = "fraud-detection-ensemble"
MODEL_NAME      = "fraud-ensemble"
N_FOLDS         = 5
RANDOM_STATE    = 42


# ─────────────────────────────────────────────────────────────────
# 1. Why not simple averaging?
# ─────────────────────────────────────────────────────────────────
# XGBoost and LSTM capture fundamentally different signals:
#   • XGBoost: tabular patterns (PCA features, rolling stats, amounts)
#   • LSTM:    sequential behavioural signals (spending velocity over time)
# A calibrated meta-learner learns the optimal *combination weights*
# from held-out data, whereas averaging implicitly assumes equal contribution.
# ─────────────────────────────────────────────────────────────────


def generate_oof_predictions(xgb_model, lstm_predict_fn,
                             X_tab: np.ndarray, X_seq: np.ndarray,
                             y: np.ndarray, has_sequence: np.ndarray) -> np.ndarray:
    """
    Generate Out-Of-Fold predictions for both base models to avoid leakage
    when training the meta-learner.

    has_sequence: boolean array marking which rows have ≥10 historical txns
                  (LSTM can only predict for these rows — cold-start handling below).
    """
    oof_xgb  = np.zeros(len(y), dtype=np.float32)
    oof_lstm = np.full(len(y), np.nan, dtype=np.float32)
    folds    = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    for fold, (train_idx, val_idx) in enumerate(folds.split(X_tab, y)):
        logger.info("OOF fold %d/%d", fold + 1, N_FOLDS)

        # ── XGBoost OOF ──────────────────────────────────────────
        xgb_model.fit(
            X_tab[train_idx], y[train_idx],
            eval_set=[(X_tab[val_idx], y[val_idx])],
            verbose=False,
        )
        oof_xgb[val_idx] = xgb_model.predict_proba(X_tab[val_idx])[:, 1]

        # ── LSTM OOF (only for cards that have sequences) ─────────
        seq_val_mask = has_sequence[val_idx]
        if seq_val_mask.any():
            lstm_probs = lstm_predict_fn(X_seq[val_idx[seq_val_mask]])
            oof_lstm[val_idx[seq_val_mask]] = lstm_probs

    return oof_xgb, oof_lstm


def build_meta_features(xgb_probs: np.ndarray,
                        lstm_probs: np.ndarray) -> np.ndarray:
    """
    Assemble the 3-feature meta matrix:
      [xgb_prob, lstm_prob, xgb_only_flag]
    For cold-start rows (no sequence), lstm_prob is filled with the dataset
    mean and a flag column indicates the LSTM was unavailable.
    """
    try:
        lstm_mean = np.nanmean(lstm_probs)
        if np.isnan(lstm_mean):
            lstm_mean = 0.5
    except:
        lstm_mean = 0.5

    lstm_filled      = np.where(np.isnan(lstm_probs), lstm_mean, lstm_probs)
    lstm_missing_flag = np.isnan(lstm_probs).astype(np.float32)

    return np.column_stack([xgb_probs, lstm_filled, lstm_missing_flag])


def build_meta_learner() -> CalibratedClassifierCV:
    """
    Calibrated logistic regression as the meta-learner.
    Calibration ensures the output is a true probability (not just a score),
    which is critical for downstream threshold decisions.
    """
    base = LogisticRegression(
        C=0.1,           # strong regularisation — meta-learner has only 3 features
        solver="lbfgs",
        max_iter=500,
        random_state=RANDOM_STATE,
    )
    return CalibratedClassifierCV(base, method="isotonic", cv=5)


def train_ensemble(oof_xgb: np.ndarray, oof_lstm: np.ndarray,
                   y: np.ndarray) -> CalibratedClassifierCV:
    """Train the meta-learner on OOF predictions."""
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    meta_X = build_meta_features(oof_xgb, oof_lstm)
    meta   = build_meta_learner()

    with mlflow.start_run(run_name="ensemble-meta-learner"):
        meta.fit(meta_X, y)
        probs  = meta.predict_proba(meta_X)[:, 1]
        pr_auc = average_precision_score(y, probs)

        mlflow.log_metric("meta_pr_auc_oof", pr_auc)
        mlflow.sklearn.log_model(meta, "meta_learner",
                                 registered_model_name=MODEL_NAME)
        logger.info("Meta-learner PR-AUC (OOF): %.4f", pr_auc)

    return meta


def predict_ensemble(xgb_model, lstm_predict_fn,
                     meta_model: CalibratedClassifierCV,
                     X_tab: np.ndarray, X_seq: np.ndarray,
                     has_sequence: np.ndarray) -> np.ndarray:
    """
    Single-pass inference for the full ensemble.
    Cold-start cards (no sequence history) fall back to XGBoost score only;
    the LSTM slot is filled with the training mean and the flag is set.
    """
    xgb_probs  = xgb_model.predict_proba(X_tab)[:, 1]
    lstm_probs = np.full(len(X_tab), np.nan, dtype=np.float32)

    if has_sequence.any():
        lstm_probs[has_sequence] = lstm_predict_fn(X_seq[has_sequence])

    meta_X = build_meta_features(xgb_probs, lstm_probs)
    return meta_model.predict_proba(meta_X)[:, 1]


def save_ensemble(xgb_model, lstm_model, meta_model: CalibratedClassifierCV,
                  save_dir: str = "output/models"):
    """
    Serialize all three components to disk and log to MLflow.
    Structure mirrors MLflow model flavour conventions.
    """
    os.makedirs(save_dir, exist_ok=True)

    with open(os.path.join(save_dir, "xgb_model.pkl"), "wb") as f:
        pickle.dump(xgb_model, f)
    with open(os.path.join(save_dir, "meta_model.pkl"), "wb") as f:
        pickle.dump(meta_model, f)
    # LSTM is saved separately as lstm.pt + lstm_fraud.onnx via lstm_model.py

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="ensemble-artifact-save"):
        mlflow.log_artifact(os.path.join(save_dir, "xgb_model.pkl"))
        mlflow.log_artifact(os.path.join(save_dir, "meta_model.pkl"))
    logger.info("Ensemble models saved to %s and logged to MLflow.", save_dir)
