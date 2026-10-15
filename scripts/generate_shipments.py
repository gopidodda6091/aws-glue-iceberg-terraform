"""Generate synthetic Gulf Freight Co. shipment events as daily JSON-lines files.

The data is deliberately messy, the way real feeds are:
* every shipment emits several status events over a few days,
* some events are delivered twice (same event_id, later ingest_seq),
* some events arrive late (land in a later day's file),
* a few rows are malformed (blank key, bad timestamp, unknown status).

Output layout mirrors the raw zone: <out>/shipments/dt=YYYY-MM-DD/part-0000.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

PORTS = ("USHOU", "USMSY", "USMOB", "USCRP", "MXVER", "USTPA", "USGLS")
CARRIERS = ("Pelican Line", "Bayou Barge", "Gulfstar Shipping", "Delta Coastal")
FLOW = ("booked", "picked_up", "in_transit", "delivered")


def shipment_events(rng: random.Random, shipment_no: int, start: datetime) -> Iterator[dict]:
    """Yield the lifecycle events of one shipment."""
    origin, destination = rng.sample(PORTS, 2)
    carrier = rng.choice(CARRIERS)
    weight = round(rng.uniform(250, 24000), 1)
    ts = start + timedelta(minutes=rng.randint(0, 60 * 24))
    steps = FLOW if rng.random() > 0.08 else (*FLOW[:2], "exception")
    for step_no, status in enumerate(steps[: rng.randint(2, len(steps))]):
        ts += timedelta(hours=rng.randint(2, 30))
        yield {
            "shipment_id": f"GF-{shipment_no:06d}",
            "event_id": f"EV-{shipment_no:06d}-{step_no}",
            "event_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "origin_port": origin.lower() if rng.random() < 0.1 else origin,
            "destination_port": destination,
            "carrier": carrier,
            "weight_kg": weight,
            "ingest_seq": 1,
        }


def corrupt(rng: random.Random, event: dict) -> dict:
    """Return a malformed copy of an event."""
    bad = dict(event)
    choice = rng.choice(("blank_key", "bad_ts", "bad_status"))
    if choice == "blank_key":
        bad["shipment_id"] = "  "
    elif choice == "bad_ts":
        bad["event_ts"] = "not-a-timestamp"
    else:
        bad["status"] = "teleported"
    return bad


def generate(n_shipments: int, start: datetime, seed: int) -> dict[str, list[dict]]:
    """Return events grouped by landing date (dt=...)."""
    rng = random.Random(seed)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for i in range(n_shipments):
        day_start = start + timedelta(days=rng.randint(0, 2))
        for event in shipment_events(rng, i, day_start):
            landed = datetime.strptime(event["event_ts"], "%Y-%m-%dT%H:%M:%SZ")
            if rng.random() < 0.05:  # late arrival
                landed += timedelta(days=1)
            day = landed.strftime("%Y-%m-%d")
            by_day[day].append(event)
            if rng.random() < 0.07:  # duplicate delivery
                by_day[day].append({**event, "ingest_seq": 2})
            if rng.random() < 0.02:
                by_day[day].append(corrupt(rng, event))
    return dict(by_day)


def write(by_day: dict[str, list[dict]], out_dir: Path) -> list[Path]:
    """Write one JSON-lines file per landing day; return the paths written."""
    written = []
    for day, events in sorted(by_day.items()):
        path = out_dir / "shipments" / f"dt={day}" / "part-0000.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--shipments", type=int, default=500)
    parser.add_argument("--start", default="2026-03-01")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=UTC)
    paths = write(generate(args.shipments, start, args.seed), args.out)
    total = sum(1 for p in paths for _ in p.open(encoding="utf-8"))
    print(f"wrote {total} events across {len(paths)} daily files under {args.out}")


if __name__ == "__main__":
    main()
