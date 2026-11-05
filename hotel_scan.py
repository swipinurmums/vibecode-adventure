import argparse, csv, json, os
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv

def days(a, b):
    n = (date.fromisoformat(b) - date.fromisoformat(a)).days
    if n < 1:
        raise ValueError("Check-out must be after check-in")
    return n

def normalise(payload, city, country, start, end, adults):
    nights = days(start, end)
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
            "destination": city, "country": country, "check_in": start,
            "check_out": end, "nights": nights, "adults": adults,
            "property": p.get("name"), "rating": p.get("overall_rating"),
            "total_price_gbp": price, "tax_basis": basis,
            "before_tax_gbp": before, "nightly_price_gbp": (p.get("rate_per_night") or {}).get("extracted_display_price"),
            "source": p.get("source"), "url": p.get("link")
        })
    return sorted(rows, key=lambda r: (r["total_price_gbp"] is None, r["total_price_gbp"] or float("inf")))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--country", default="")
    ap.add_argument("--check-in", required=True)
    ap.add_argument("--check-out", required=True)
    ap.add_argument("--adults", type=int, default=1)
    a = ap.parse_args()
    if a.adults < 1:
        ap.error("--adults must be at least 1")
    try:
        nights = days(a.check_in, a.check_out)
    except ValueError as e:
        ap.error(str(e))
    load_dotenv()
    key = os.getenv("SERPAPI_KEY")
    if not key or key == "replace_me":
        raise SystemExit("SERPAPI_KEY is missing")
    params = {"engine":"google_hotels", "q":", ".join(x for x in (a.city,a.country) if x),
              "check_in_date":a.check_in, "check_out_date":a.check_out,
              "adults":a.adults, "children":0, "gl":"uk", "hl":"en",
              "currency":"GBP", "api_key":key}
    response = requests.get("https://serpapi.com/search", params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise SystemExit(payload["error"])
    folder = Path("data/hotels") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "raw.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rows = normalise(payload, a.city, a.country, a.check_in, a.check_out, a.adults)
    fields = list(rows[0]) if rows else ["destination","country","check_in","check_out","nights","adults","property","rating","total_price_gbp","tax_basis","before_tax_gbp","nightly_price_gbp","source","url"]
    with (folder / "hotels.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    priced = [r for r in rows if r["total_price_gbp"] is not None]
    print(f"{a.city}, {a.country}: {nights} nights; {len(rows)} properties, {len(priced)} with whole-stay prices")
    for i, r in enumerate(priced[:10], 1):
        print(f'{i}. {r["property"]}: £{float(r["total_price_gbp"]):.2f} total ({r["tax_basis"]})')
        if r["url"]: print(r["url"])
    print(f"Saved to {folder}")

if __name__ == "__main__":
    main()
