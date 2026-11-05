import json,tempfile,unittest
from pathlib import Path
from deal_tracker import observation,compare,ingest_explore
class DealTrackerTests(unittest.TestCase):
 def test_three_comparable_observations_use_median(self):
  current=observation("flight","MAN","Rome","Italy","2027-05-01","2027-05-08",100)
  history=[dict(current,price_gbp=p,observed_at=str(i)) for i,p in enumerate((150,140,130))]
  result=compare(history,current,"flight")
  self.assertEqual(result["benchmark_gbp"],140);self.assertEqual(result["discount_percent"],28.6);self.assertEqual(result["deal_status"],"strong_deal")
 def test_requires_three_samples_and_matches_trip_month_duration(self):
  current=observation("flight","MAN","Rome","Italy","2027-05-01","2027-05-08",80)
  history=[dict(current,price_gbp=150,observed_at="a"),dict(current,price_gbp=150,observed_at="b",travel_month="06"),dict(current,price_gbp=150,observed_at="c",nights=14)]
  self.assertEqual(compare(history,current,"flight")["deal_status"],"building_history")
 def test_hotels_only_compare_same_property(self):
  current=observation("hotel","MAN","Rome","Italy","2027-05-01","2027-05-08",100,"Hotel A")
  history=[dict(current,price_gbp=150,observed_at=str(i)) for i in range(3)];history.append(dict(current,property_key="hotel b",price_gbp=900,observed_at="other"))
  self.assertEqual(compare(history,current,"hotel")["benchmark_gbp"],150)
 def test_invalid_trip_dates_are_rejected(self):
  self.assertIsNone(observation("flight","MAN","Rome","Italy","bad","2027-05-08",100))
 def test_ingest_persists_flight_observation(self):
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/"response.json";history=Path(folder)/"observations.jsonl"
   source.write_text(json.dumps({"search_parameters":{"departure_id":"MAN"},"destinations":[{"name":"Rome","country":"Italy","start_date":"2027-05-01","end_date":"2027-05-08","flight_price":100}]}),encoding="utf-8")
   rows=ingest_explore(source,history);self.assertEqual(len(rows),1);self.assertEqual(rows[0]["origin"],"MAN");self.assertEqual(len(history.read_text().splitlines()),1)
if __name__=="__main__":unittest.main()
