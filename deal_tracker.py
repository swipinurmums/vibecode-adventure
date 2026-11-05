#!/usr/bin/env python3
"""Persist price observations and compare only genuinely comparable trips."""
import argparse, csv, json, statistics
from datetime import datetime, timezone
from pathlib import Path
HISTORY=Path("data/history/observations.jsonl")
MIN_SAMPLES=3
def load_history(path=HISTORY):
 p=Path(path)
 if not p.exists(): return []
 rows=[]
 for line in p.read_text(encoding="utf-8").splitlines():
  try:
   if line.strip(): rows.append(json.loads(line))
  except json.JSONDecodeError: pass
 return rows
def observation(kind,origin,destination,country,start,end,price,property_name=None):
 try:
  nights=(datetime.strptime(end,"%Y-%m-%d")-datetime.strptime(start,"%Y-%m-%d")).days
  month=datetime.strptime(start,"%Y-%m-%d").strftime("%m")
 except (TypeError,ValueError): return None
 if nights<=0:return None
 return {"kind":kind,"origin":origin or "","destination":destination or "","country":country or "","travel_month":month,"nights":nights,"property":property_name,"property_key":(property_name or "").strip().casefold() if kind=="hotel" else None,"price_gbp":float(price),"observed_at":datetime.now(timezone.utc).isoformat()}
def compare(history,current,kind):
 keys=("origin","destination","country","travel_month","nights"); prices=[]
 for row in history:
  if row.get("kind")!=kind or any(row.get(k)!=current.get(k) for k in keys):continue
  if kind=="hotel" and row.get("property_key")!=current.get("property_key"):continue
  try: value=float(row["price_gbp"])
  except (KeyError,TypeError,ValueError):continue
  if value>0:prices.append(value)
 if len(prices)<MIN_SAMPLES:return {"sample_count":len(prices),"benchmark_gbp":None,"discount_percent":None,"deal_status":"building_history"}
 median=statistics.median(prices); discount=(median-float(current["price_gbp"]))/median*100
 status="strong_deal" if discount>=15 else ("below_typical" if discount>0 else "not_below_typical")
 return {"sample_count":len(prices),"benchmark_gbp":round(median,2),"discount_percent":round(discount,1),"deal_status":status}
def append_history(path,rows):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("a",encoding="utf-8") as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False)+"\n")
def ingest_explore(source,history_path=HISTORY):
 payload=json.loads(Path(source).read_text(encoding="utf-8")); airport=payload.get("search_parameters",{}).get("departure_id",""); history=load_history(history_path); rows=[]
 for item in payload.get("destinations",[]):
  if item.get("flight_price") is None:continue
  row=observation("flight",airport,item.get("name"),item.get("country"),item.get("start_date"),item.get("end_date"),item["flight_price"])
  if row is None:continue
  row.update(compare(history,row,"flight"));rows.append(row)
 append_history(history_path,rows);return rows
def ingest_hotels(source,history_path=HISTORY):
 with Path(source).open(encoding="utf-8-sig",newline="") as f: source_rows=list(csv.DictReader(f))
 history=load_history(history_path);rows=[]
 for item in source_rows:
  try:price=float(item.get("total_price_gbp"))
  except (TypeError,ValueError):continue
  row=observation("hotel",item.get("origin"),item.get("destination"),item.get("country"),item.get("flight_departure_date"),item.get("flight_return_date"),price,item.get("property"))
  if row is None:continue
  row.update(compare(history,row,"hotel"));rows.append(row)
 append_history(history_path,rows);return rows
def report(rows):
 print(f"Historical observations added: {len(rows)}")
 for row in rows[:20]:
  benchmark=row["benchmark_gbp"]
  detail=f"building history ({row['sample_count']}/{MIN_SAMPLES} comparable past observations)" if benchmark is None else f"{row['discount_percent']:+.1f}% vs median £{benchmark:.2f} ({row['sample_count']} samples)"
  print(f"{row['kind']}: {row.get('property') or row['destination']} £{row['price_gbp']:.2f} — {row['deal_status']} — {detail}")
def main():
 parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest="command",required=True)
 explore=commands.add_parser("ingest-explore");explore.add_argument("--file",required=True)
 hotels=commands.add_parser("ingest-hotels");hotels.add_argument("--file",required=True)
 args=parser.parse_args();report(ingest_explore(args.file) if args.command=="ingest-explore" else ingest_hotels(args.file))
if __name__=="__main__":main()
