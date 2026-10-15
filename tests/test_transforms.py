from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pyspark.sql import Row, SparkSession

import shipments_incremental as job


def raw_df(spark: SparkSession, rows: list[dict]):
    return spark.createDataFrame([Row(**r) for r in rows], schema=job.RAW_SCHEMA)


def event(shipment_id: str, ts: str, status: str = "in_transit", seq: int = 1, **kw) -> dict:
    base = {
        "shipment_id": shipment_id,
        "event_id": f"{shipment_id}-{ts}",
        "event_ts": ts,
        "status": status,
        "origin_port": "USHOU",
        "destination_port": "USMSY",
        "carrier": "Pelican Line",
        "weight_kg": 1000.0,
        "ingest_seq": seq,
    }
    base.update(kw)
    return base


# --- normalize ---------------------------------------------------------------


def test_normalize_drops_unkeyable_and_unparseable_rows(spark: SparkSession) -> None:
    df = raw_df(
        spark,
        [
            event("GF-1", "2026-03-01T10:00:00Z"),
            event("   ", "2026-03-01T10:00:00Z"),
            event("GF-2", "not-a-timestamp"),
            event("GF-3", "2026-03-01T10:00:00Z", status="teleported"),
        ],
    )
    out = job.normalize_events(df).collect()
    assert [r.shipment_id for r in out] == ["GF-1"]


def test_normalize_cleans_case_and_whitespace(spark: SparkSession) -> None:
    df = raw_df(
        spark,
        [event(" GF-1 ", "2026-03-01T10:00:00Z", status=" Delivered ", origin_port="ushou ")],
    )
    row = job.normalize_events(df).first()
    assert row.shipment_id == "GF-1"
    assert row.status == "delivered"
    assert row.origin_port == "USHOU"
    assert row.event_ts == datetime(2026, 3, 1, 10, 0, 0)


def test_normalize_defaults_missing_ingest_seq(spark: SparkSession) -> None:
    df = raw_df(spark, [event("GF-1", "2026-03-01T10:00:00Z", seq=None)])
    assert job.normalize_events(df).first().ingest_seq == 0


# --- watermark ---------------------------------------------------------------


def test_compute_watermark_first_run_is_none() -> None:
    assert job.compute_watermark(None, timedelta(hours=6)) is None


def test_compute_watermark_applies_lookback() -> None:
    last = datetime(2026, 3, 2, 12, 0)
    assert job.compute_watermark(last, timedelta(hours=6)) == datetime(2026, 3, 2, 6, 0)


def test_compute_watermark_rejects_negative_lookback() -> None:
    with pytest.raises(ValueError):
        job.compute_watermark(datetime(2026, 3, 2), timedelta(hours=-1))


def test_filter_after_watermark_is_strict(spark: SparkSession) -> None:
    df = job.normalize_events(
        raw_df(
            spark,
            [
                event("GF-1", "2026-03-01T05:59:59Z"),
                event("GF-2", "2026-03-01T06:00:00Z"),
                event("GF-3", "2026-03-01T06:00:01Z"),
            ],
        )
    )
    out = job.filter_after_watermark(df, datetime(2026, 3, 1, 6, 0, 0))
    assert [r.shipment_id for r in out.collect()] == ["GF-3"]


def test_filter_without_watermark_keeps_everything(spark: SparkSession) -> None:
    df = job.normalize_events(raw_df(spark, [event("GF-1", "2020-01-01T00:00:00Z")]))
    assert job.filter_after_watermark(df, None).count() == 1


# --- dedupe ------------------------------------------------------------------


def test_dedupe_keeps_latest_event_per_shipment(spark: SparkSession) -> None:
    df = job.normalize_events(
        raw_df(
            spark,
            [
                event("GF-1", "2026-03-01T10:00:00Z", status="booked"),
                event("GF-1", "2026-03-02T10:00:00Z", status="delivered"),
                event("GF-1", "2026-03-01T20:00:00Z", status="in_transit"),
                event("GF-2", "2026-03-01T09:00:00Z", status="booked"),
            ],
        )
    )
    out = {r.shipment_id: r.status for r in job.dedupe_latest(df).collect()}
    assert out == {"GF-1": "delivered", "GF-2": "booked"}


def test_dedupe_breaks_timestamp_ties_with_ingest_seq(spark: SparkSession) -> None:
    df = job.normalize_events(
        raw_df(
            spark,
            [
                event("GF-1", "2026-03-01T10:00:00Z", carrier="Old", seq=1),
                event("GF-1", "2026-03-01T10:00:00Z", carrier="Redelivered", seq=2),
            ],
        )
    )
    rows = job.dedupe_latest(df).collect()
    assert len(rows) == 1 and rows[0].carrier == "Redelivered"


def test_dedupe_requires_keys(spark: SparkSession) -> None:
    df = job.normalize_events(raw_df(spark, [event("GF-1", "2026-03-01T10:00:00Z")]))
    with pytest.raises(ValueError):
        job.dedupe_latest(df, key_cols=())


# --- prepare_increment (whole pre-merge pipeline) ----------------------------


def test_prepare_increment_rereads_lookback_window(spark: SparkSession) -> None:
    df = raw_df(
        spark,
        [
            event("GF-1", "2026-03-02T01:00:00Z"),  # older than lookback: skipped
            event("GF-2", "2026-03-02T09:00:00Z"),  # late event inside lookback
            event("GF-3", "2026-03-02T13:00:00Z"),  # new
            event("GF-3", "2026-03-02T13:00:00Z", seq=2),  # duplicate
        ],
    )
    out = job.prepare_increment(df, datetime(2026, 3, 2, 12, 0), timedelta(hours=6))
    assert sorted((r.shipment_id, r.ingest_seq) for r in out.collect()) == [
        ("GF-2", 1),
        ("GF-3", 2),
    ]


# --- run() without Iceberg: empty increment short-circuits before MERGE ------


def test_run_returns_zero_when_nothing_is_newer(spark: SparkSession, tmp_path) -> None:
    import json

    spark.sql("DROP TABLE IF EXISTS plain_target")
    spark.sql("CREATE TABLE plain_target (event_ts TIMESTAMP) USING parquet")
    spark.sql("INSERT INTO plain_target VALUES (TIMESTAMP '2026-03-05 00:00:00')")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "part.json").write_text(json.dumps(event("GF-1", "2026-03-01T00:00:00Z")) + "\n")
    assert job.run(spark, job.JobArgs(str(raw), "plain_target", 6)) == 0


def test_generated_feed_reduces_to_one_row_per_shipment(spark: SparkSession, tmp_path) -> None:
    from datetime import UTC

    import generate_shipments as gen

    gen.write(gen.generate(60, datetime(2026, 3, 1, tzinfo=UTC), seed=11), tmp_path)
    raw = spark.read.schema(job.RAW_SCHEMA).json(str(tmp_path / "shipments"))
    out = job.prepare_increment(raw, None, timedelta(hours=6))
    assert out.count() == out.select("shipment_id").distinct().count()
    assert out.count() <= 60
    assert (
        out.where(
            "status NOT IN ('booked','picked_up','in_transit','delivered','exception')"
        ).count()
        == 0
    )
