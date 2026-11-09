import argparse, csv, json, os
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv

API_URL = "https://serpapi.com/search"


def valid_nights(start, end):
    try:
        n = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


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


def normalise(payload, flight, adults):
    nights = valid_nights(flight["departure_date"], flight["return_date"])
    rows = []
    for p in payload.get("properties", []):
        total = p.get("total_rate") or {}
        after = total.get("extracted_after_taxes_fees")
        shown = total.get("extracted_display_price")
        before = total.get("extracted_before_taxes_fees")
        price = after if after is not None else shown
        basis = "after_taxes_and_fees" if after is not None else (
            "displayed_total_tax_status_unknown" if shown is not None else "no_total_stay_price")
        rows.append({
            "origin": flight["origin"], "destination": flight["destination"],
            "country": flight.get("country", ""),
            "flight_departure_date": flight["departure_date"],
            "flight_return_date": flight["return_date"],
            "flight_price_gbp": flight.get("flight_price_gbp"),
            "flight_stops": flight.get("stops"),
            "flight_airline": flight.get("airline"),
            "nights": nights, "adults": adults,
            "property": p.get("name"), "accommodation_type": classify_accommodation(
                p.get("name"), p.get("type")),
            "rating": p.get("overall_rating"),
            "review_count": p.get("reviews"),
            "hotel_class": p.get("extracted_hotel_class"),
            "location_rating": p.get("location_rating"),
            "latitude": (p.get("gps_coordinates") or {}).get("latitude"),
            "longitude": (p.get("gps_coordinates") or {}).get("longitude"),
            "total_price_gbp": price, "tax_basis": basis,
            "before_tax_gbp": before,
            "nightly_price_gbp": (p.get("rate_per_night") or {}).get("extracted_display_price"),
            "source": p.get("source"), "url": p.get("link")
        })
    return sorted(rows, key=lambda r: (r["total_price_gbp"] is None,
                                       r["total_price_gbp"] if r["total_price_gbp"] is not None else float("inf")))


def hotel_search_query(flight):
    parts = [flight.get("destination"), flight.get("country"), flight.get("continent")]
    result = []
    for part in parts:
        value = (part or "").strip()
        if value and value.casefold() not in [x.casefold() for x in result]:
            result.append(value)
    return ", ".join(result)


def fetch_one(api_key, flight, adults):
    params = {
        "engine": "google_hotels",
        "q": hotel_search_query(flight),
        "check_in_date": flight["departure_date"],
        "check_out_date": flight["return_date"],
        "adults": adults, "children": 0,
        "gl": "uk", "hl": "en", "currency": "GBP", "api_key": api_key
    }
    response = requests.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error") or payload.get("search_metadata", {}).get("status") == "Error":
        raise RuntimeError(payload.get("error") or "SerpApi hotel search failed")
    return payload


def load_flight_candidates(path, max_flight_price):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    candidates = []
    for row in rows:
        destination = (row.get("destination") or "").strip()
        start, end = row.get("departure_date"), row.get("return_date")
        if not destination or not valid_nights(start, end):
            continue
        try:
            price = float(str(row.get("flight_price_gbp", "")).replace(",", "").replace("£", "").strip())
        except (TypeError, ValueError):
            continue
        if price > max_flight_price:
            continue
        row["flight_price_gbp"] = price
        candidates.append(row)
    candidates.sort(key=lambda r: r["flight_price_gbp"])
    return candidates


def main():
    ap = argparse.ArgumentParser(description="Search hotels from flight candidates or independently by destination and stay dates.")
    ap.add_argument("--from-csv", help="Explore scanner destinations.csv")
    ap.add_argument("--continent", choices=["Africa", "Asia", "Europe", "North America", "South America", "Oceania"])
    ap.add_argument("--destination", default="", help="Optional city or destination to narrow a hotel-only search")
    ap.add_argument("--country", default="", help="Optional country to narrow a hotel-only search")
    ap.add_argument("--check-in", help="Hotel-only check-in date (YYYY-MM-DD)")
    ap.add_argument("--check-out", help="Hotel-only check-out date (YYYY-MM-DD)")
    ap.add_argument("--max-searches", type=int, default=1,
                    help="Maximum hotel API calls in this run; keep at 1 for the integration test.")
    ap.add_argument("--max-flight-price", type=float, default=250,
                    help="Only consider flights at or below this GBP return price.")
    ap.add_argument("--adults", type=int, default=1)
    args = ap.parse_args()
    if args.max_searches < 1 or args.adults < 1:
        ap.error("--max-searches and --adults must be positive")
    load_dotenv()
    key = os.getenv("SERPAPI_KEY")
    if not key or key == "replace_me":
        raise SystemExit("SERPAPI_KEY is missing")
    if args.continent:
        if args.from_csv:
            ap.error("--continent cannot be combined with --from-csv")
        if not args.check_in or not args.check_out or not valid_nights(args.check_in, args.check_out):
            ap.error("--continent requires valid --check-in and --check-out dates")
        city = args.destination.strip()
        country = args.country.strip()
        candidates = [{
            "origin": "HOTEL_ONLY", "destination": city or country or args.continent,
            "country": country, "continent": args.continent,
            "departure_date": args.check_in, "return_date": args.check_out,
            "flight_price_gbp": None, "stops": None, "airline": None,
        }]
    else:
        if not args.from_csv:
            ap.error("Use --from-csv for flight-led searches or --continent for hotel-only searches")
        if args.destination or args.country or args.check_in or args.check_out:
            ap.error("--destination/--country/--check-in/--check-out require --continent")
        candidates = load_flight_candidates(args.from_csv, args.max_flight_price)
    if not candidates:
        print("No eligible priced flight rows with valid future trip dates. No hotel searches made.")
        return 0
    selected = candidates[:args.max_searches]
    print(f"Eligible flight candidates: {len(candidates)}; hotel searches allowed this run: {args.max_searches}")
    root = Path("data/hotels") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root.mkdir(parents=True, exist_ok=True)
    for index, flight in enumerate(selected, 1):
        city = flight["destination"]
        country = flight.get("country", "")
        start, end = flight["departure_date"], flight["return_date"]
        label = "hotel-only search" if flight.get("flight_price_gbp") is None else "flight £" + str(round(float(flight["flight_price_gbp"])))
        print("\n[" + str(index) + "/" + str(len(selected)) + "] " + city + ", " + country + " | " + label + " | " + start + " to " + end)
        payload = fetch_one(key, flight, args.adults)
        folder = root / f"{index:02d}-{city.lower().replace(' ', '-')}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "raw.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        rows = normalise(payload, flight, args.adults)
        fields = list(rows[0]) if rows else [
            "origin","destination","country","flight_departure_date","flight_return_date",
            "flight_price_gbp","flight_stops","flight_airline","nights","adults","property",
            "accommodation_type","rating","review_count","hotel_class","location_rating",
            "latitude","longitude","total_price_gbp","tax_basis","before_tax_gbp",
            "nightly_price_gbp","source","url"]
        with (folder / "hotels.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        priced = [r for r in rows if r["total_price_gbp"] is not None]
        print(f"Properties: {len(rows)} | whole-stay prices: {len(priced)}")
        for rank, row in enumerate(priced[:5], 1):
            print(f"{rank}. {row['property'] or 'Unnamed'} | £{float(row['total_price_gbp']):.2f} total | {row['tax_basis']}")
            if row["url"]:
                print(f"   {row['url']}")
        if not priced:
            print("No whole-stay property totals returned; nightly prices were not converted into totals.")
    print(f"Hotel results saved under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
