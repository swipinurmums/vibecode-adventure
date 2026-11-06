#!/usr/bin/env python3
import argparse, csv, json, os
from datetime import datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv

API_URL = 'https://serpapi.com/search'

def classify_price_insight(lowest_price, typical_range):
    try:
        price = float(lowest_price)
        low, high = float(typical_range[0]), float(typical_range[1])
        if price <= 0 or low <= 0 or high < low: raise ValueError
    except (TypeError, ValueError, IndexError):
        return {'benchmark_status':'insufficient_price_insights','discount_vs_typical_low_percent':None}
    discount = (low-price)/low*100
    status = 'strong_deal' if discount >= 15 else ('below_typical' if price < low else ('typical' if price <= high else 'above_typical'))
    return {'benchmark_status':status,'discount_vs_typical_low_percent':round(discount,1)}

def normalise(payload, candidate):
    insight = payload.get('price_insights') or {}
    typical = insight.get('typical_price_range') or []
    try: low, high = float(typical[0]), float(typical[1])
    except (TypeError, ValueError, IndexError): low = high = None
    row = {'origin':candidate.get('origin'),'destination':candidate.get('destination'),'country':candidate.get('country'),
           'departure_date':candidate.get('departure_date'),'return_date':candidate.get('return_date'),
           'explore_fare_gbp':candidate.get('flight_price_gbp'),'google_flights_lowest_price_gbp':insight.get('lowest_price'),
           'price_level':insight.get('price_level'),'typical_price_low_gbp':low,'typical_price_high_gbp':high,
           'price_history':insight.get('price_history') or [],'observed_at':datetime.now(timezone.utc).isoformat(),
           'source':'google_flights_price_insights'}
    row.update(classify_price_insight(insight.get('lowest_price'), typical))
    return row

def main():
    parser=argparse.ArgumentParser(description='Fetch route-specific Google Flights price insights for one candidate.')
    parser.add_argument('--candidate-csv',required=True); parser.add_argument('--output-dir',default='data/flight_insights')
    parser.add_argument('--max-flight-price',type=float,default=250); args=parser.parse_args()
    load_dotenv(); secret=os.getenv('SERPAPI_KEY')
    if not secret or secret=='replace_me': raise SystemExit('SERPAPI_KEY is missing')
    with open(args.candidate_csv,newline='',encoding='utf-8-sig') as handle: rows=list(csv.DictReader(handle))
    eligible=[]
    for row in rows:
        try: price=float(str(row.get('flight_price_gbp','')).replace('£','').replace(',',''))
        except (TypeError,ValueError): continue
        if price <= args.max_flight_price and row.get('departure_date') and row.get('return_date'):
            row['flight_price_gbp']=price; eligible.append(row)
    if not eligible: raise SystemExit('No eligible flight candidate for price insights')
    candidate=sorted(eligible,key=lambda r:r['flight_price_gbp'])[0]
    arrival=candidate.get('destination_id') or candidate.get('destination')
    params={'engine':'google_flights','departure_id':candidate['origin'],'arrival_id':arrival,
            'outbound_date':candidate['departure_date'],'return_date':candidate['return_date'],'type':'1',
            'adults':'1','travel_class':'1','currency':'GBP','gl':'uk','hl':'en'}
    params['api_'+'key']=secret
    response=requests.get(API_URL,params=params,timeout=90); response.raise_for_status(); payload=response.json()
    if payload.get('error') or payload.get('search_metadata',{}).get('status')=='Error':
        raise RuntimeError(payload.get('error') or 'Google Flights insights search failed')
    result=normalise(payload,candidate)
    folder=Path(args.output_dir)/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); folder.mkdir(parents=True,exist_ok=True)
    (folder/'raw.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'insights.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f"{result['origin']} -> {result['destination']} | lowest {result['google_flights_lowest_price_gbp']} GBP | typical {result['typical_price_low_gbp']}-{result['typical_price_high_gbp']} GBP | {result['benchmark_status']}")

if __name__=='__main__': main()