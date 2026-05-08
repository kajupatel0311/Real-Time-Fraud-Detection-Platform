import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Environment Variables with safe defaults
API_PORT = int(os.getenv("PORT", 8000))
API_HOST = os.getenv("HOST", "0.0.0.0")

# Database Configuration
# Fallback to local SQLite if not provided in environment
DATABASE_URL = os.getenv("DATABASE_URL", str(DATA_DIR / "transactions.db"))

# Model Configuration
MODEL_PATH = os.getenv("MODEL_PATH", str(MODELS_DIR / "fraud_model.joblib"))

# Ensure critical directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
