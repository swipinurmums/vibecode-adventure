#!/usr/bin/env python3
"""Small, auditable Google Travel Explore discovery test."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--airport", choices=["MAN", "BHX", "LBA"])
    group.add_argument("--all", action="store_true", help="Scan MAN, BHX and LBA (3 API searches)")
    parser.add_argument(
        "--region",
        choices=["worldwide", "europe", "asia", "africa", "north_america", "south_america", "oceania"],
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
        print(f"No verified Google region ID is configured for: {args.region}", file=sys.stderr)
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
            print(f"  {len(rows)} destinations returned")
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors += 1
            print(f"  ERROR: {exc}", file=sys.stderr)

    if all_rows:
        csv_path = output_dir / "destinations.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    print(f"\nSaved results to: {output_dir}")
    print(f"Total destination rows: {len(all_rows)}")
    if errors:
        print(f"Airport searches with errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
