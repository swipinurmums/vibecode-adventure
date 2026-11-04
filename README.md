# Vibecode Adventure

A personal holiday-bargain discovery tool. The first milestone tests whether Google Travel Explore can find useful destinations worldwide from Manchester (MAN), Birmingham (BHX), and Leeds Bradford (LBA).

## Current milestone: global discovery proof of concept

- Search Google Travel Explore independently from each departure airport.
- Start with an unrestricted worldwide search (no arrival region filter).
- Save raw JSON responses and a readable CSV for inspection.
- Preserve Google Travel links so fares can be checked manually.
- Do not rank by Google discount percentage alone.
- Do not calculate a holiday-value score yet: the meaning and time basis of Explore's `hotel_price` needs validation first.

## Requirements

- Python 3.10+
- A SerpApi account and API key

## Setup

1. Clone this repository.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add your SerpApi key. **Never commit `.env` or paste your API key into chat.**
4. Run a single airport first:

   ```bash
   python explore_scan.py --airport MAN
   ```

5. Run all three airports:

   ```bash
   python explore_scan.py --all
   ```

Output is written to `data/runs/<timestamp>/`. Raw responses are retained so we can inspect the exact fields and compare the regional coverage.

## Search settings

The initial scan uses:
- Engine: `google_travel_explore`
- Origin: one of MAN, BHX, LBA
- UK localisation, GBP, English
- Economy, return flights
- Flexible dates within Google Explore's supported window
- Trip duration: Explore exposes flexible duration presets (weekend / 1 week / 2 weeks), not the exact 3–14 day range used by the Deals API. This is recorded as a limitation for the first test.

The script deliberately makes one request per airport. Avoid repeatedly forcing fresh searches while testing: SerpApi's exact-parameter cache can serve repeat requests for free within its cache window.

## Regional discovery

Explore supports `arrival_area_id` using Google Knowledge Graph location IDs. Europe is documented by SerpApi as `/m/02j9z`. Other continent IDs should be verified against Google's/SerpApi's location data before being added; this project does not guess opaque IDs.

The first run establishes the unrestricted worldwide baseline. Next we will validate region IDs and compare Asia, Africa, the Americas and Oceania against that baseline, while watching the 250-search monthly allowance.

## Important caveats

- Explore returns Google's surfaced destination suggestions, not every possible fare.
- Prices and availability can change; always open the Google Flights link before making a decision.
- A low airfare is not automatically a cheap holiday.
- `hotel_price` is stored as supplied but is not yet treated as a nightly rate or total stay cost.
- This is a discovery and alerting tool, not a booking bot.
