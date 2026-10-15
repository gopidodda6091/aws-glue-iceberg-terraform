"""Incremental load of Gulf Freight Co. shipment events into an Iceberg table.

The module is split in two layers:

* Pure transform functions (``normalize_events``, ``compute_watermark``,
  ``filter_after_watermark``, ``dedupe_latest``, ``build_merge_sql``) that take
  and return Spark DataFrames or plain values. They import nothing from
  ``awsglue`` and are unit-tested on a local SparkSession.
* A thin Glue entrypoint (``main``) that resolves job arguments, reads the raw
  JSON, wires the transforms together and executes the ``MERGE INTO``. The
  ``awsglue`` import happens inside ``main`` so tests never need it.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)

KEY_COLUMNS: tuple[str, ...] = ("shipment_id",)
WATERMARK_COLUMN = "event_ts"
TIEBREAK_COLUMN = "ingest_seq"
VALID_STATUSES: frozenset[str] = frozenset(
    {"booked", "picked_up", "in_transit", "delivered", "exception"}
)

# Raw events arrive as JSON with string timestamps; parse them explicitly so a
# malformed value becomes NULL instead of silently shifting time zones.
RAW_SCHEMA = StructType(
    [
        StructField("shipment_id", StringType()),
        StructField("event_id", StringType()),
        StructField("event_ts", StringType()),
        StructField("status", StringType()),
        StructField("origin_port", StringType()),
        StructField("destination_port", StringType()),
        StructField("carrier", StringType()),
        StructField("weight_kg", DoubleType()),
        StructField("ingest_seq", LongType()),
    ]
)

TARGET_COLUMNS: tuple[str, ...] = tuple(f.name for f in RAW_SCHEMA.fields)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class JobArgs:
    """Arguments the job needs, independent of how they were supplied."""

    raw_path: str
    target_table: str
    lookback_hours: int


# --------------------------------------------------------------------------
# Pure transforms
# --------------------------------------------------------------------------


def normalize_events(df: DataFrame) -> DataFrame:
    """Cast and clean raw events; drop rows that cannot be keyed or ordered."""
    return (
        df.select(
            F.trim("shipment_id").alias("shipment_id"),
            F.trim("event_id").alias("event_id"),
            F.to_timestamp("event_ts").alias("event_ts"),
            F.lower(F.trim("status")).alias("status"),
            F.upper(F.trim("origin_port")).alias("origin_port"),
            F.upper(F.trim("destination_port")).alias("destination_port"),
            F.trim("carrier").alias("carrier"),
            F.col("weight_kg").cast("double").alias("weight_kg"),
            F.coalesce(F.col("ingest_seq").cast("bigint"), F.lit(0)).alias("ingest_seq"),
        )
        .where(F.col("shipment_id").isNotNull() & (F.col("shipment_id") != ""))
        .where(F.col("event_ts").isNotNull())
        .where(F.col("status").isin(*sorted(VALID_STATUSES)))
    )


def compute_watermark(last_loaded_ts: datetime | None, lookback: timedelta) -> datetime | None:
    """Return the lower bound for the next run.

    ``None`` means "no data loaded yet": process everything. Otherwise the
    bound is moved back by ``lookback`` so late-arriving events are re-read;
    the MERGE makes the overlap idempotent.
    """
    if lookback < timedelta(0):
        raise ValueError("lookback must not be negative")
    if last_loaded_ts is None:
        return None
    return last_loaded_ts - lookback


def filter_after_watermark(
    df: DataFrame, watermark: datetime | None, ts_col: str = WATERMARK_COLUMN
) -> DataFrame:
    """Keep rows strictly newer than ``watermark`` (all rows if it is None)."""
    if watermark is None:
        return df
    # Pass the bound as a string so Spark interprets it in the session time
    # zone (UTC on Glue) rather than the Python driver's local zone.
    bound = watermark.strftime("%Y-%m-%d %H:%M:%S.%f")
    return df.where(F.col(ts_col) > F.lit(bound).cast("timestamp"))


def dedupe_latest(
    df: DataFrame,
    key_cols: Sequence[str] = KEY_COLUMNS,
    order_col: str = WATERMARK_COLUMN,
    tiebreak_col: str = TIEBREAK_COLUMN,
) -> DataFrame:
    """Keep the newest event per key; ties on ``order_col`` go to the higher tiebreak."""
    if not key_cols:
        raise ValueError("key_cols must not be empty")
    window = Window.partitionBy(*key_cols).orderBy(
        F.col(order_col).desc(), F.col(tiebreak_col).desc()
    )
    return df.withColumn("_rn", F.row_number().over(window)).where(F.col("_rn") == 1).drop("_rn")


def _check_identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


def _check_table_name(name: str) -> str:
    parts = name.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"table name must have 1-3 parts: {name!r}")
    for part in parts:
        _check_identifier(part)
    return name


def build_merge_sql(
    target_table: str,
    source_view: str,
    columns: Sequence[str] = TARGET_COLUMNS,
    key_cols: Sequence[str] = KEY_COLUMNS,
    order_col: str = WATERMARK_COLUMN,
) -> str:
    """Build an Iceberg ``MERGE INTO`` that upserts only when the source is newer.

    Older replays of an event never overwrite a newer row, which keeps the
    merge idempotent when the lookback window re-reads data.
    """
    _check_table_name(target_table)
    _check_identifier(source_view)
    cols = [_check_identifier(c) for c in columns]
    keys = [_check_identifier(k) for k in key_cols]
    _check_identifier(order_col)
    if not keys:
        raise ValueError("key_cols must not be empty")
    missing = [k for k in [*keys, order_col] if k not in cols]
    if missing:
        raise ValueError(f"columns missing key/order columns: {missing}")

    on_clause = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    update_cols = [c for c in cols if c not in keys]
    set_clause = ",\n    ".join(f"t.{c} = s.{c}" for c in update_cols)
    insert_cols = ", ".join(cols)
    insert_vals = ", ".join(f"s.{c}" for c in cols)
    return (
        f"MERGE INTO {target_table} AS t\n"
        f"USING {source_view} AS s\n"
        f"ON {on_clause}\n"
        f"WHEN MATCHED AND s.{order_col} > t.{order_col} THEN UPDATE SET\n"
        f"    {set_clause}\n"
        f"WHEN NOT MATCHED THEN INSERT ({insert_cols})\n"
        f"    VALUES ({insert_vals})"
    )


def prepare_increment(
    raw: DataFrame, last_loaded_ts: datetime | None, lookback: timedelta
) -> DataFrame:
    """Normalize -> watermark filter -> dedupe. Everything before the MERGE."""
    watermark = compute_watermark(last_loaded_ts, lookback)
    events = normalize_events(raw)
    return dedupe_latest(filter_after_watermark(events, watermark))


# --------------------------------------------------------------------------
# I/O and entrypoint
# --------------------------------------------------------------------------


def read_last_loaded_ts(spark: SparkSession, target_table: str) -> datetime | None:
    """Max event time already in the target, or None for an empty table."""
    _check_table_name(target_table)
    row = spark.sql(f"SELECT max({WATERMARK_COLUMN}) AS ts FROM {target_table}").first()
    return None if row is None else row["ts"]


def run(spark: SparkSession, args: JobArgs) -> int:
    """Execute one incremental run; returns the number of source rows merged."""
    raw = spark.read.schema(RAW_SCHEMA).json(args.raw_path)
    last_ts = read_last_loaded_ts(spark, args.target_table)
    increment = prepare_increment(raw, last_ts, timedelta(hours=args.lookback_hours))
    increment = increment.cache()
    count = increment.count()
    if count == 0:
        return 0
    increment.createOrReplaceTempView("shipments_increment")
    spark.sql(build_merge_sql(args.target_table, "shipments_increment"))
    return count


def parse_args(argv: Sequence[str]) -> JobArgs:
    """Parse ``--raw_path``, ``--target_table`` and ``--lookback_hours``.

    Glue passes many extra arguments (``--JOB_NAME``, ``--TempDir`` ...);
    unknown ones are ignored.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw_path", required=True)
    parser.add_argument("--target_table", required=True)
    parser.add_argument("--lookback_hours", type=int, default=6)
    ns, _unknown = parser.parse_known_args(list(argv))
    if ns.lookback_hours < 0:
        parser.error("--lookback_hours must be >= 0")
    return JobArgs(ns.raw_path, ns.target_table, ns.lookback_hours)


def main(argv: Sequence[str]) -> None:  # pragma: no cover - runs only on Glue
    from awsglue.context import GlueContext  # type: ignore[import-not-found]
    from awsglue.job import Job  # type: ignore[import-not-found]
    from awsglue.utils import getResolvedOptions  # type: ignore[import-not-found]
    from pyspark.context import SparkContext

    resolved = getResolvedOptions(list(argv), ["JOB_NAME"])
    args = parse_args(argv)
    glue_context = GlueContext(SparkContext.getOrCreate())
    job = Job(glue_context)
    job.init(resolved["JOB_NAME"], resolved)
    merged = run(glue_context.spark_session, args)
    print(f"merged {merged} shipment rows into {args.target_table}")
    job.commit()


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv)
