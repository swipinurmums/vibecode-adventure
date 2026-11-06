#!/usr/bin/env python3
"""Build a dashboard-ready, ranked feed from historical observations."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from deal_tracker import load_history


def trip_key(row):
    return (
        row.get("origin"), row.get("destination"), row.get("country"),
        row.get("start_date"), row.get("nights")
    )


def latest_rows(rows):
    latest = {}
    for row in rows:
        if row.get("kind") not in ("flight", "hotel"):
            continue
        identity = trip_key(row)
        if row.get("kind") == "hotel":
            identity += ((row.get("property_key") or row.get("property") or "").casefold(),)
        key = (row.get("kind"),) + identity
        stamp = str(row.get("observed_at") or "")
        if key not in latest or stamp >= str(latest[key].get("observed_at") or ""):
            latest[key] = row
    return list(latest.values())


def load_insights(folder):
    found = {}
    root = Path(folder)
    if not root.exists():
        return found
    for path in sorted(root.glob("**/insights.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = (row.get("origin"), row.get("destination"), row.get("departure_date"), row.get("return_date"))
        if key not in found or str(row.get("observed_at") or "") >= str(found[key].get("observed_at") or ""):
            found[key] = row
    return found


def rank_record(row, insight=None):
    flight_discount = (insight or {}).get("discount_vs_typical_low_percent")
    if flight_discount is None:
        flight_discount = row.get("flight_discount_percent", row.get("discount_percent") if row.get("kind") == "flight" else None)
    hotel_discount = row.get("discount_percent") if row.get("kind") == "hotel" else None
    combined = row.get("combined_discount_percent") if row.get("kind") == "hotel" else None
    available = [x for x in (flight_discount, hotel_discount) if isinstance(x, (int, float))]
    ranking_discount = combined if isinstance(combined, (int, float)) else (sum(available) / len(available) if available else None)

    if combined is not None and combined >= 15:
        status = "strong_combined_deal"
    elif (insight or {}).get("benchmark_status") == "strong_deal" and hotel_discount is not None and hotel_discount >= 15:
        status = "strong_combined_deal"
    elif ranking_discount is not None and ranking_discount >= 15:
        status = "strong_component_deal"
    elif ranking_discount is not None and ranking_discount > 0:
        status = "below_typical"
    elif ranking_discount is not None:
        status = "not_below_typical"
    else:
        status = "building_history"

    if insight and row.get("kind") == "hotel" and row.get("benchmark_gbp") is not None:
        confidence = "high" if row.get("sample_count", 0) >= 3 else "medium"
    elif insight or row.get("benchmark_gbp") is not None:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "deal_status": status,
        "ranking_discount_percent": round(ranking_discount, 1) if ranking_discount is not None else None,
        "flight_discount_percent": flight_discount,
        "hotel_discount_percent": hotel_discount,
        "combined_discount_percent": combined,
        "confidence": confidence,
    }


def build_feed(history, insights):
    records = []
    for row in latest_rows(history):
        insight = insights.get((
            row.get("origin"), row.get("destination"),
            row.get("start_date"), row.get("end_date")
        ))
        if row.get("kind") == "hotel":
            # Historical hotel rows store trip length, while insight records
            # store both exact dates. Match by trip identity and derive dates
            # only when they are available on the history row.
            insight = insights.get((
                row.get("origin"), row.get("destination"),
                row.get("start_date"), row.get("end_date")
            ), insight)
        ranked = rank_record(row, insight)
        record = dict(row)
        record.update(ranked)
        if insight:
            record["google_flights_price_insights"] = insight
        records.append(record)
    records.sort(key=lambda r: (
        r.get("ranking_discount_percent") is None,
        -(r.get("ranking_discount_percent") or 0),
        r.get("observed_at") or ""
    ))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deal_count": len(records),
        "strong_deal_count": sum(r["deal_status"] in ("strong_combined_deal", "strong_component_deal") for r in records),
        "deals": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="data/history/observations.jsonl")
    parser.add_argument("--insights-dir", default="data/flight_insights")
    parser.add_argument("--output", default="data/deals/deals.json")
    args = parser.parse_args()
    feed = build_feed(load_history(args.history), load_insights(args.insights_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Deal feed built: {feed['deal_count']} records, {feed['strong_deal_count']} strong deal signals")
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()
