"""End-to-end MERGE INTO against a real (local, Hadoop-catalog) Iceberg table.

Opt-in with ICEBERG_IT=1 (CI sets it): the shared SparkSession then loads the
iceberg-spark-runtime jar from Maven Central and registers a ``local`` catalog.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import iceberg_enabled
from pyspark.sql import SparkSession

import shipments_incremental as job

pytestmark = pytest.mark.skipif(
    not iceberg_enabled(), reason="set ICEBERG_IT=1 to run (downloads the Iceberg jar)"
)

TABLE = "local.curated.shipments"
DDL = f"""
CREATE TABLE {TABLE} (
  shipment_id STRING, event_id STRING, event_ts TIMESTAMP, status STRING,
  origin_port STRING, destination_port STRING, carrier STRING,
  weight_kg DOUBLE, ingest_seq BIGINT
) USING iceberg
"""


def _land(path: Path, rows: list[dict]) -> str:
    path.mkdir(parents=True, exist_ok=True)
    (path / "part-0000.json").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return str(path)


def _row(sid: str, ts: str, status: str) -> dict:
    return {
        "shipment_id": sid,
        "event_id": f"{sid}-{ts}",
        "event_ts": ts,
        "status": status,
        "origin_port": "USHOU",
        "destination_port": "USMSY",
        "carrier": "Pelican Line",
        "weight_kg": 500.0,
        "ingest_seq": 1,
    }


def test_two_runs_upsert_and_ignore_stale_replays(spark: SparkSession, tmp_path: Path) -> None:
    spark.sql(f"DROP TABLE IF EXISTS {TABLE}")
    spark.sql(DDL)

    day1 = _land(
        tmp_path / "d1",
        [
            _row("GF-1", "2026-03-01T08:00:00Z", "booked"),
            _row("GF-2", "2026-03-01T09:00:00Z", "booked"),
        ],
    )
    assert job.run(spark, job.JobArgs(day1, TABLE, 6)) == 2

    day2 = _land(
        tmp_path / "d2",
        [
            _row("GF-1", "2026-03-01T20:00:00Z", "in_transit"),
            _row("GF-2", "2026-03-01T09:00:00Z", "booked"),  # replay inside lookback
            _row("GF-3", "2026-03-01T21:00:00Z", "booked"),
        ],
    )
    job.run(spark, job.JobArgs(day2, TABLE, 24))

    rows = {r.shipment_id: r.status for r in spark.table(TABLE).collect()}
    assert rows == {"GF-1": "in_transit", "GF-2": "booked", "GF-3": "booked"}
