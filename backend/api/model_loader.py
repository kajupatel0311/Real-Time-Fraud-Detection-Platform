"""
Utilities for loading and interfacing with the serialized risk model.
"""
import os
import logging
import joblib
import numpy as np
from config import MODEL_PATH

logger = logging.getLogger(__name__)

class ModelLoader:
    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.is_loaded = False
        self.model_type = "None"

    def load(self):
        if not os.path.exists(self.model_path):
            logger.warning(f"Model file not found at {self.model_path}. Please run training script.")
            return

        try:
            self.model = joblib.load(self.model_path)
            self.is_loaded = True
            self.model_type = type(self.model).__name__
            logger.info(f"Model loaded successfully: {self.model_type}")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")

    def predict_proba(self, features: dict) -> float:
        """
        Returns the probability of fraud for a given feature set.
        """
        if not self.is_loaded:
            return 0.0

        try:
            # Map features to the required input order
            feature_order = [
                "amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", 
                "newbalanceDest", "step", "type_encoded", "txn_count", 
                "amt_sum", "velocity", "burst", "time_gap", "merchant_risk", 
                "balance_diff_orig", "balance_diff_dest", "balance_mismatch",
                "hour_of_day", "is_night"
            ]
            
            x = np.array([[features.get(f, 0.0) for f in feature_order]], dtype=np.float32)
            
            # Use predict_proba for classification models
            if hasattr(self.model, "predict_proba"):
                return float(self.model.predict_proba(x)[0, 1])
            
            return float(self.model.predict(x)[0])
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return 0.0

model_loader = ModelLoader()
