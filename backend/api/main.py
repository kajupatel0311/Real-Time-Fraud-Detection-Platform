from __future__ import annotations
import os
import time
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    TransactionRequest, 
    PredictionResponse, 
    AlertItem, 
    HealthResponse, 
    ChatRequest, 
    ChatResponse
)
from .model_loader import model_loader
from .feature_engineering import feature_store
from .fraud_bot import fraud_bot
from .nlp_parser import parse_transaction_message
from .database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

app_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing FraudSentinel services...")
    model_loader.load()
    yield
    logger.info("Shutting down FraudSentinel services...")

app = FastAPI(
    title="FraudSentinel API",
    description="Production-grade real-time fraud detection engine.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and template configuration
# Asset paths are resolved relative to the web/ directory
current_dir = os.path.dirname(__file__)
web_dir = os.path.abspath(os.path.join(current_dir, "../../web"))

app.mount("/static", StaticFiles(directory=os.path.join(web_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(web_dir, "templates"))

@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/predict", response_model=PredictionResponse, tags=["Analysis"])
async def predict_transaction(request: TransactionRequest):
    if not model_loader.is_loaded:
        raise HTTPException(status_code=503, detail="Risk model not initialized.")

    txn_data = request.model_dump()
    features = feature_store.compute_features(txn_data)
    ml_probability = model_loader.predict_proba(features)
    
    result = fraud_bot.analyze(txn_data, features, ml_probability)
    
    feature_store.update_memory(txn_data, is_fraud=(result.risk_level == "High"), prob=ml_probability)
    db.store_record(result.model_dump(), txn_data, "API_DIRECT")

    logger.info("Processed transaction %s: risk=%s, score=%.4f", 
                result.transaction_id, result.risk_level, result.final_risk_score)
    return result

@app.post("/chat_predict", response_model=ChatResponse, tags=["Analysis"])
async def analyze_chat_message(request: ChatRequest):
    if not model_loader.is_loaded:
        raise HTTPException(status_code=503, detail="Risk model not initialized.")

    parsed_txn = parse_transaction_message(request.message)
    features = feature_store.compute_features(parsed_txn)
    ml_probability = model_loader.predict_proba(features)
    
    prediction = fraud_bot.analyze(parsed_txn, features, ml_probability)

    feature_store.update_memory(parsed_txn, is_fraud=(prediction.risk_level == "High"), prob=ml_probability)
    db.store_record(prediction.model_dump(), parsed_txn, request.message)

    # Human-centric risk communication
    if prediction.risk_level == "High":
        msg = (
            "This transaction shows high-risk indicators and has been flagged for manual review. "
            f"Risk score: {int(prediction.final_risk_score * 100)}%. "
            f"Action: {prediction.action}."
        )
    elif prediction.risk_level == "Medium":
        msg = (
            "Unusual activity detected. Secondary verification is recommended. "
            f"Action: {prediction.action}."
        )
    else:
        msg = "Transaction verified against baseline patterns. No immediate risk identified."

    return ChatResponse(
        message=msg,
        prediction=prediction,
        parsed_data=parsed_txn
    )

@app.get("/history", response_model=List[PredictionResponse], tags=["Audit"])
async def get_transaction_history(limit: int = 50):
    records = db.fetch_history(limit=limit)
    return [PredictionResponse(**r) for r in records]

@app.get("/alerts", response_model=List[AlertItem], tags=["Audit"])
async def get_risk_alerts(limit: int = 50):
    alerts = db.fetch_alerts(limit=min(limit, 50))
    return [AlertItem(**a) for a in alerts]

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def system_health():
    return HealthResponse(
        status="healthy" if model_loader.is_loaded else "degraded",
        model_loaded=model_loader.is_loaded,
        model_type=model_loader.model_type,
        uptime_seconds=round(time.time() - app_start_time, 1),
        total_predictions=fraud_bot.total_processed,
        total_alerts=len(db.fetch_alerts(100)),
    )
