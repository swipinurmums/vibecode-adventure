#!/usr/bin/env python3
"""Google Travel Explore discovery scan with a readable, date-aware summary."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

API_URL = "https://serpapi.com/search"
REGIONS = [
    "worldwide", "europe", "asia", "africa",
    "north_america", "south_america", "oceania",
]


def load_config() -> dict[str, Any]:
    return json.loads(Path("config.json").read_text(encoding="utf-8"))


def fetch_explore(
    api_key: str, airport: str, config: dict[str, Any], region_id: str | None
) -> dict[str, Any]:
    params = {
        "engine": "google_travel_explore",
        "departure_id": airport,
        "gl": config["localisation"]["gl"],
        "hl": config["localisation"]["hl"],
        "currency": config["localisation"]["currency"],
        **config["flight"],
        "api_key": api_key,
    }
    if region_id:
        params["arrival_area_id"] = region_id

    response = requests.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    metadata = payload.get("search_metadata", {})
    if metadata.get("status") == "Error" or payload.get("error"):
        raise RuntimeError(payload.get("error") or "SerpApi reported an error")

    return payload


def normalise_destinations(payload: dict[str, Any], airport: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("destinations", []):
        rows.append({
            "origin": airport,
            "destination": item.get("name"),
            "country": item.get("country"),
            "departure_date": item.get("start_date"),
            "return_date": item.get("end_date"),
            "flight_price_gbp": item.get("flight_price"),
            # Stored raw until the hotel-price basis is verified.
            "hotel_price_raw": item.get("hotel_price"),
            "flight_duration_minutes": item.get("flight_duration"),
            "stops": item.get("number_of_stops"),
            "airline": item.get("airline"),
            "google_travel_url": item.get("link"),
            "destination_id": item.get("destination_id"),
        })
    return rows


def price_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").replace("£", "").strip())
    except (TypeError, ValueError):
        return None


def format_duration(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (int, float)):
        hours, minutes = divmod(int(value), 60)
        return f"{hours}h {minutes}m" if hours else f"{minutes}m"
    return str(value)


def print_summary(rows: list[dict[str, Any]], airport: str, region: str) -> None:
    priced = [row for row in rows if price_number(row.get("flight_price_gbp")) is not None]
    unpriced = len(rows) - len(priced)
    print(f"\n=== {airport} | {region.replace('_', ' ').title()} ===")
    print(f"Destinations: {len(rows)} | Priced: {len(priced)} | No price: {unpriced}")

    dates = [
        date
        for row in rows
        for date in (row.get("departure_date"), row.get("return_date"))
        if date
    ]
    if dates:
        print(f"Date range in results: {min(dates)} to {max(dates)}")

    if not priced:
        print("No priced destinations in this response.")
        return

    priced.sort(key=lambda row: price_number(row.get("flight_price_gbp")) or float("inf"))
    print("\nCheapest 10 priced destinations (flight price only):")
    for index, row in enumerate(priced[:10], start=1):
        destination = row.get("destination") or "Unknown destination"
        country = row.get("country") or ""
        label = f"{destination}, {country}" if country else destination
        price = price_number(row.get("flight_price_gbp"))
        outbound = row.get("departure_date") or "date TBC"
        inbound = row.get("return_date") or "date TBC"
        stops = row.get("stops")
        stops_label = f"{stops} stop(s)" if stops is not None else "stops TBC"
        duration = format_duration(row.get("flight_duration_minutes"))
        airline = row.get("airline") or "airline TBC"
        print(
            f"{index:>2}. {label} | £{price:,.0f} return | "
            f"{outbound} → {inbound} | {stops_label} | {duration} | {airline}"
        )
        link = row.get("google_travel_url")
        if link:
            print(f"    {link}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--airport", choices=["MAN", "BHX", "LBA"])
    group.add_argument("--all", action="store_true", help="Scan MAN, BHX and LBA (3 API searches)")
    parser.add_argument(
        "--region",
        choices=REGIONS,
        default="worldwide",
        help="Worldwide baseline or a configured continent/region.",
    )
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key or api_key == "replace_me":
        print("Missing SERPAPI_KEY. Copy .env.example to .env and add your key.", file=sys.stderr)
        return 2

    config = load_config()
    airports = config["departure_airports"] if args.all else [args.airport]
    region_id = config["regions"].get(args.region)

    if args.region != "worldwide" and not region_id:
        print(f"No region ID is configured for: {args.region}", file=sys.stderr)
        return 2

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path("data/runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    errors = 0
    for airport in airports:
        print(f"Searching {airport} ({args.region})...")
        try:
            # Exactly one API request per airport per run.
            payload = fetch_explore(api_key, airport, config, region_id)
            (output_dir / f"{airport}_{args.region}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            rows = normalise_destinations(payload, airport)
            all_rows.extend(rows)
            print_summary(rows, airport, args.region)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors += 1
            print(f"  ERROR: {exc}", file=sys.stderr)

    if all_rows:
        csv_path = output_dir / "destinations.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    print(f"\nSaved raw responses and CSV to: {output_dir}")
    print(f"Total destination rows: {len(all_rows)}")
    if errors:
        print(f"Airport searches with errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
