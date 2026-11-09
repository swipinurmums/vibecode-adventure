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

    def test_flight_and_hotel_are_ranked_independently_from_combined_value(self):
        row = {"kind":"hotel","discount_percent":20,"combined_discount_percent":18,
               "benchmark_gbp":300,"sample_count":4}
        result = rank_record(row)
        self.assertEqual(result["deal_status"],"strong_hotel_deal")
        self.assertEqual(result["ranking_discount_percent"],20)
        self.assertEqual(result["combined_deal_status"],"strong_combined_deal")
        self.assertEqual(result["deal_modes"],["hotel","combined"])

    def test_hotel_only_deal_does_not_require_or_invent_flight_benchmark(self):
        row = {"kind":"hotel","discount_percent":22,"benchmark_gbp":300,
               "sample_count":4,"price_gbp":234}
        feed = build_feed([row], {})
        deal = feed["deals"][0]
        self.assertEqual(deal["deal_status"],"strong_hotel_deal")
        self.assertEqual(deal["hotel_deal_status"],"strong_hotel_deal")
        self.assertEqual(deal["combined_deal_status"],"building_combined_benchmark")
        self.assertIsNone(deal["combined_discount_percent"])
        self.assertEqual(deal["deal_modes"],["hotel"])

    def test_google_flight_insight_and_hotel_history_create_separate_and_combined_signals(self):
        row = {"kind":"hotel","origin":"MAN","destination":"Rome","country":"Italy",
               "start_date":"2027-05-01","end_date":"2027-05-08","nights":7,
               "property":"Hotel A","observed_at":"2026-11-01","price_gbp":200,
               "flight_price_gbp":80,"benchmark_gbp":300,"discount_percent":33.3,
               "flight_benchmark_gbp":100,"sample_count":3}
        insight = {"origin":"MAN","destination":"Rome","departure_date":"2027-05-01",
                   "return_date":"2027-05-08","benchmark_status":"strong_deal",
                   "google_flights_lowest_price_gbp":75,"typical_price_low_gbp":100,
                   "discount_vs_typical_low_percent":20,"observed_at":"2026-11-02"}
        feed = build_feed([row], {("MAN","Rome","2027-05-01","2027-05-08"):insight})
        deal = feed["deals"][0]
        self.assertEqual(feed["deal_count"],1)
        self.assertEqual(deal["deal_status"],"strong_hotel_deal")
        self.assertEqual(deal["flight_deal_status"],"strong_flight_deal")
        self.assertEqual(deal["combined_deal_status"],"strong_combined_deal")
        self.assertEqual(deal["confidence"],"high")
        self.assertEqual(deal["combined_price_gbp"],280.0)
        self.assertEqual(deal["combined_benchmark_gbp"],400.0)
        self.assertEqual(deal["combined_discount_percent"],30.0)
        self.assertEqual(deal["combined_benchmark_method"],
                         "google_flights_typical_low_plus_hotel_historical_median")
        self.assertIn("google_flights_price_insights",deal)
        self.assertEqual(deal["deal_modes"],["hotel","combined"])

    def test_orphan_price_insight_is_a_standalone_flight_deal(self):
        insight = {"origin":"MAN","destination":"Tokyo","departure_date":"2027-06-01",
                   "return_date":"2027-06-08","google_flights_lowest_price_gbp":400,
                   "typical_price_low_gbp":600,"discount_vs_typical_low_percent":33.3,
                   "benchmark_status":"strong_deal","observed_at":"2026-11-06"}
        feed = build_feed([], {("MAN","Tokyo","2027-06-01","2027-06-08"):insight})
        deal = feed["deals"][0]
        self.assertEqual(feed["deal_count"],1)
        self.assertEqual(deal["kind"],"flight_insight")
        self.assertEqual(deal["deal_status"],"strong_flight_deal")
        self.assertEqual(deal["deal_modes"],["flight"])

    def test_missing_benchmarks_are_not_called_deals(self):
        result = rank_record({"kind":"hotel","deal_status":"building_history"})
        self.assertEqual(result["deal_status"],"building_hotel_benchmark")
        self.assertIsNone(result["ranking_discount_percent"])


if __name__ == "__main__":
    unittest.main()
