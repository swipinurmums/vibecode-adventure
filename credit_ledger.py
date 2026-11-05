#!/usr/bin/env python3
"""Persistent monthly SerpApi quota ledger. Reservations are written before API calls."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PATH = Path("data/usage/monthly.json")
CAPS = {"flight": 120, "personal": 50, "hotel": 80}
TOTAL_CAP = 250

def month_key():
    return datetime.now(timezone.utc).strftime("%Y-%m")

def load():
    if not PATH.exists():
        return {"schema_version": 1, "reconciled": False, "months": {}}
    return json.loads(PATH.read_text(encoding="utf-8"))

def save(data):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

def current(data):
    return data.setdefault("months", {}).setdefault(month_key(), {
        "baseline_used": None,
        "reserved": {"flight": 0, "personal": 0, "hotel": 0}
    })

def status(data):
    month = current(data)
    print(f"UTC month: {month_key()}")
    print(f"Reconciled: {data.get('reconciled', False)}")
    print(f"Opening usage baseline: {month.get('baseline_used')}")
    reserved = month.get("reserved", {})
    tracked = sum(int(reserved.get(k, 0)) for k in CAPS)
    baseline = month.get("baseline_used")
    print(f"Tracked reservations: {tracked}/{TOTAL_CAP}")
    if baseline is not None:
        print(f"Estimated total usage incl. baseline: {baseline + tracked}/{TOTAL_CAP}")
    for name, cap in CAPS.items():
        used = int(reserved.get(name, 0))
        print(f"{name}: {used}/{cap} (remaining allocation {max(0, cap-used)})")

def reconcile(baseline_used):
    if not 0 <= baseline_used <= TOTAL_CAP:
        raise ValueError(f"baseline_used must be between 0 and {TOTAL_CAP}")
    data = load()
    month = current(data)
    month["baseline_used"] = baseline_used
    data["reconciled"] = True
    save(data)
    print(f"Saved opening baseline of {baseline_used} searches for {month_key()}.")
    status(data)

def reserve(category, count=1):
    if category not in CAPS:
        raise ValueError("Unknown credit category")
    if count < 1:
        raise ValueError("count must be positive")
    data = load()
    month = current(data)
    if not data.get("reconciled") or month.get("baseline_used") is None:
        raise RuntimeError("BLOCKED: monthly ledger has not been reconciled. Check SerpApi account usage, then run the ledger setup workflow first.")
    reserved = month.setdefault("reserved", {})
    for name in CAPS:
        reserved.setdefault(name, 0)
    if reserved[category] + count > CAPS[category]:
        raise RuntimeError(f"BLOCKED: {category} allocation would exceed {CAPS[category]} searches/month.")
    total = month["baseline_used"] + sum(int(reserved[k]) for k in CAPS)
    if total + count > TOTAL_CAP:
        raise RuntimeError(f"BLOCKED: monthly account cap of {TOTAL_CAP} would be exceeded.")
    reserved[category] += count
    save(data)
    print(f"Reserved {count} {category} search(es) before API request.")
    status(data)

def main_with_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("reconcile", help="Set current month's already-used account total")
    rec.add_argument("--baseline-used", type=int, required=True)
    res = sub.add_parser("reserve", help="Reserve credits before an API request")
    res.add_argument("--category", choices=CAPS, required=True)
    res.add_argument("--count", type=int, default=1)
    sub.add_parser("status", help="Show current monthly usage and remaining allocations")
    args = parser.parse_args(argv)
    try:
        if args.command == "reconcile":
            reconcile(args.baseline_used)
        elif args.command == "reserve":
            reserve(args.category, args.count)
        else:
            status(load())
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc))
    return 0

if __name__ == "__main__":
    raise SystemExit(main_with_args())
