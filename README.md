# Vibecode Adventure

Personal holiday-bargain discovery tool. Backend first; dashboard last.

## Flight discovery
Google Travel Explore scans MAN, BHX and LBA worldwide or by region. Results include destinations, estimated return fares, outbound/return dates, stops, duration, airline and Google Travel links. The separate Google Flights Deals API for flexible 3–14-day trips remains planned.

## Flight-to-hotel integration
The Flight-to-hotel integration test workflow starts with a fresh Explore scan. It passes the resulting CSV directly to hotel_scan.py. No check-in or check-out dates are entered manually: the dates come from each discovered flight row.

The current integration test deliberately makes at most ONE Google Hotels request, for the cheapest eligible flight costing no more than £250 return. It uses the exact flight dates, and records the matched flight details alongside each hotel result. If no eligible priced flight with valid dates is found, no hotel search is made.

Hotel totals prefer the extracted whole-stay total after taxes and fees. If that is unavailable, a displayed whole-stay total is retained with tax status marked unknown. Nightly rates are stored separately and never multiplied to invent a stay total.

## SerpApi credit policy
The free allowance is 250 searches/month. Proposed planning allocation: 120 automated flight searches, 50 reserved for personal/manual destination searches, 80 for hotel comparisons and development. These are NOT yet enforced by a persistent monthly ledger. The integrated workflow is manual-dispatch only and makes one flight search plus at most one hotel search. Do not enable scheduled hotel searches or increase the hotel-search cap until monthly usage accounting and reserve enforcement exist. Identical cached requests within one hour may be free; the code does not force fresh searches.

## Setup
Install dependencies with pip install -r requirements.txt. Set SERPAPI_KEY as a GitHub repository secret; never commit or paste the key into chat.

## Workflows
- Explore discovery test: one regional flight scan.
- Flight-to-hotel integration test: one flight scan followed by at most one hotel search for the cheapest eligible flight, using its discovered dates.
- Unit tests: python -m unittest discover -s tests -v

## Remaining backend work
Destination food/transport estimates, total-holiday scoring, monthly credit ledger/reserve enforcement, hotel matching across multiple selected flights, Google Flights Deals integration, historical deal tracking and alerts. Dashboard comes last. This is a discovery tool, not a booking bot.
