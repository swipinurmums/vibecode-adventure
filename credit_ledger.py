#!/usr/bin/env python3
"""Persistent monthly SerpApi quota ledger. Reservations are written before API calls."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PATH = Path("data/usage/monthly.json")
# SerpApi renews on the 4th of each month (the 2026-12-04 renewal
# follows a 2026-11-04 cycle start). Keep the ledger aligned to that cycle.
BILLING_CYCLE_DAY = 4
CAPS = {"flight": 142, "personal": 20, "hotel": 45, "research": 28, "coverage": 15}
TOTAL_CAP = 250

def month_key(now=None):
    now = now or datetime.now(timezone.utc)
    year, month = now.year, now.month
    if now.day < BILLING_CYCLE_DAY:
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
    return f"{year:04d}-{month:02d}-{BILLING_CYCLE_DAY:02d}"

def load():
    if not PATH.exists():
        return {"schema_version": 1, "reconciled": False, "months": {}}
    return json.loads(PATH.read_text(encoding="utf-8"))

def save(data):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

def current(data):
    months = data.setdefault("months", {})
    key = month_key()
    # One-time migration from the old calendar-month ledger without discarding
    # any reservations already recorded for the active provider billing cycle.
    legacy_key = key[:7]
    if key not in months and legacy_key in months:
        months[key] = months.pop(legacy_key)
    return months.setdefault(key, {
        "baseline_used": None,
        "reserved": {"flight": 0, "personal": 0, "hotel": 0, "research": 0, "coverage": 0}
    })

def status(data):
    month = current(data)
    reserved = month.get("reserved", {})
    counted = sum(int(reserved.get(k, 0)) for k in CAPS)
    print(f"UTC billing cycle: {month_key()} (renews on day {BILLING_CYCLE_DAY})")
    print(f"Reconciled: {month.get('baseline_used') is not None}")
    print(f"Opening usage baseline (charged to flight allocation): {month.get('baseline_used')}")
    print(f"Counted monthly usage incl. baseline: {counted}/{TOTAL_CAP}")
    for name, cap in CAPS.items():
        used = int(reserved.get(name, 0))
        print(f"{name}: {used}/{cap} (remaining allocation {max(0, cap-used)})")

def reconcile(baseline_used):
    if not 0 <= baseline_used <= TOTAL_CAP:
        raise ValueError(f"baseline_used must be between 0 and {TOTAL_CAP}")
    data = load()
    month = current(data)
    if month.get("baseline_used") is not None:
        raise RuntimeError("This month is already reconciled. Refusing to reset recorded reservations.")
    # Prior unclassified usage is conservatively charged to the flight bucket,
    # preserving the 50 personal and 80 hotel allocations.
    month["baseline_used"] = baseline_used
    month["reserved"] = {"flight": baseline_used, "personal": 0, "hotel": 0, "research": 0, "coverage": 0}
    data["reconciled"] = True
    save(data)
    print(f"Saved opening baseline of {baseline_used} searches for billing cycle {month_key()}.")
    status(data)

def reserve(category, count=1):
    if category not in CAPS:
        raise ValueError("Unknown credit category")
    if count < 1:
        raise ValueError("count must be positive")
    data = load()
    month = current(data)
    if month.get("baseline_used") is None:
        raise RuntimeError("BLOCKED: monthly ledger has not been reconciled. Check SerpApi account usage, then run the ledger setup workflow first.")
    reserved = month.setdefault("reserved", {})
    for name in CAPS:
        reserved.setdefault(name, 0)
    if reserved[category] + count > CAPS[category]:
        raise RuntimeError(f"BLOCKED: {category} allocation would exceed {CAPS[category]} searches/month.")
    total = sum(int(reserved[k]) for k in CAPS)
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
