"""
Data Drift & Model Monitoring
Monitors feature distribution shifts and triggers retraining.
"""
import os
import json
import logging
import sqlite3
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AIRFLOW_BASE_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_DAG_ID   = "fraud_model_retraining"
PSI_THRESHOLD    = 0.25
MONITORED_FEATS  = ["amount", "velocity", "merchant_risk"]


def generate_evidently_report(reference: pd.DataFrame, current: pd.DataFrame,
                              output_dir: str = "output/monitoring") -> str:
    """
    Generate a full Evidently report covering:
      - Data Drift (feature distribution shift)
      - Data Quality (nulls, out-of-range values)
      - Target Drift (fraud rate change)
    Returns path to the saved HTML report.
    """
    try:
        from evidently.report import Report
        from evidently.metric_preset import (
            DataDriftPreset, DataQualityPreset, TargetDriftPreset
        )
    except ImportError:
        logger.error("evidently not installed. Run: pip install evidently>=0.4")
        return ""

    os.makedirs(output_dir, exist_ok=True)
    report = Report(metrics=[
        DataDriftPreset(),
        DataQualityPreset(),
        TargetDriftPreset(),
    ])
    report.run(reference_data=reference, current_data=current)

    out_path = os.path.join(output_dir, f"drift_report_{datetime.utcnow().date()}.html")
    report.save_html(out_path)
    logger.info("Evidently report saved to %s", out_path)
    return out_path

def compute_psi(expected: np.ndarray, actual: np.ndarray,
                buckets: int = 10) -> float:
    """
    Population Stability Index (PSI).
    Formula: PSI = Σ (Actual% - Expected%) × ln(Actual% / Expected%)

    Interpretation:
      PSI < 0.1  → No significant change  (green)
      PSI < 0.2  → Moderate shift         (amber)
      PSI >= 0.2 → Large shift — retrain! (red)
    """
    # Build consistent bin edges from both distributions
    breakpoints = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    breakpoints[0]  = -np.inf
    breakpoints[-1] =  np.inf

    def _bucket_pcts(arr):
        counts = np.histogram(arr, bins=breakpoints)[0]
        pcts   = counts / len(arr)
        # Replace zero with a small epsilon to avoid log(0)
        return np.where(pcts == 0, 1e-8, pcts)

    expected_pcts = _bucket_pcts(expected)
    actual_pcts   = _bucket_pcts(actual)

    psi = np.sum((actual_pcts - expected_pcts) * np.log(actual_pcts / expected_pcts))
    return float(psi)


def compute_psi_all_features(reference: pd.DataFrame,
                              current: pd.DataFrame,
                              features: list = MONITORED_FEATS) -> dict:
    psi_scores = {}
    for feat in features:
        if feat not in reference.columns or feat not in current.columns:
            logger.warning("Feature '%s' missing from data — skipping PSI.", feat)
            continue
        ref_vals = reference[feat].dropna().values
        cur_vals = current[feat].dropna().values
        psi = compute_psi(ref_vals, cur_vals)
        psi_scores[feat] = round(psi, 6)
        logger.info("PSI[%s] = %.4f", feat, psi)
    return psi_scores

