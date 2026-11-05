#!/usr/bin/env python3
"""Persist price observations and compare only genuinely comparable trips."""
import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

HISTORY = Path("data/history/observations.jsonl")
MIN_SAMPLES = 3


def load_history(path=HISTORY):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            if line.strip():
                rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def classify_accommodation(name, source_type=None):
    label = f"{source_type or ''} {name or ''}".casefold()
    hostel_terms = ("hostel", "generator", "clink", "jacobs inn",
                    "abbey court", "gogarty", "a&o hostel", "meininger")
    if any(term in label for term in hostel_terms):
        return "hostel"
    rental_terms = ("vacation rental", "apartment", "homestay", "guesthouse",
                    "guest house", "holiday home", "holiday rental", "villa",
                    "serviced apartment", "private room")
    if any(term in label for term in rental_terms):
        return "vacation_rental"
    return "hotel"


def rating_band(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "unrated"
    if not 1 <= score <= 5:
        return "unrated"
    if score < 3.5:
        return "below_3_5"
    if score < 4:
        return "3_5_to_4"
    if score < 4.5:
        return "4_to_4_5"
    return "4_5_plus"


def lead_time_band(start, observed_at):
    """Group fares by how far ahead the outbound date was when observed."""
    try:
        departure = datetime.strptime(start, "%Y-%m-%d").date()
        observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        days = (departure - observed.astimezone(timezone.utc).date()).days
    except (TypeError, ValueError):
        return "unknown"
    if days < 0:
        return "already_departed"
    if days <= 7:
        return "0_7_days"
    if days <= 30:
        return "8_30_days"
    if days <= 90:
        return "31_90_days"
    if days <= 180:
        return "91_180_days"
    if days <= 365:
        return "181_365_days"
    return "366_plus_days"


def comparable_lead_time_band(row):
    # Derive only when a legacy row still has its exact outbound date. Older
    # records with month-only trip data remain "unknown" and are not mixed
    # into a dated lead-time benchmark.
    return row.get("lead_time_band") or lead_time_band(
        row.get("start_date"), row.get("observed_at")
    )


def observation(kind, origin, destination, country, start, end, price,
                property_name=None, accommodation_type_value=None,
                rating=None, adults=1, tax_basis="unknown", hotel_class=None,
                location_rating=None, review_count=None):
    observed_at = datetime.now(timezone.utc).isoformat()
    try:
        nights = (datetime.strptime(end, "%Y-%m-%d") -
                  datetime.strptime(start, "%Y-%m-%d")).days
        month = datetime.strptime(start, "%Y-%m-%d").strftime("%m")
        amount = float(price)
    except (TypeError, ValueError):
        return None
    if nights <= 0 or amount <= 0:
        return None
    row = {
        "kind": kind, "origin": origin or "", "destination": destination or "",
        "country": country or "", "travel_month": month, "nights": nights,
        "start_date": start, "property": property_name, "price_gbp": amount,
        "observed_at": observed_at
    }
    if kind == "flight":
        row["lead_time_band"] = lead_time_band(start, observed_at)
    if kind == "hotel":
        try:
            guest_count = int(adults or 1)
        except (TypeError, ValueError):
            guest_count = 1
        row.update({
            "property_key": (property_name or "").strip().casefold(),
            "accommodation_type": classify_accommodation(property_name, accommodation_type_value),
            "rating_band": rating_band(rating),
            "adults": guest_count,
            "tax_basis": tax_basis or "unknown",
            "hotel_class": (int(hotel_class) if str(hotel_class or "").strip().isdigit() else None),
            "location_rating": location_rating,
            "location_rating_band": location_rating_band(location_rating),
            "review_count": (int(review_count) if str(review_count or "").strip().isdigit() else 0)
        })
    return row


def location_rating_band(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if not 1 <= score <= 5:
        return "unknown"
    lower = int((score - 1) * 2) / 2 + 1
    return f"{lower:.1f}_{lower + 0.5:.1f}"


def comparable_hotel_value(row, key):
    if key == "hotel_class":
        try:
            return int(row.get(key))
        except (TypeError, ValueError):
            return None
    if key == "location_rating_band":
        return row.get(key) or location_rating_band(row.get("location_rating"))
    if key == "review_count":
        try:
            return int(row.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    if key == "accommodation_type":
        return row.get(key) or classify_accommodation(row.get("property"))
    if key == "rating_band":
        return row.get(key) or "unrated"
    if key == "tax_basis":
        return row.get(key) or "unknown"
    if key == "adults":
        try:
            return int(row.get(key) or 1)
        except (TypeError, ValueError):
            return 1
    if key == "property_key":
        return (row.get(key) or row.get("property") or "").strip().casefold()
    return row.get(key)


def compare(history, current, kind):
    keys = ("origin", "destination", "country", "travel_month", "nights")
    # Flight fares are comparable only when observed at a similar booking
    # lead time. Legacy rows derive this from their original observation date.
    # Keep at most one observation per UTC day for each hotel property (or
    # per route for flights). Re-running an identical scan must not inflate
    # the benchmark sample count with duplicate same-day prices.
    samples_by_key = {}
    for row in history:
        if row.get("kind") != kind or any(row.get(k) != current.get(k) for k in keys):
            continue
        if kind == "flight" and comparable_lead_time_band(row) != comparable_lead_time_band(current):
            continue
        if kind == "hotel":
            hotel_keys = ("accommodation_type", "rating_band", "adults", "tax_basis")
            if any(comparable_hotel_value(row, k) != comparable_hotel_value(current, k)
                   for k in hotel_keys):
                continue
            # Cross-property matching needs stronger quality evidence than a
            # broad review-score band: same star class and location-score band,
            # with at least 20 reviews for both properties. Otherwise only
            # compare a property against its own history.
            same_property = (comparable_hotel_value(row, "property_key") ==
                             comparable_hotel_value(current, "property_key"))
            quality_keys = ("hotel_class", "location_rating_band")
            quality_known = all(
                comparable_hotel_value(row, k) is not None and
                comparable_hotel_value(current, k) is not None and
                comparable_hotel_value(row, k) != "unknown" and
                comparable_hotel_value(current, k) != "unknown"
                for k in quality_keys
            )
            enough_reviews = (
                comparable_hotel_value(row, "review_count") >= 20 and
                comparable_hotel_value(current, "review_count") >= 20
            )
            if not same_property and not (quality_known and enough_reviews):
                continue
            if not same_property and any(
                comparable_hotel_value(row, k) != comparable_hotel_value(current, k)
                for k in quality_keys
            ):
                continue
            if comparable_hotel_value(current, "rating_band") == "unrated" and not same_property:
                continue
        try:
            value = float(row["price_gbp"])
        except (KeyError, TypeError, ValueError):
            continue
        if value > 0:
            observed = str(row.get("observed_at") or "")
            day = observed[:10] if len(observed) >= 10 else observed
            if kind == "hotel":
                property_key = (row.get("property") or "").strip().casefold()
                sample_key = (day, property_key)
            else:
                sample_key = (day,)
            samples_by_key[sample_key] = value
    prices = list(samples_by_key.values())
    if len(prices) < MIN_SAMPLES:
        return {"sample_count": len(prices), "benchmark_gbp": None,
                "discount_percent": None, "deal_status": "building_history"}
    median = statistics.median(prices)
    discount = (median - float(current["price_gbp"])) / median * 100
    status = ("strong_deal" if discount >= 15 else
              ("below_typical" if discount > 0 else "not_below_typical"))
    return {"sample_count": len(prices), "benchmark_gbp": round(median, 2),
            "discount_percent": round(discount, 1), "deal_status": status}


def append_history(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ingest_explore(source, history_path=HISTORY):
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    airport = payload.get("search_parameters", {}).get("departure_id", "")
    history = load_history(history_path)
    rows = []
    for item in payload.get("destinations", []):
        if item.get("flight_price") is None:
            continue
        row = observation("flight", airport, item.get("name"), item.get("country"),
                          item.get("start_date"), item.get("end_date"), item["flight_price"])
        if row is None:
            continue
        row.update(compare(history, row, "flight"))
        rows.append(row)
    append_history(history_path, rows)
    return rows


def ingest_hotels(source, history_path=HISTORY):
    with Path(source).open(encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))
    history = load_history(history_path)
    rows = []
    for item in source_rows:
        row = observation(
            "hotel", item.get("origin"), item.get("destination"), item.get("country"),
            item.get("flight_departure_date"), item.get("flight_return_date"),
            item.get("total_price_gbp"), item.get("property"),
            item.get("accommodation_type"), item.get("rating"), item.get("adults", 1),
            item.get("tax_basis", "unknown"), item.get("hotel_class"),
            item.get("location_rating"), item.get("review_count")
        )
        if row is None:
            continue
        row.update(compare(history, row, "hotel"))
        rows.append(row)
    append_history(history_path, rows)
    return rows


def report(rows):
    print(f"Historical observations added: {len(rows)}")
    for row in rows[:20]:
        benchmark = row["benchmark_gbp"]
        detail = (f"building history ({row['sample_count']}/{MIN_SAMPLES} comparable past observations)"
                  if benchmark is None else
                  f"{row['discount_percent']:+.1f}% vs median £{benchmark:.2f} ({row['sample_count']} samples)")
        label = row.get("property") or row["destination"]
        if row["kind"] == "hotel":
            label += f" [{row.get('accommodation_type')}, {row.get('rating_band')}]"
        print(f"{row['kind']}: {label} £{row['price_gbp']:.2f} — {row['deal_status']} — {detail}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    explore = commands.add_parser("ingest-explore")
    explore.add_argument("--file", required=True)
    hotels = commands.add_parser("ingest-hotels")
    hotels.add_argument("--file", required=True)
    args = parser.parse_args()
    rows = ingest_explore(args.file) if args.command == "ingest-explore" else ingest_hotels(args.file)
    report(rows)


if __name__ == "__main__":
    main()
