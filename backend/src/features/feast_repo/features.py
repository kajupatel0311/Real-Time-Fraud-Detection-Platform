from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Float64

# Define an entity for the transaction. Often this is a user or card ID.
# Here we define an entity for the card_id.
card = Entity(
    name="card_id",
    join_keys=["card_id"],
    description="Card identifier for the transaction",
)

# Define the offline data source (could be S3/Parquet in production, local file for now)
transaction_source = FileSource(
    name="transaction_hourly_stats",
    path="../../../data/raw/creditcard.csv",  # Typically points to a transformed historical dataset like a Delta table
    timestamp_field="Time",  # Requires an actual datetime locally, but we'll conceptualize it or map it later
    created_timestamp_column="Time",
)

# Define the Feature View that connects the source, entity, and fields
transaction_stats_fv = FeatureView(
    name="transaction_stats",
    entities=[card],
    ttl=timedelta(days=30),  # How far back to look for features
    schema=[
        Field(name="Amount", dtype=Float64),
        Field(name="V1", dtype=Float64),
        Field(name="Velocity_1H", dtype=Float64),
        Field(name="Amt_Rolling_Mean_1H", dtype=Float64),
    ],
    online=True,
    source=transaction_source,
    tags={"team": "fraud", "pipeline": "real-time"},
)
