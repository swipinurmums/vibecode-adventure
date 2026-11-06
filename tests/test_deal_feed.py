import unittest
from deal_feed import build_feed, latest_rows, rank_record


class DealFeedTests(unittest.TestCase):
    def test_latest_observation_wins_for_same_trip_and_property(self):
        older = {"kind":"hotel","origin":"MAN","destination":"Rome","country":"Italy",
                 "start_date":"2027-05-01","end_date":"2027-05-08","nights":7,
                 "property":"Hotel A","property_key":"hotel a","observed_at":"2026-11-01",
                 "price_gbp":200,"benchmark_gbp":300,"discount_percent":33.3,"sample_count":3}
        newer = dict(older, observed_at="2026-11-02", price_gbp=190)
        rows = latest_rows([older,newer])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["price_gbp"],190)

    def test_combined_benchmark_ranks_a_strong_combined_deal(self):
        row = {"kind":"hotel","discount_percent":20,"combined_discount_percent":18,
               "benchmark_gbp":300,"sample_count":4}
        result = rank_record(row)
        self.assertEqual(result["deal_status"],"strong_combined_deal")
        self.assertEqual(result["ranking_discount_percent"],18)

    def test_flight_insight_and_hotel_history_create_strong_combined_signal(self):
        row = {"kind":"hotel","origin":"MAN","destination":"Rome","country":"Italy",
               "start_date":"2027-05-01","end_date":"2027-05-08","nights":7,
               "property":"Hotel A","observed_at":"2026-11-01","price_gbp":200,
               "benchmark_gbp":300,"discount_percent":33.3,"sample_count":3}
        insight = {"origin":"MAN","destination":"Rome","departure_date":"2027-05-01",
                   "return_date":"2027-05-08","benchmark_status":"strong_deal",
                   "google_flights_lowest_price_gbp":80,"typical_price_low_gbp":100,"discount_vs_typical_low_percent":20,"observed_at":"2026-11-02"}
        feed = build_feed([row], {("MAN","Rome","2027-05-01","2027-05-08"):insight})
        self.assertEqual(feed["deal_count"],1)
        self.assertEqual(feed["deals"][0]["deal_status"],"strong_combined_deal")
        self.assertEqual(feed["deals"][0]["confidence"],"high")
        self.assertEqual(feed["deals"][0]["combined_price_gbp"],280.0)
        self.assertEqual(feed["deals"][0]["combined_benchmark_gbp"],400.0)
        self.assertEqual(feed["deals"][0]["combined_discount_percent"],30.0)
        self.assertEqual(feed["deals"][0]["combined_benchmark_method"],"google_flights_typical_low_plus_hotel_historical_median")
        self.assertIn("google_flights_price_insights",feed["deals"][0])

    def test_orphan_price_insight_is_included(self):
        insight = {"origin":"MAN","destination":"Tokyo","departure_date":"2027-06-01",
                   "return_date":"2027-06-08","google_flights_lowest_price_gbp":400,
                   "typical_price_low_gbp":600,"discount_vs_typical_low_percent":33.3,
                   "benchmark_status":"strong_deal","observed_at":"2026-11-06"}
        feed = build_feed([], {("MAN","Tokyo","2027-06-01","2027-06-08"):insight})
        self.assertEqual(feed["deal_count"], 1)
        self.assertEqual(feed["deals"][0]["kind"], "flight_insight")
        self.assertEqual(feed["deals"][0]["deal_status"], "strong_component_deal")

    def test_missing_benchmarks_are_not_called_deals(self):
        result = rank_record({"kind":"hotel","deal_status":"building_history"})
        self.assertEqual(result["deal_status"],"building_history")
        self.assertIsNone(result["ranking_discount_percent"])


if __name__ == "__main__":
    unittest.main()
