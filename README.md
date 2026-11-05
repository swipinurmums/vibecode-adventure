# Vibecode Adventure

Personal holiday-bargain discovery tool. Backend first; dashboard last.

## Flight discovery
Google Travel Explore scans MAN, BHX and LBA worldwide or by region. Results include destinations, estimated return fares, outbound/return dates, stops, duration, airline and Google Travel links. The separate Google Flights Deals API for flexible 3–14-day trips remains planned.

## Flight-to-hotel integration
The integration workflow starts with a fresh Explore scan and passes the resulting flight rows directly to Google Hotels. Hotel check-in and check-out dates are taken from the matching flight. The current test searches at most one hotel destination, selected from flights costing no more than £250 return.

Hotel totals prefer the extracted whole-stay total after taxes and fees. If unavailable, a displayed whole-stay total is retained with tax status marked unknown. Nightly rates are stored separately and never multiplied to invent a stay total.

## Monthly SerpApi credit protection
The free allowance is planned around 250 searches/month:
- 120 automated flight searches
- 50 protected for future personal/manual destination searches
- 80 for hotel comparisons and controlled development

The persistent ledger is stored in data/usage/monthly.json. It enforces each category allocation and a hard 250-search total. A reservation is committed to the repository BEFORE an API request, so failed requests are conservatively counted rather than risking an unrecorded charge. All API workflows share one GitHub Actions concurrency group to prevent simultaneous runs from racing the ledger. The personal allocation cannot be consumed by flight or hotel workflows.

**One-time setup is required before any protected workflow can make an API request.** Check the current month's total usage in your SerpApi dashboard, then run the "Set up monthly SerpApi credit ledger" workflow and enter that number as the opening baseline. Previous searches are not inferable from this repository, so the ledger intentionally blocks requests until the baseline is reconciled. At the start of each new calendar month, reconcile again using the new month's dashboard usage. The baseline is deducted from the global 250 cap; new workflow reservations are also limited by their category allocations.

Reservations are counted before requests. This is deliberately conservative: if a workflow reserves a search and then fails before making the request, that reservation remains used until the monthly baseline is manually reconciled. Do not edit the ledger file manually while workflows are running.

Identical exact-parameter requests may be served from SerpApi's cache, but the ledger does not assume a request will be free.

## Setup
Install dependencies with pip install -r requirements.txt. Set SERPAPI_KEY as a GitHub repository secret; never commit or paste the key into chat.

## Workflows
- **Set up monthly SerpApi credit ledger:** enter the current account usage total before the first protected scan, and reconcile monthly.
- **Explore discovery test:** reserves one flight search before running a regional scan.
- **Flight-to-hotel integration test:** reserves one flight search, then reserves one hotel search only if an eligible priced flight with valid dates exists.
- **Unit tests:** python -m unittest discover -s tests -v

## Remaining backend work
Destination food/transport costs, total-holiday scoring, broader hotel comparisons, Google Flights Deals integration, historical deal tracking and alerts. Dashboard comes last. This is a discovery tool, not a booking bot.
