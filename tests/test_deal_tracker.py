import csv
import json
import tempfile
import unittest
from pathlib import Path

from deal_tracker import observation, compare, ingest_explore, ingest_hotels, classify_accommodation, append_history


class DealTrackerTests(unittest.TestCase):
    def test_three_comparable_observations_use_median(self):
        current = observation("flight", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08", 100)
        history = [dict(current, price_gbp=p, observed_at=str(i)) for i, p in enumerate((150, 140, 130))]
        result = compare(history, current, "flight")
        self.assertEqual(result["benchmark_gbp"], 140)
        self.assertEqual(result["discount_percent"], 28.6)
        self.assertEqual(result["deal_status"], "strong_deal")


    def test_flight_comparison_excludes_different_booking_lead_time_bands(self):
        current = observation("flight", "MAN", "Rome", "Italy",
                              "2027-05-01", "2027-05-08", 100)
        history = [
            dict(current, price_gbp=150, observed_at="2026-11-05T08:00:00+00:00",
                 lead_time_band=current["lead_time_band"]),
            dict(current, price_gbp=140, observed_at="2026-11-04T08:00:00+00:00",
                 lead_time_band=current["lead_time_band"]),
            dict(current, price_gbp=130, observed_at="2026-11-03T08:00:00+00:00",
                 lead_time_band="0_7_days")
        ]
        result = compare(history, current, "flight")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["deal_status"], "building_history")

    def test_legacy_flight_history_derives_lead_time_from_observation_date(self):
        current = observation("flight", "MAN", "Rome", "Italy",
                              "2027-05-01", "2027-05-08", 100)
        history = [
            dict(current, price_gbp=150, observed_at="2026-11-05T08:00:00+00:00"),
            dict(current, price_gbp=140, observed_at="2026-11-04T08:00:00+00:00"),
            dict(current, price_gbp=130, observed_at="2026-11-03T08:00:00+00:00")
        ]
        for row in history:
            row.pop("lead_time_band", None)
        result = compare(history, current, "flight")
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["deal_status"], "strong_deal")

    def test_requires_three_samples_and_matches_trip_month_duration(self):
        current = observation("flight", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08", 80)
        history = [dict(current, price_gbp=150, observed_at="a"),
                   dict(current, price_gbp=150, observed_at="b", travel_month="06"),
                   dict(current, price_gbp=150, observed_at="c", nights=14)]
        self.assertEqual(compare(history, current, "flight")["deal_status"], "building_history")

    def test_hotels_compare_across_properties_in_same_category_and_quality_band(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2, "after_taxes_and_fees", 4, 4.6, 150)
        history = [observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                               price, name, "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.7, 180)
                   for price, name in ((150, "Hotel B"), (140, "Hotel C"), (130, "Hotel D"))]
        result = compare(history, current, "hotel")
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["benchmark_gbp"], 140)
        self.assertEqual(result["deal_status"], "strong_deal")

    def test_hotel_comparison_excludes_different_type_rating_and_guest_count(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Villa A", "vacation_rental", 4.2, 2),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Hotel B", "hotel", 3.2, 2, "unknown", 4, 4.5, 100),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Hotel C", "hotel", 4.2, 1, "unknown", 4, 4.5, 100)
        ]
        result = compare(history, current, "hotel")
        self.assertEqual(result["sample_count"], 0)
        self.assertEqual(result["deal_status"], "building_history")

    def test_hotel_comparison_rejects_different_star_class_or_location_quality(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2, "after_taxes_and_fees", 4, 4.5, 150)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Hotel B", "hotel", 4.3, 2, "after_taxes_and_fees", 3, 4.5, 150),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Hotel C", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 3.5, 150),
        ]
        self.assertEqual(compare(history, current, "hotel")["sample_count"], 0)

    def test_cross_property_hotel_benchmark_requires_sufficient_review_count(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2, "after_taxes_and_fees", 4, 4.5, 150)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        150, "Hotel B", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.5, 8),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        140, "Hotel C", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.5, 180),
        ]
        self.assertEqual(compare(history, current, "hotel")["sample_count"], 1)

    def test_cross_property_hotel_benchmark_requires_matching_star_and_location_quality(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2, "after_taxes_and_fees", 4, 4.6, 150)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Hotel B", "hotel", 4.3, 2, "after_taxes_and_fees", 3, 4.6, 150),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        500, "Hotel C", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 3.6, 150),
        ]
        self.assertEqual(compare(history, current, "hotel")["sample_count"], 0)

    def test_cross_property_hotel_benchmark_requires_twenty_reviews(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2, "after_taxes_and_fees", 4, 4.6, 150)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        150, "Hotel B", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.7, 8),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        140, "Hotel C", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.7, 180),
        ]
        self.assertEqual(compare(history, current, "hotel")["sample_count"], 1)

    def test_unrated_hotels_only_compare_with_same_property(self):
        current = observation("hotel", "MAN", "Dublin", "Ireland", "2027-05-01", "2027-05-08",
                              100, "Lua's Place", "hotel", None, 1)
        history = [
            dict(current, property=name, property_key=name.casefold(),
                 accommodation_type=None, rating_band=None, price_gbp=150 + i)
            for i, name in enumerate(("Generator Dublin", "The Dawson Hotel", "Lua's Place"))
        ]
        result = compare(history, current, "hotel")
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["deal_status"], "building_history")

    def test_unrated_property_requires_its_own_three_price_observations(self):
        current = observation("hotel", "MAN", "Dublin", "Ireland", "2027-05-01", "2027-05-08",
                              100, "Lua's Place", "hotel", None, 1)
        history = [dict(current, price_gbp=150 + i, observed_at=str(i)) for i in range(3)]
        result = compare(history, current, "hotel")
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["deal_status"], "strong_deal")

    def test_known_hostel_brands_are_not_misclassified_as_hotels(self):
        self.assertEqual(classify_accommodation("Generator Dublin", "hotel"), "hostel")
        self.assertEqual(classify_accommodation("Clink i Lár", "hotel"), "hostel")

    def test_same_day_repeat_scans_do_not_inflate_flight_sample_count(self):
        current = observation("flight", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08", 100)
        history = [
            dict(current, price_gbp=150, observed_at="2026-11-05T08:00:00+00:00"),
            dict(current, price_gbp=150, observed_at="2026-11-05T12:00:00+00:00"),
            dict(current, price_gbp=140, observed_at="2026-11-04T08:00:00+00:00"),
        ]
        result = compare(history, current, "flight")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["deal_status"], "building_history")

    def test_hotel_repeated_same_day_observation_is_deduplicated_per_property(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        150, "Hotel A", "hotel", 4.3, 2),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        140, "Hotel A", "hotel", 4.3, 2),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        130, "Hotel A", "hotel", 4.3, 2),
        ]
        history[0]["observed_at"] = "2026-11-05T08:00:00+00:00"
        history[1]["observed_at"] = "2026-11-05T12:00:00+00:00"
        history[2]["observed_at"] = "2026-11-04T08:00:00+00:00"
        result = compare(history, current, "hotel")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["deal_status"], "building_history")


    def test_hotel_comparison_excludes_different_tax_basis(self):
        current = observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                              100, "Hotel A", "hotel", 4.2, 2, "after_taxes_and_fees", 4, 4.6, 150)
        history = [
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        150, "Hotel B", "hotel", 4.3, 2, "displayed_total_tax_status_unknown", 4, 4.7, 180),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        140, "Hotel C", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.7, 180),
            observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08",
                        130, "Hotel D", "hotel", 4.3, 2, "after_taxes_and_fees", 4, 4.7, 180)
        ]
        result = compare(history, current, "hotel")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["deal_status"], "building_history")

    def test_invalid_trip_dates_and_prices_are_rejected(self):
        self.assertIsNone(observation("flight", "MAN", "Rome", "Italy", "bad", "2027-05-08", 100))
        self.assertIsNone(observation("hotel", "MAN", "Rome", "Italy", "2027-05-01", "2027-05-08", 0))

    def test_ingest_persists_flight_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "response.json"
            history = Path(folder) / "observations.jsonl"
            source.write_text(json.dumps({"search_parameters": {"departure_id": "MAN"},
                "destinations": [{"name": "Rome", "country": "Italy", "start_date": "2027-05-01",
                                  "end_date": "2027-05-08", "flight_price": 100}]}), encoding="utf-8")
            rows = ingest_explore(source, history)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["origin"], "MAN")
            self.assertEqual(len(history.read_text().splitlines()), 1)

    def test_ingest_hotels_persists_category_and_quality(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "hotels.csv"
            history = Path(folder) / "observations.jsonl"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "origin", "destination", "country", "flight_departure_date",
                    "flight_return_date", "total_price_gbp", "property",
                    "accommodation_type", "rating", "adults", "hotel_class",
                    "location_rating", "review_count"])
                writer.writeheader()
                writer.writerow({"origin": "MAN", "destination": "Rome", "country": "Italy",
                    "flight_departure_date": "2027-05-01", "flight_return_date": "2027-05-08",
                    "total_price_gbp": "100", "property": "Hotel A",
                    "accommodation_type": "hotel", "rating": "4.2", "adults": "2",
                    "hotel_class": "4", "location_rating": "4.5", "review_count": "150"})
            rows = ingest_hotels(source, history)
            self.assertEqual(rows[0]["accommodation_type"], "hotel")
            self.assertEqual(rows[0]["rating_band"], "4_to_4_5")
            self.assertEqual(rows[0]["adults"], 2)
            self.assertEqual(rows[0]["hotel_class"], 4)
            self.assertEqual(rows[0]["location_rating_band"], "4.5_5.0")
            self.assertEqual(rows[0]["review_count"], 150)


    def test_hotel_ingestion_scores_combined_flight_and_hotel_value(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "hotels.csv"
            history_path = Path(folder) / "observations.jsonl"
            history = []
            for day, flight_price, hotel_price in (
                ("2026-11-03T08:00:00+00:00", 200, 300),
                ("2026-11-04T08:00:00+00:00", 190, 290),
                ("2026-11-05T08:00:00+00:00", 210, 310),
            ):
                flight = observation("flight", "MAN", "Rome", "Italy",
                                     "2027-05-01", "2027-05-08", flight_price)
                hotel = observation("hotel", "MAN", "Rome", "Italy",
                                     "2027-05-01", "2027-05-08", hotel_price,
                                     "Hotel A", "hotel", 4.2, 2,
                                     "after_taxes_and_fees", 4, 4.6, 150)
                flight["observed_at"] = day
                hotel["observed_at"] = day
                history.extend((flight, hotel))
            append_history(history_path, history)

            with source.open("w", newline="", encoding="utf-8") as handle:
                fields = [
                    "origin", "destination", "country", "flight_departure_date",
                    "flight_return_date", "flight_price_gbp", "total_price_gbp",
                    "property", "accommodation_type", "rating", "adults",
                    "tax_basis", "hotel_class", "location_rating", "review_count"
                ]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "origin": "MAN", "destination": "Rome", "country": "Italy",
                    "flight_departure_date": "2027-05-01",
                    "flight_return_date": "2027-05-08",
                    "flight_price_gbp": "100", "total_price_gbp": "100",
                    "property": "Hotel A", "accommodation_type": "hotel",
                    "rating": "4.2", "adults": "2",
                    "tax_basis": "after_taxes_and_fees", "hotel_class": "4",
                    "location_rating": "4.6", "review_count": "150"
                })

            rows = ingest_hotels(source, history_path)
            scored = rows[0]
            self.assertEqual(scored["flight_benchmark_gbp"], 200)
            self.assertEqual(scored["benchmark_gbp"], 300)
            self.assertEqual(scored["combined_price_gbp"], 200)
            self.assertEqual(scored["combined_benchmark_gbp"], 500)
            self.assertEqual(scored["combined_discount_percent"], 60.0)
            self.assertEqual(scored["combined_deal_status"], "strong_deal")
            self.assertEqual(scored["combined_benchmark_method"], "sum_of_component_medians")


    def test_observation_retains_exact_return_date_for_insight_matching(self):
        row = observation("flight", "MAN", "Rome", "Italy",
                          "2027-05-01", "2027-05-08", 100)
        self.assertEqual(row["start_date"], "2027-05-01")
        self.assertEqual(row["end_date"], "2027-05-08")


    def test_comparisons_require_exact_outbound_and_return_dates(self):
        current = observation("flight", "MAN", "Rome", "Italy",
                              "2027-05-01", "2027-05-08", 100)
        other_week = observation("flight", "MAN", "Rome", "Italy",
                                  "2027-05-08", "2027-05-15", 40)
        same_week = observation("flight", "MAN", "Rome", "Italy",
                                 "2027-05-01", "2027-05-08", 150)
        result = compare([other_week, same_week], current, "flight")
        self.assertEqual(result["sample_count"], 1)
        self.assertIsNone(result["benchmark_gbp"])

    def test_rebuild_history_removes_legacy_cross_date_hotel_benchmarks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "observations.jsonl"
            old = {
                "kind": "hotel", "origin": "MAN", "destination": "Dublin",
                "country": "Ireland", "travel_month": "11", "nights": 7,
                "property": "The Dawson Hotel", "property_key": "the dawson hotel",
                "price_gbp": 666, "observed_at": "2026-11-01T10:00:00+00:00",
                "accommodation_type": "hotel", "rating_band": "3_5_to_4",
                "adults": 1, "tax_basis": "displayed_total_tax_status_unknown",
            }
            current = dict(old, price_gbp=212,
                           observed_at="2026-11-05T10:00:00+00:00",
                           start_date="2026-11-16", end_date="2026-11-23",
                           flight_price_gbp=30)
            append_history(path, [old, current])
            rebuilt = rebuild_history(path)
            self.assertEqual(rebuilt[1]["sample_count"], 0)
            self.assertEqual(rebuilt[1]["deal_status"], "building_history")
            self.assertIsNone(rebuilt[1]["benchmark_gbp"])
            self.assertEqual(len(load_history(path)), 2)



if __name__ == "__main__":
    unittest.main()
