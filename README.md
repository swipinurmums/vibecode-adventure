# Vibecode Adventure

Personal holiday-bargain discovery tool. Backend first; dashboard last.

## Flight discovery
Google Travel Explore scans MAN, BHX and LBA worldwide or by region. Results include destinations, estimated return fares, outbound/return dates, stops, duration, airline and Google Travel links. The separate Google Flights Deals API for flexible 3–14-day trips remains planned.

## Flight-to-hotel integration
The integration workflow starts with a fresh Explore scan and passes the resulting flight rows directly to Google Hotels. Hotel check-in and check-out dates are taken from the matching flight. The current test searches at most one hotel destination, selected from flights costing no more than £250 return.

Hotel totals prefer the extracted whole-stay total after taxes and fees. If unavailable, a displayed whole-stay total is retained with tax status marked unknown. Nightly rates are stored separately and never multiplied to invent a stay total.

## Monthly SerpApi credit protection
The planned free allowance is 250 searches/month:
- 120 automated flight searches
- 50 protected for future personal/manual destination searches
- 80 for hotel comparisons and controlled development

The persistent ledger is stored in data/usage/monthly.json. It enforces each category allocation and a hard 250-search total. A reservation is committed to the repository BEFORE an API request, so failed requests are conservatively counted rather than risking an unrecorded charge. All API workflows share one GitHub Actions concurrency group to prevent simultaneous runs from racing the ledger. Flight and hotel workflows cannot consume the protected personal allocation.

**One-time setup is required before any protected workflow can make an API request.** Check the current month's total usage in your SerpApi dashboard, then run the "Set up monthly SerpApi credit ledger" workflow and enter that number as the opening baseline. Earlier usage is not inferable from this repository, so the ledger intentionally blocks requests until the baseline is reconciled. To preserve the personal and hotel allocations, all unclassified earlier usage is conservatively charged against the flight allocation. At the start of each new calendar month, reconcile again using the new month's dashboard usage. The workflow refuses to overwrite a month's existing ledger.

Reservations are counted before requests. If a workflow reserves a search and then fails before making the request, that reservation remains counted for the month. Do not edit the ledger file manually while workflows are running.

Identical exact-parameter requests may be served from SerpApi's cache, but the ledger does not assume a request will be free.

## Setup
Install dependencies with pip install -r requirements.txt. Set SERPAPI_KEY as a GitHub repository secret; never commit or paste the key into chat.

## Workflows
- **Set up monthly SerpApi credit ledger:** enter the current account usage total before the first protected scan, and reconcile monthly.
- **Explore discovery test:** reserves one flight search before running a regional scan.
- **Flight-to-hotel integration test:** reserves one flight search, then reserves one hotel search only if an eligible priced flight with valid dates exists.
- **Unit tests:** python -m unittest discover -s tests -v

## Historical deal detection
Successful Explore and hotel workflows append observed prices to data/history/observations.jsonl. Flight comparisons require the same origin, destination, country, travel month and trip length. Hotel comparisons additionally require the same destination trip profile, accommodation type (hotel, hostel or vacation rental), review-score band and guest count, but no longer require the exact same property. Review-score bands are broad to avoid treating tiny rating differences as meaningful. A benchmark is withheld until at least three comparable earlier observations exist. The median is used, and prices at least 15% below it are marked strong_deal. This is an early personal history benchmark, not a market-wide average; tax basis should also be considered when comparing hotel totals.

## Remaining backend work
Improve flight benchmarks with dedicated Google Flights price insights, build combined holiday deal scoring and alerts. Destination food/transport estimates are a later drill-down detail, not a primary ranking factor. Dashboard comes last. This is a discovery tool, not a booking bot.
