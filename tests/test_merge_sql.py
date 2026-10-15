from __future__ import annotations

import pytest

import shipments_incremental as job


def test_merge_sql_shape() -> None:
    sql = job.build_merge_sql("glue_catalog.curated.shipments", "src")
    assert sql.startswith("MERGE INTO glue_catalog.curated.shipments AS t\nUSING src AS s")
    assert "ON t.shipment_id = s.shipment_id" in sql
    assert "WHEN MATCHED AND s.event_ts > t.event_ts THEN UPDATE SET" in sql
    assert "WHEN NOT MATCHED THEN INSERT (" + ", ".join(job.TARGET_COLUMNS) + ")" in sql


def test_merge_sql_does_not_update_key_columns() -> None:
    sql = job.build_merge_sql("db.shipments", "src")
    assert "t.shipment_id = s.shipment_id," not in sql
    assert "t.status = s.status" in sql


def test_merge_sql_composite_key() -> None:
    sql = job.build_merge_sql(
        "db.t", "src", columns=("a", "b", "ts", "v"), key_cols=("a", "b"), order_col="ts"
    )
    assert "ON t.a = s.a AND t.b = s.b" in sql
    assert "UPDATE SET\n    t.ts = s.ts,\n    t.v = s.v\n" in sql


@pytest.mark.parametrize(
    "target, view",
    [
        ("db.shipments; DROP TABLE x", "src"),
        ("a.b.c.d", "src"),
        ("db.shipments", "src --"),
        ("db.ship-ments", "src"),
    ],
)
def test_merge_sql_rejects_unsafe_identifiers(target: str, view: str) -> None:
    with pytest.raises(ValueError):
        job.build_merge_sql(target, view)


def test_merge_sql_requires_key_in_columns() -> None:
    with pytest.raises(ValueError, match="missing"):
        job.build_merge_sql("db.t", "src", columns=("status", "event_ts"))


def test_parse_args_ignores_glue_extras() -> None:
    args = job.parse_args(
        [
            "script.py",
            "--JOB_NAME",
            "x",
            "--raw_path",
            "s3://raw/shipments/",
            "--target_table",
            "glue_catalog.curated.shipments",
            "--lookback_hours",
            "12",
            "--TempDir",
            "s3://tmp/",
        ]
    )
    assert args == job.JobArgs("s3://raw/shipments/", "glue_catalog.curated.shipments", 12)


def test_parse_args_rejects_negative_lookback() -> None:
    with pytest.raises(SystemExit):
        job.parse_args(["--raw_path", "p", "--target_table", "t", "--lookback_hours", "-1"])
