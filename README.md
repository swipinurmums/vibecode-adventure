# Vibecode Adventure

Personal holiday-bargain discovery tool. Backend first; dashboard last.

## Flight discovery
Google Travel Explore scans MAN, BHX and LBA worldwide or by region. Results include destinations, estimated return fares, outbound/return dates, stops, duration, airline and Google Travel links. Scans use the configured forward-looking travel window rather than only searching immediate departures.

## Flight-to-hotel integration
The integration workflow starts with a fresh Explore scan and passes the resulting flight rows directly to Google Hotels. Hotel check-in and check-out dates are taken from the matching flight. The current test searches at most one hotel destination, selected from flights costing no more than £250 return.

Hotel totals prefer the extracted whole-stay total after taxes and fees. If unavailable, a displayed whole-stay total is retained with tax status marked unknown. Nightly rates are stored separately and never multiplied to invent a stay total.

## Independent Google Flights price insights
The Google Flights workflow searches one exact route and date pair, then records Google's lowest available fare, typical price range, price-level label and returned price history. It classifies the lowest fare against the lower edge of the typical range (15%+ below = strong deal; below but less than 15% = below typical; inside = typical; above = above typical). The scheduled discovery workflow also captures one route-specific insight on eligible MAN scans, using a separate research allocation. Manual searches still reserve one credit from the protected personal allocation.

## Independent deal modes and ranked feed
`deal_feed.py` builds `data/deals/deals.json` with three independent modes: **flights only**, **hotels only**, and **combined flight + hotel value**. Flight records are ranked only on the flight component; hotel records are ranked only on the hotel component. A combined score is shown separately and only when both components have credible benchmarks. A hotel bargain therefore remains visible even when flight history is missing, and a flight bargain never needs a hotel search. Each record exposes its available `deal_modes`, component statuses, combined status, benchmark source, sample count and confidence. The feed does not call a trip a bargain merely because its absolute price is low.

## Automated schedule
The scheduled workflow runs four worldwide Explore scans per day: MAN at 05:00 and 17:00 UTC, BHX at 11:00 UTC, and LBA at 23:00 UTC. The MAN 17:00 slot can also capture one Google Flights route benchmark and perform one hotel search when an eligible flight candidate exists. Research-budget exhaustion skips the extra insight rather than stopping the flight scan or hotel search. GitHub may queue scheduled runs, but airport selection uses the scheduled cron slot rather than the actual start time.

## Monthly SerpApi credit protection
The planned free allowance is 250 searches/month:
- 120 automated flight-discovery searches
- 50 protected for personal/manual destination searches
- 50 hotel searches, including standalone hotel-only searches
- 30 automated route-price benchmark searches

The persistent ledger is stored in data/usage/monthly.json. It enforces each category allocation and a hard 250-search total. A reservation is committed to the repository BEFORE an API request, so failed requests are conservatively counted rather than risking an unrecorded charge. All API workflows share one GitHub Actions concurrency group to prevent simultaneous runs from racing the ledger. Automated research and hotel searches cannot consume the protected personal allocation.

**One-time setup is required before any protected workflow can make an API request.** Check the current month's total usage in your SerpApi dashboard, then run the "Set up monthly SerpApi credit ledger" workflow and enter that number as the opening baseline. Earlier usage is not inferable from this repository, so the ledger intentionally blocks requests until the baseline is reconciled. To preserve the personal and hotel allocations, all unclassified earlier usage is conservatively charged against the flight allocation. At the start of each new calendar month, reconcile again using the new month's dashboard usage. The workflow refuses to overwrite a month's existing ledger.

Reservations are counted before requests. If a workflow reserves a search and then fails before making the request, that reservation remains counted for the month. Do not edit the ledger file manually while workflows are running.

Identical exact-parameter requests may be served from SerpApi's cache, but the ledger does not assume a request will be free.

## Setup
Install dependencies with pip install -r requirements.txt. Set SERPAPI_KEY as a GitHub repository secret; never commit or paste the key into chat.

## Workflows
- **Set up monthly SerpApi credit ledger:** enter the current account usage total before the first protected scan, and reconcile monthly.
- **Explore discovery test:** reserves one flight search before running a regional scan.
- **Flight-to-hotel integration test:** reserves one flight search, then reserves one hotel search only if an eligible priced flight with valid dates exists.
- **Scheduled worldwide bargain discovery:** four flight scans daily and up to one hotel search daily, all credit-reserved before requests.
- **Manual Google Flights price insights:** one route/date search using the protected personal allocation.
- **Manual hotel-only search:** search a destination and stay dates without needing to find or supply a flight; results feed the hotel-only deal mode.
- **Unit tests:** python -m unittest discover -s tests -v

## Historical deal detection
Successful Explore and hotel workflows append observed prices to data/history/observations.jsonl. Flight historical comparisons require the same origin, destination, country, exact outbound/return dates and booking lead-time band. Route-specific Google Flights typical-price ranges provide a separate market reference when available. Hotel comparisons require the same destination, exact stay dates and duration, accommodation type, review-score band, guest count and tax basis. Hotel prices are independent of departure airport, so hotel-only searches and hotel results attached to flights can contribute to the same destination/stay benchmark. Cross-property comparisons still require matching star class and location-rating band, with at least 20 reviews for both properties; otherwise only the same property is compared. At least three earlier observations are required, and five are needed for high historical confidence. The median is used; prices at least 15% below it are strong component deals. Personal historical medians are not universal market averages.

## Remaining backend work
Next backend work is data quality, longer-term alert delivery and destination cost estimates as an optional drill-down. Destination food/transport estimates must not affect the primary deal ranking. Combined holiday scoring is calculated only when both components have credible references: the flight side can use a route-specific Google Flights typical-price range or a historical median, while the hotel side uses a comparable historical stay median. It adds those component references and compares them with the actual flight fare attached to the hotel search plus the whole-stay hotel total. This is an indicative component-based benchmark, not a paired historical package average. The feed exposes separate benchmark source and confidence fields for flight, hotel and combined scores. The dashboard comes after the backend is stable. This is a discovery tool, not a booking bot.
