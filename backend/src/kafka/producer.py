"""
Stage 2.1 — Kafka Producer
Reads PaySim CSV (or any CSV with the right columns) and replays it into Kafka
at a configurable rate. Malformed rows are sent to the DLQ topic.
"""
import json
import time
import logging
import uuid
from datetime import datetime
import pandas as pd
from kafka import KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = "localhost:9092"
RAW_TOPIC         = "transactions.raw"
DLQ_TOPIC         = "transactions.dlq"

# Required columns (mapped from PaySim column names → canonical names)
PAYSIM_COL_MAP = {
    "nameOrig": "card_id",
    "amount":   "amount",
    "nameDest": "merchant_id",
    "isFraud":  "is_fraud",
    "step":     "step",
}


def build_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        # Partition by card_id so all txns for the same card stay ordered
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        # Tuning for throughput
        linger_ms=5,
        batch_size=65536,
        compression_type="lz4",
        acks=1,              # leader ack only for speed; use acks='all' for durability
    )


def send_to_dlq(producer: KafkaProducer, raw_row: dict, error: str):
    dlq_msg = {"original": raw_row, "error": error, "ts": datetime.utcnow().isoformat()}
    producer.send(DLQ_TOPIC, key="dlq", value=dlq_msg)
    logger.warning("Sent to DLQ: %s", error)


def validate_and_transform(row: dict) -> dict:
    """Validate a PaySim row and transform it to the canonical schema."""
    required = {"card_id", "amount", "merchant_id"}
    if not required.issubset(row.keys()):
        raise ValueError(f"Missing fields: {required - row.keys()}")
    if not isinstance(row["amount"], (int, float)) or row["amount"] < 0:
        raise ValueError(f"Invalid amount: {row['amount']}")

    return {
        "txn_id":       str(uuid.uuid4()),
        "card_id":      str(row["card_id"]),
        "amount":       float(row["amount"]),
        "merchant_id":  str(row["merchant_id"]),
        "timestamp":    int(time.time() * 1000),
        "currency":     "USD",
        "country_code": "US",
        "channel":      "WEB",
        "is_fraud":     bool(row.get("is_fraud", False)),
    }


def replay_csv(csv_path: str, tps: int = 1000):
    """
    Replay a CSV file into Kafka simulating real-time transactions.
    tps: target transactions-per-second (throttle via sleep).
    """
    logger.info("Loading dataset from %s", csv_path)
    df = pd.read_csv(csv_path).rename(columns=PAYSIM_COL_MAP)
    df = df[[c for c in PAYSIM_COL_MAP.values() if c in df.columns]]

    producer = build_producer()
    interval = 1.0 / tps  # seconds between sends
    sent = 0
    errors = 0

    logger.info("Starting replay at %d TPS → topic '%s'", tps, RAW_TOPIC)

    for _, row in df.iterrows():
        raw = row.to_dict()
        try:
            msg = validate_and_transform(raw)
            future = producer.send(RAW_TOPIC, key=msg["card_id"], value=msg)
            future.add_errback(lambda e: logger.error("Kafka send error: %s", e))
            sent += 1
        except (ValueError, KeyError) as exc:
            send_to_dlq(producer, raw, str(exc))
            errors += 1

        if sent % 10_000 == 0:
            logger.info("Sent %d txns | DLQ errors: %d", sent, errors)

        time.sleep(interval)

    producer.flush()
    logger.info("Done. Total sent: %d | DLQ errors: %d", sent, errors)


if __name__ == "__main__":
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "data/raw/paysim.csv"
    replay_csv(csv_file, tps=1000)
