#!/usr/bin/env python3
"""Build independent flight, hotel and combined-holiday deal signals."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from deal_tracker import load_history


def trip_key(row):
    return (
        row.get("origin"), row.get("destination"), row.get("country"),
        row.get("start_date"), row.get("end_date"), row.get("nights")
    )


def latest_rows(rows):
    latest = {}
    for row in rows:
        if row.get("kind") not in ("flight", "hotel"):
            continue
        identity = trip_key(row)
        if row.get("kind") == "hotel":
            # A hotel's price is destination/date-specific, not departure-airport-specific.
            identity = tuple(row.get(k) for k in ("destination", "country", "start_date", "end_date", "nights"))
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


def status_for(discount, component):
    if not isinstance(discount, (int, float)):
        return f"building_{component}_benchmark"
    if discount >= 15:
        return f"strong_{component}_deal"
    if discount > 0:
        return f"below_typical_{component}"
    return f"not_below_typical_{component}"


def rank_record(row, insight=None):
    """Rank the requested component independently; never let package value overwrite it."""
    is_hotel = row.get("kind") == "hotel"
    historical_source = "personal_historical_median"
    insight_source = "google_flights_price_insights"
    if is_hotel:
        hotel_discount = row.get("discount_percent")
        flight_discount = (insight or {}).get("discount_vs_typical_low_percent")
        if flight_discount is None:
            flight_discount = row.get("flight_discount_percent")
        component_discount, component = hotel_discount, "hotel"
        component_source = historical_source if row.get("benchmark_gbp") is not None else "insufficient_comparable_history"
        flight_source = insight_source if insight and flight_discount is not None else (
            historical_source if row.get("flight_benchmark_gbp") is not None else "insufficient_comparable_history")
    else:
        flight_discount = (insight or {}).get("discount_vs_typical_low_percent")
        if flight_discount is None:
            flight_discount = row.get("discount_percent", row.get("flight_discount_percent"))
        hotel_discount = None
        component_discount, component = flight_discount, "flight"
        component_source = insight_source if insight and flight_discount is not None else (
            historical_source if row.get("benchmark_gbp") is not None else "insufficient_comparable_history")
        flight_source = component_source

    combined = row.get("combined_discount_percent") if is_hotel else None
    modes = [component]
    if is_hotel and isinstance(combined, (int, float)):
        modes.append("combined")
    samples = row.get("sample_count", 0) or 0
    component_confidence = (
        "high" if component_source == historical_source and samples >= 5
        else ("medium" if component_source != "insufficient_comparable_history" else "low")
    )
    flight_samples = (row.get("flight_sample_count", 0) or 0) if is_hotel else samples
    flight_confidence = (
        "medium" if flight_source == insight_source
        else ("high" if flight_source == historical_source and flight_samples >= 5
              else ("medium" if flight_source == historical_source else "low"))
    )
    hotel_source = historical_source if is_hotel and row.get("benchmark_gbp") is not None else "insufficient_comparable_history"
    combined_source = (
        row.get("combined_benchmark_method") or "component_benchmarks"
        if isinstance(combined, (int, float)) else "insufficient_component_benchmarks"
    )
    return {
        "deal_status": status_for(component_discount, component),
        "ranking_discount_percent": round(component_discount, 1) if isinstance(component_discount, (int, float)) else None,
        "flight_discount_percent": flight_discount,
        "hotel_discount_percent": hotel_discount,
        "combined_discount_percent": combined,
        "flight_deal_status": status_for(flight_discount, "flight"),
        "hotel_deal_status": status_for(hotel_discount, "hotel") if is_hotel else None,
        "combined_deal_status": status_for(combined, "combined") if is_hotel else None,
        "combined_ranking_discount_percent": round(combined, 1) if isinstance(combined, (int, float)) else None,
        "deal_modes": modes,
        "benchmark_source": component_source,
        "flight_benchmark_source": flight_source,
        "hotel_benchmark_source": hotel_source,
        "combined_benchmark_source": combined_source,
        "confidence": component_confidence,
        "flight_confidence": flight_confidence,
    }

def build_feed(history, insights):
    records = []
    matched_insights = set()
    for row in latest_rows(history):
        key = (row.get("origin"), row.get("destination"), row.get("start_date"), row.get("end_date"))
        insight = insights.get(key)
        record = dict(row)

        # Package value is calculated only when both components have credible
        # benchmarks. Use the actual flight fare attached to this hotel search
        # as the current package price, and Google's typical-low fare as the
        # market reference when available.
        if record.get("kind") == "hotel":
            try:
                current_flight = float(record.get("flight_price_gbp"))
                current_hotel = float(record.get("price_gbp"))
            except (TypeError, ValueError):
                current_flight = current_hotel = None
            typical_flight = None
            if insight:
                typical_flight = insight.get("typical_price_low_gbp")
            if typical_flight is None:
                typical_flight = record.get("flight_benchmark_gbp")
            hotel_benchmark = record.get("benchmark_gbp")
            if (current_flight is not None and current_hotel is not None
                    and typical_flight is not None and hotel_benchmark is not None
                    and float(typical_flight) > 0 and float(hotel_benchmark) > 0):
                combined_current = current_flight + current_hotel
                combined_benchmark = float(typical_flight) + float(hotel_benchmark)
                combined_discount = (combined_benchmark - combined_current) / combined_benchmark * 100
                record.update({
                    "combined_price_gbp": round(combined_current, 2),
                    "combined_benchmark_gbp": round(combined_benchmark, 2),
                    "combined_discount_percent": round(combined_discount, 1),
                    "combined_deal_status": status_for(combined_discount, "combined"),
                    "combined_benchmark_method": (
                        "google_flights_typical_low_plus_hotel_historical_median"
                        if insight and insight.get("typical_price_low_gbp") is not None
                        else "historical_flight_median_plus_hotel_median"
                    ),
                })
            else:
                record.update({
                    "combined_price_gbp": (
                        round(current_flight + current_hotel, 2)
                        if current_flight is not None and current_hotel is not None else None
                    ),
                    "combined_benchmark_gbp": None,
                    "combined_discount_percent": None,
                    "combined_deal_status": "building_combined_benchmark",
                    "combined_benchmark_method": None,
                })

        ranked = rank_record(record, insight)
        record.update(ranked)
        if insight:
            record["google_flights_price_insights"] = insight
            if record.get("kind") == "flight":
                record["benchmark_price_gbp"] = insight.get("google_flights_lowest_price_gbp")
                record["benchmark_reference_gbp"] = insight.get("typical_price_low_gbp")
            matched_insights.add(key)
        records.append(record)

    # A route insight is a standalone flight opportunity even if no hotel was
    # searched for that destination or date.
    for key, insight in insights.items():
        if key in matched_insights:
            continue
        row = {
            "kind": "flight_insight", "origin": insight.get("origin"),
            "destination": insight.get("destination"), "country": insight.get("country"),
            "start_date": insight.get("departure_date"), "end_date": insight.get("return_date"),
            "price_gbp": insight.get("google_flights_lowest_price_gbp"),
            "observed_at": insight.get("observed_at"),
            "benchmark_gbp": insight.get("typical_price_low_gbp"),
            "benchmark_price_gbp": insight.get("google_flights_lowest_price_gbp"),
            "benchmark_source": "google_flights_price_insights",
        }
        record = dict(row)
        record.update(rank_record(dict(row, kind="flight"), insight))
        record["kind"] = "flight_insight"
        record["google_flights_price_insights"] = insight
        records.append(record)

    records.sort(key=lambda r: (
        r.get("ranking_discount_percent") is None,
        -(r.get("ranking_discount_percent") or 0),
        r.get("observed_at") or ""
    ))
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deal_count": len(records),
        "strong_deal_count": sum(
            str(r.get("deal_status", "")).startswith("strong_") for r in records
        ),
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
    print(f"Deal feed built: {feed['deal_count']} records, {feed['strong_deal_count']} strong component deals")
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()
