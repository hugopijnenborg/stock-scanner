from __future__ import annotations

import argparse

from backtest import run_backtest
from scanner import scan
from universe import load_top_us_stocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Trader-pattern stock scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    u = sub.add_parser("universe", help="show current top 1000 universe")
    u.add_argument("--limit", type=int, default=1000)

    s = sub.add_parser("scan", help="scan current market")
    s.add_argument("--limit", type=int, default=1000)
    s.add_argument("--top", type=int, default=25)

    b = sub.add_parser("backtest", help="backtest supplied trader entries")

    args = parser.parse_args()
    if args.command == "universe":
        print(load_top_us_stocks(args.limit).to_string(index=False))
    elif args.command == "scan":
        print(scan(args.limit, args.top).to_string(index=False))
    elif args.command == "backtest":
        result = run_backtest()
        print(result.to_string(index=False))
        result.to_csv("trader_backtest.csv", index=False)
        print("\nSaved trader_backtest.csv")


if __name__ == "__main__":
    main()
