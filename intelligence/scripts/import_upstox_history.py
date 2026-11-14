"""Manual, local CLI. Run from the intelligence directory: python -m scripts.import_upstox_history ..."""
import argparse
import json
from app.upstox_history import import_upstox_daily

def main():
    parser=argparse.ArgumentParser(description="Explicit authorized Upstox daily candle import")
    parser.add_argument("--symbol",required=True)
    parser.add_argument("--market",choices=("NSE","BSE"),required=True)
    parser.add_argument("--from-date",required=True)
    parser.add_argument("--to-date",required=True)
    args=parser.parse_args()
    print(json.dumps(import_upstox_daily(args.symbol,args.market,args.from_date,args.to_date)))

if __name__=="__main__":
    main()
