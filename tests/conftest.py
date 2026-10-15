from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "glue_jobs"))
sys.path.insert(0, str(ROOT / "scripts"))

ICEBERG_PKG = "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1"


def iceberg_enabled() -> bool:
    """The Iceberg integration test needs a jar from Maven Central; opt-in."""
    return os.environ.get("ICEBERG_IT") == "1"


@pytest.fixture(scope="session")
def spark(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SparkSession]:
    # Spark converts naive Python datetimes with the driver's local zone; pin
    # everything to UTC so tests behave the same on laptops and in CI.
    os.environ["TZ"] = "UTC"
    time.tzset()
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("shipments-tests")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.warehouse.dir", str(tmp_path_factory.mktemp("spark-warehouse")))
        .config("spark.driver.extraJavaOptions", "-Duser.timezone=UTC")
    )
    if iceberg_enabled():
        builder = (
            builder.config("spark.jars.packages", ICEBERG_PKG)
            .config(
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            )
            .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.local.type", "hadoop")
            .config(
                "spark.sql.catalog.local.warehouse",
                str(tmp_path_factory.mktemp("iceberg-warehouse")),
            )
        )
    session = builder.getOrCreate()
    yield session
    session.stop()
