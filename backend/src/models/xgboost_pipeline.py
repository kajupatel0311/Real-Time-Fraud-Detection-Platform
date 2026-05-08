"""
Stage 3.1 — XGBoost Pipeline with Class Imbalance Handling + MLflow Tracking
Updated: Realistic threshold optimization for Recall 0.90-0.95.
"""
import os
import logging
import json
import numpy as np
import pandas as pd
import mlflow
import mlflow.xgboost
from xgboost import XGBClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_recall_curve, average_precision_score,
    f1_score, classification_report, roc_auc_score
)
from sklearn.model_selection import StratifiedKFold
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MLFLOW_URI       = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
EXPERIMENT_NAME  = "fraud-detection-xgboost"
MODEL_NAME       = "fraud-xgboost"
RANDOM_STATE     = 42

def compute_scale_pos_weight(y: np.ndarray) -> float:
    neg = (y == 0).sum()
    pos = (y == 1).sum()
    return neg / pos if pos > 0 else 1.0

def build_pipeline(scale_pos_weight: float) -> ImbPipeline:
    xgb = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="aucpr",
        tree_method="hist",
        random_state=RANDOM_STATE,
        early_stopping_rounds=30,
        n_jobs=-1,
    )

    pipeline = ImbPipeline(steps=[
        ("scaler", StandardScaler()),
        ("smote",  SMOTE(sampling_strategy=0.1, random_state=RANDOM_STATE)),
        ("model",  xgb),
    ])
    return pipeline

def find_best_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Tune the decision threshold to prioritise Recall (0.90-0.95) and Precision (0.70-0.85).
    """
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    
    # Target: recall in [0.90, 0.95], precision as high as possible in [0.70, 0.85]
    # We'll filter for thresholds that meet the recall target
    mask = (recalls >= 0.90) & (recalls <= 0.95)
    
    if not mask.any():
        # Fallback to maximizing F1 if no threshold meets the targets
        logger.warning("No threshold found in target recall range [0.90, 0.95]. Falling back to F1.")
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-8)
        best_idx = np.argmax(f1_scores)
    else:
        # Find index in target range with highest precision within [0.70, 0.85]
        target_idxs = np.where(mask)[0]
        target_precisions = precisions[target_idxs]
        
        # Prefer precision in [0.70, 0.85]
        pref_mask = (target_precisions >= 0.70) & (target_precisions <= 0.85)
        if pref_mask.any():
            # Pick the one with highest precision in this range
            best_idx = target_idxs[pref_mask][np.argmax(target_precisions[pref_mask])]
        else:
            # Pick the one with highest precision regardless of range (among target recall)
            best_idx = target_idxs[np.argmax(target_precisions)]
            
    best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else 0.5
    
    # User constraint: Avoid thresholds > 0.8 unless justified
    if best_threshold > 0.8:
        logger.info("Caping threshold at 0.8 (user constraint) - original: %.4f", best_threshold)
        best_threshold = 0.8
        
    logger.info("Optimized threshold: %.4f (Recall=%.4f, Precision=%.4f)", 
                best_threshold, recalls[best_idx], precisions[best_idx])
    return float(best_threshold)

def evaluate(y_true, y_prob, threshold: float = 0.5) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    pr_auc = average_precision_score(y_true, y_prob)
    roc    = roc_auc_score(y_true, y_prob)
    f1     = f1_score(y_true, y_pred)
    recall = (y_true & y_pred).sum() / y_true.sum() if y_true.sum() > 0 else 0
    precision = (y_true & y_pred).sum() / y_pred.sum() if y_pred.sum() > 0 else 0
    
    logger.info("\n%s", classification_report(y_true, y_pred, target_names=["Legit","Fraud"]))
    return {
        "pr_auc": pr_auc, "roc_auc": roc, "f1_fraud": f1, 
        "threshold": threshold, "recall": recall, "precision": precision
    }

def train(X_train: pd.DataFrame, y_train: pd.Series,
          X_val: pd.DataFrame,   y_val: pd.Series) -> tuple:
    spw = compute_scale_pos_weight(y_train.values)
    pipeline = build_pipeline(spw)
    pipeline.fit(X_train, y_train, model__eval_set=[(X_val, y_val)], model__verbose=False)
    y_prob = pipeline.predict_proba(X_val)[:, 1]
    threshold = find_best_threshold(y_val.values, y_prob)
    metrics = evaluate(y_val.values, y_prob, threshold)
    return pipeline, metrics, threshold
