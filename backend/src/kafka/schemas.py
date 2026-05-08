"""
Stage 2.1 — Kafka Topic Architecture & Avro Schema Definitions
Topics:
    - transactions.raw        : All incoming transactions (12 partitions, keyed by card_id)
    - transactions.enriched   : After Spark feature engineering
    - transactions.fraud.alerts: Flagged fraud events
    - transactions.dlq        : Dead Letter Queue for malformed events
"""

# --------------------  Avro Schema  --------------------
TRANSACTION_SCHEMA = {
    "type": "record",
    "name": "Transaction",
    "namespace": "com.frauddetector",
    "fields": [
        {"name": "txn_id",       "type": "string"},
        {"name": "card_id",      "type": "string"},
        {"name": "amount",       "type": "double"},
        {"name": "merchant_id",  "type": "string"},
        {"name": "timestamp",    "type": "long"},        # epoch ms
        {"name": "currency",     "type": "string"},
        {"name": "country_code", "type": "string"},
        {"name": "channel",      "type": {"type": "enum", "name": "Channel",
                                          "symbols": ["MOBILE", "WEB", "ATM", "POS"]}},
        {"name": "is_fraud",     "type": ["null", "boolean"], "default": None}  # label; None at ingest
    ]
}

# --------------------  Topic Config  --------------------
TOPIC_CONFIG = {
    "transactions.raw": {
        "partitions": 12,
        "replication_factor": 3,
        "config": {
            "retention.ms": str(7 * 24 * 60 * 60 * 1000),   # 7 days
            "compression.type": "lz4",
            "max.message.bytes": "1048576"
        }
    },
    "transactions.enriched": {
        "partitions": 12,
        "replication_factor": 3,
        "config": {
            "retention.ms": str(3 * 24 * 60 * 60 * 1000),   # 3 days
            "compression.type": "lz4"
        }
    },
    "transactions.fraud.alerts": {
        "partitions": 4,
        "replication_factor": 3,
        "config": {
            "retention.ms": str(30 * 24 * 60 * 60 * 1000),  # 30 days (audit)
            "compression.type": "gzip"
        }
    },
    "transactions.dlq": {
        "partitions": 2,
        "replication_factor": 3,
        "config": {
            "retention.ms": str(14 * 24 * 60 * 60 * 1000),  # 14 days
            "compression.type": "gzip"
        }
    }
}