def trigger_retraining_dag(psi_scores: dict,
                           dag_id: str = AIRFLOW_DAG_ID) -> bool:
    """
    POST to Airflow REST API to trigger the retraining DAG,
    passing PSI scores as the conf payload for the DAG to use.
    """
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}/dagRuns"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {os.getenv('AIRFLOW_AUTH_TOKEN', 'YWRtaW46YWRtaW4=')}",
    }
    payload = {
        "dag_run_id": f"drift_trigger_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "conf": {
            "psi_scores": psi_scores,
            "trigger_reason": "PSI exceeded threshold",
            "threshold": PSI_THRESHOLD,
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Retraining DAG triggered successfully: %s", resp.json().get("dag_run_id"))
        return True
    except requests.RequestException as exc:
        logger.error("Failed to trigger Airflow DAG: %s", exc)
        return False

def _psi_to_status(psi: float) -> tuple:
    if psi < 0.1:
        return "green",  "#00e5a0", "STABLE"
    elif psi < PSI_THRESHOLD:
        return "amber",  "#ffd166", "WARNING"
    else:
        return "red",    "#ff6b6b", "DRIFT DETECTED"


def generate_drift_dashboard(psi_scores: dict,
                             output_path: str = "output/monitoring/drift_dashboard.html"):
    """
    Generate a self-contained HTML traffic-light dashboard showing drift status
    per feature with green/amber/red indicators.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for feat, psi in psi_scores.items():
        _, color, label = _psi_to_status(psi)
        rows += f"""
        <tr>
          <td>{feat}</td>
          <td style="font-family:monospace">{psi:.4f}</td>
          <td><span style="
              background:{color}22; color:{color};
              border:1px solid {color}55;
              padding:4px 14px; border-radius:20px;
              font-family:monospace; font-size:12px; font-weight:600;">
            {label}
          </span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fraud Model Drift Monitor</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
  <style>
    :root {{--bg:#0a0a0f;--card:#13131a;--border:rgba(255,255,255,0.07);
           --accent:#00e5a0;--text:#e8e8f0;--muted:#888899;}}
    * {{margin:0;padding:0;box-sizing:border-box;}}
    body {{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;
           min-height:100vh;padding:40px 60px;}}
    h1 {{font-size:28px;font-weight:700;color:#fff;margin-bottom:6px;}}
    .subtitle {{color:var(--muted);font-size:14px;margin-bottom:32px;}}
    .card {{background:var(--card);border:1px solid var(--border);
            border-radius:12px;overflow:hidden;}}
    table {{width:100%;border-collapse:collapse;}}
    th {{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);
         text-transform:uppercase;letter-spacing:.06em;padding:14px 20px;
         border-bottom:1px solid var(--border);text-align:left;}}
    td {{padding:16px 20px;border-bottom:1px solid rgba(255,255,255,.04);
         font-size:14px;}}
    tr:last-child td {{border-bottom:none;}}
    .footer {{margin-top:24px;color:var(--muted);font-size:12px;
              font-family:'IBM Plex Mono',monospace;}}
    .threshold-note {{background:rgba(0,229,160,.05);border:1px solid
              rgba(0,229,160,.2);border-radius:8px;padding:14px 20px;
              margin-bottom:24px;font-size:13px;color:#b0f0dc;}}
  </style>
</head>
<body>
  <h1>Fraud Model — Drift Monitor</h1>
  <div class="subtitle">Generated: {ts} &nbsp;|&nbsp; PSI threshold for retraining: {PSI_THRESHOLD}</div>
  <div class="threshold-note">
    PSI &lt; 0.10 → Stable &nbsp;|&nbsp; 0.10 – 0.20 → Warning &nbsp;|&nbsp;
    &gt; 0.20 → Drift Detected — Airflow retraining DAG triggered automatically.
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>Feature</th><th>PSI Score</th><th>Status</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div class="footer">Powered by Evidently AI + custom PSI engine</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Drift dashboard saved → %s", output_path)
    return output_path

def run_daily_drift_check(reference_path: str, current_path: str):
    """
    Orchestrates the full daily drift check:
      1. Load reference + current datasets
      2. Compute PSI for all monitored features
      3. Generate HTML dashboard
      4. Trigger Airflow retraining if any PSI > threshold
    Scheduled via Airflow / cron at 01:00 UTC daily.
    """
    logger.info("=== Daily Drift Check started at %s ===", datetime.utcnow().isoformat())

    reference = pd.read_parquet(reference_path) if reference_path.endswith(".parquet") \
                else pd.read_csv(reference_path)
    current   = pd.read_parquet(current_path)   if current_path.endswith(".parquet") \
                else pd.read_csv(current_path)

    psi_scores = compute_psi_all_features(reference, current)

    generate_drift_dashboard(psi_scores)

    # Try to generate Evidently report too (optional — requires evidently package)
    try:
        generate_evidently_report(reference, current)
    except Exception as exc:
        logger.warning("Evidently report skipped: %s", exc)

    # Trigger retraining if any feature exceeds threshold
    max_psi = max(psi_scores.values(), default=0.0)
    if max_psi >= PSI_THRESHOLD:
        logger.warning("PSI threshold breached (max=%.4f). Triggering retraining DAG.", max_psi)
        trigger_retraining_dag(psi_scores)
    else:
        logger.info("All PSI scores below threshold. No retraining needed.")

    logger.info("=== Daily Drift Check complete ===")
    return psi_scores
