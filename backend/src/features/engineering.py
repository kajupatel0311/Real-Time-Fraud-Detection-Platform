import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def encode_type(df):
    """One-hot encode the transaction 'type' column."""
    logger.info("Encoding transaction types...")
    type_dummies = pd.get_dummies(df["type"], prefix="type")
    df = pd.concat([df, type_dummies], axis=1)
    return df

def user_behavioral_features(df):
    """
    User-level behavioral features.
    Optimized burst_count using diff() to avoid slow rolling transform.
    """
    logger.info("Calculating user-level behavioral features...")
    
    # Sorting is critical for diff/shift
    df = df.sort_values(["nameOrig", "step"])
    user_group = df.groupby("nameOrig")
    
    df["txn_count"] = user_group.cumcount() + 1
    df["amt_sum"] = user_group["amount"].cumsum()
    df["velocity"] = df["amount"] / (df["oldbalanceOrg"] + 1)
    df["time_gap"] = user_group["step"].diff().fillna(0)
    
    # burst_count: transactions in last 3 steps
    # We use diff(2) to check the time gap between current and 2nd previous transaction.
    # If this gap is <= 3, then there are at least 3 transactions in a 3-step window.
    # We'll use this as a proxy 'is_burst' feature (0 or 1) or 'burst_index'.
    logger.info("Calculating burst features (optimized)...")
    df["step_diff_2"] = user_group["step"].diff(2).fillna(999)
    df["burst_count"] = (df["step_diff_2"] <= 3).astype(int) + 2 # Minimal 2 if it's a burst
    df.drop(columns=["step_diff_2"], inplace=True)
    
    return df

def merchant_behavioral_features(df):
    logger.info("Calculating merchant-level features...")
    is_first = ~df.duplicated(subset=["nameOrig", "nameDest"])
    df["unique_merchants"] = is_first.groupby(df["nameOrig"]).cumsum()
    df["merchant_frequency"] = df.groupby("nameDest").cumcount() + 1
    return df

def merchant_risk_score(df, train_ref=None, alpha=10):
    logger.info("Calculating merchant risk score...")
    if train_ref is not None:
        merchant_stats = train_ref.groupby("nameDest")["isFraud"].agg(["sum", "count"])
        global_mean = train_ref["isFraud"].mean()
        df = df.merge(merchant_stats, on="nameDest", how="left")
        df["sum"] = df["sum"].fillna(0)
        df["count"] = df["count"].fillna(0)
        df["merchant_risk"] = (df["sum"] + alpha * global_mean) / (df["count"] + alpha)
        df.drop(columns=["sum", "count"], inplace=True)
    else:
        global_mean = df["isFraud"].mean()
        df["_shifted_isFraud"] = df.groupby("nameDest")["isFraud"].shift(1).fillna(0)
        shifted_sum = df.groupby("nameDest")["_shifted_isFraud"].cumsum()
        shifted_count = df.groupby("nameDest").cumcount()
        df["merchant_risk"] = (shifted_sum + alpha * global_mean) / (shifted_count + alpha)
        df.drop(columns=["_shifted_isFraud"], inplace=True)
    df["merchant_risk"] = df["merchant_risk"].fillna(0)
    return df

def apply_all_features(df, train_ref=None):
    df = df.copy()
    df = encode_type(df)
    df = user_behavioral_features(df)
    df = merchant_behavioral_features(df)
    df = merchant_risk_score(df, train_ref=train_ref)
    df = df.fillna(0)
    return df
