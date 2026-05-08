"""
Stage 2.2 — PySpark Structured Streaming
Consumes transactions.raw Kafka topic, engineers velocity features via
windowed aggregations, and writes enriched records to Delta Lake on S3.

Run with:
    spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0,\
        io.delta:delta-core_2.12:2.4.0 src/spark/streaming_job.py
"""
import sys
import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, LongType, BooleanType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ───────────────────────── Config ──────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
RAW_TOPIC       = "transactions.raw"
ENRICHED_TOPIC  = "transactions.enriched"
DELTA_OUTPUT    = os.getenv("DELTA_OUTPUT", "output/delta/enriched_transactions")
CHECKPOINT_DIR  = os.getenv("CHECKPOINT_DIR", "output/checkpoints/streaming")

# ───────────────────────── Schema ──────────────────────────
TXN_SCHEMA = StructType([
    StructField("txn_id",       StringType(),  False),
    StructField("card_id",      StringType(),  False),
    StructField("amount",       DoubleType(),  False),
    StructField("merchant_id",  StringType(),  False),
    StructField("timestamp",    LongType(),    False),
    StructField("currency",     StringType(),  True),
    StructField("country_code", StringType(),  True),
    StructField("channel",      StringType(),  True),
    StructField("is_fraud",     BooleanType(), True),
])


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("FraudDetection-Streaming")
        # Kafka integration
        .config("spark.sql.streaming.kafka.useDeprecatedOffsetFetching", "false")
        # Delta Lake
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Performance tuning (Prompt 2.2)
        .config("spark.sql.shuffle.partitions", "12")        # match Kafka partitions
        .config("spark.streaming.backpressure.enabled", "true")
        .config("spark.streaming.kafka.maxRatePerPartition", "5000")
        .config("spark.sql.streaming.minBatchesToRetain", "5")
        # Delta write tuning
        .config("spark.databricks.delta.optimizeWrite.enabled", "true")
        .config("spark.databricks.delta.autoCompact.enabled", "true")
        .getOrCreate()
    )


def read_kafka_stream(spark: SparkSession):
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", RAW_TOPIC)
        .option("startingOffsets", "latest")
        .option("maxOffsetsPerTrigger", 50_000)   # backpressure knob (Prompt 2.2)
        .option("failOnDataLoss", "false")
        .load()
    )


def parse_and_enrich(raw_stream):
    """
    Parse JSON payload and engineer velocity features using Spark windows.
    Three windows per card: 1-min, 5-min, 1-hour — run as one query to avoid
    triple Kafka reads (Prompt 2.2: combine aggregations).
    """
    # Parse JSON value
    parsed = (
        raw_stream
        .selectExpr("CAST(value AS STRING) AS json_str",
                    "CAST(key AS STRING) AS kafka_key",
                    "timestamp AS kafka_ts")
        .select(
            F.from_json(F.col("json_str"), TXN_SCHEMA).alias("data"),
            "kafka_ts"
        )
        .select("data.*", "kafka_ts")
        .withColumn("event_time", F.to_timestamp(F.col("timestamp") / 1000))
        .withWatermark("event_time", "2 minutes")   # allow 2-min late arrivals
    )

    # ── Velocity aggregations (all three windows in one pass) ──────────────
    # 1-min window: transaction count and amount sum per card
    vel_1m = (
        parsed
        .groupBy(F.col("card_id"), F.window("event_time", "1 minute"))
        .agg(
            F.count("txn_id").alias("txn_count_1m"),
            F.sum("amount").alias("amount_sum_1m"),
        )
        .select("card_id",
                F.col("window.end").alias("window_end_1m"),
                "txn_count_1m", "amount_sum_1m")
    )

    # 5-min window
    vel_5m = (
        parsed
        .groupBy(F.col("card_id"), F.window("event_time", "5 minutes"))
        .agg(
            F.count("txn_id").alias("txn_count_5m"),
            F.sum("amount").alias("amount_sum_5m"),
            F.countDistinct("merchant_id").alias("unique_merchants_5m"),
        )
        .select("card_id",
                F.col("window.end").alias("window_end_5m"),
                "txn_count_5m", "amount_sum_5m", "unique_merchants_5m")
    )

    # 1-hour window
    vel_1h = (
        parsed
        .groupBy(F.col("card_id"), F.window("event_time", "1 hour"))
        .agg(
            F.count("txn_id").alias("txn_count_1h"),
            F.sum("amount").alias("amount_sum_1h"),
            F.max("amount").alias("amount_max_1h"),
            F.countDistinct("merchant_id").alias("unique_merchants_1h"),
        )
        .select("card_id",
                F.col("window.end").alias("window_end_1h"),
                "txn_count_1h", "amount_sum_1h", "amount_max_1h",
                "unique_merchants_1h")
    )

    return parsed, vel_1m, vel_5m, vel_1h


def write_stream_to_delta(stream, path: str, checkpoint: str, trigger_secs: int = 30):
    return (
        stream.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint)
        .option("mergeSchema", "true")
        # Micro-batch trigger every 30s (tunable)
        .trigger(processingTime=f"{trigger_secs} seconds")
        .start(path)
    )


def run():
    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    logger.info("SparkSession started. Reading from Kafka topic: %s", RAW_TOPIC)

    raw_stream = read_kafka_stream(spark)
    parsed, vel_1m, vel_5m, vel_1h = parse_and_enrich(raw_stream)

    # Write each stream to its own Delta table with isolated checkpoints
    q1 = write_stream_to_delta(
        parsed, f"{DELTA_OUTPUT}/raw_parsed",
        f"{CHECKPOINT_DIR}/raw_parsed"
    )
    q2 = write_stream_to_delta(
        vel_1m, f"{DELTA_OUTPUT}/velocity_1m",
        f"{CHECKPOINT_DIR}/velocity_1m"
    )
    q3 = write_stream_to_delta(
        vel_5m, f"{DELTA_OUTPUT}/velocity_5m",
        f"{CHECKPOINT_DIR}/velocity_5m"
    )
    q4 = write_stream_to_delta(
        vel_1h, f"{DELTA_OUTPUT}/velocity_1h",
        f"{CHECKPOINT_DIR}/velocity_1h"
    )

    logger.info("All streaming queries running. Awaiting termination...")
    # Block until all queries finish (or Ctrl-C)
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    run()
