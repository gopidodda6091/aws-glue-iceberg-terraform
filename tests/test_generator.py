from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import generate_shipments as gen


def test_generator_is_deterministic() -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    assert gen.generate(50, start, seed=1) == gen.generate(50, start, seed=1)


def test_generator_writes_partitioned_jsonl(tmp_path: Path) -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    paths = gen.write(gen.generate(40, start, seed=3), tmp_path)
    assert paths and all(p.parent.name.startswith("dt=") for p in paths)
    first = json.loads(paths[0].read_text(encoding="utf-8").splitlines()[0])
    assert set(first) == {
        "shipment_id",
        "event_id",
        "event_ts",
        "status",
        "origin_port",
        "destination_port",
        "carrier",
        "weight_kg",
        "ingest_seq",
    }


def test_generator_contains_duplicates_for_dedupe_to_handle() -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    events = [e for day in gen.generate(300, start, seed=7).values() for e in day]
    ids = [e["event_id"] for e in events]
    assert len(ids) > len(set(ids))
