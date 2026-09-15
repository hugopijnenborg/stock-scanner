"""Turn a Discord export of the trader's alerts into a trade list.

The scanner exists to surface the kind of setup this trader buys, so his own
calls are the only direct measure of whether it does. This reads the exported
chat and writes one row per action, which scripts/rank_trader_entries.py then
scores.

Parsing notes, each of which came from a real message that was read wrong:

- One message often carries both directions. "...taking some profits: META at
  $676.37 ... Buying with a small position: SOFI at $19.75" is three sells and
  a buy. So the text is read left to right and every ticker/price pair takes
  the direction of the most recent verb before it, rather than one direction
  per message or per sentence.
- "up 10% from my entry" is a reference to an old buy, not a new one. Those
  back-references are excluded before the verbs are located, or a profit-taking
  message flips to a buy halfway through its own list.
- Ideas, hypotheticals and remarks about other people's trades are not his
  trades: "some ideas (I did not buy)", "if anyone bought IREN", "your first TP
  has been hit", "an alternative is to buy IBIT".
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

HEAD = re.compile(r"—\s*(\d{2})-(\d{2})-(\d{4}),\s*(\d{2}:\d{2})")
PAIR = re.compile(r"\b([A-Z]{2,5})\b\s*(?:at\s*|@\s*)?\(?\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
BUY = re.compile(r"\b(bought|buying|buy|added|adding|add|opening|opened|starter|entering|entered|entry|initiating|scaling in|back in)\b", re.I)
SELL = re.compile(r"\b(took profits?|taking profits?|take profits?|locking in|locked in|trimming|trimmed|trim|selling|sold|sell|exiting|exited|exit|closing|closed|de-risk\w*|stopped out|cutting)\b", re.I)
BACKREF = re.compile(r"(from|since|at)\s+(my|our|the|his)\s+(entry|avg|average|alert|position|last entry)", re.I)
SKIP = re.compile(
    r"(not an official|if i wasn|would (?:definitely )?be|if anyone|feel free|for those who|"
    r"you should be|your (?:first )?tp|has been hit|an alternative is|looking to add|i will add|"
    r"did ?n.t buy|just ideas|some ideas|not buying|watchlist|keeping an eye)",
    re.I,
)

CRYPTO = {"BTC", "ETH", "IBIT", "SOL", "XRP", "DOGE"}
NOT_TICKERS = {
    "VIP", "TP", "SL", "PT", "DD", "ATH", "IMO", "CEO", "ETF", "EPS", "IPO", "AI", "US", "EU",
    "UK", "NYSE", "SP", "FY", "YTD", "Q1", "Q2", "Q3", "Q4", "AM", "PM", "ET", "CET", "LOL",
    "BTW", "FYI", "ASAP", "EOD", "THE", "AND", "FOR", "ALL", "NEW", "BUT", "NOT", "YES", "OUT",
    "NOW", "ONE", "TWO",
} | CRYPTO


def read_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{W}body")
    out = []
    for para in body.iter(f"{W}p"):
        text = "".join(node.text or "" for node in para.iter(f"{W}t"))
        out.append(text.replace("\xa0", " ").strip())
    return out


def split_messages(paragraphs: list[str]) -> list[dict]:
    messages, current = [], None
    for line in paragraphs:
        head = HEAD.search(line)
        if head and line.count("—") == 1 and len(line) < 120:
            if current:
                messages.append(current)
            current = {
                "date": f"{head.group(3)}-{head.group(2)}-{head.group(1)}",
                "time": head.group(4),
                "parts": [],
            }
        elif current is not None and line and line != "[Bull],":
            current["parts"].append(line)
    if current:
        messages.append(current)
    for message in messages:
        message["text"] = " @VIP ".join(message["parts"])
    return messages


def extract_actions(messages: list[dict]) -> list[dict]:
    actions, seen = [], set()
    for message in messages:
        text = message["text"]
        backrefs = [(m.start(), m.end()) for m in BACKREF.finditer(text)]
        def inside_backref(pos: int) -> bool:
            return any(start <= pos <= end for start, end in backrefs)

        marks = sorted(
            [(m.start(), "BUY") for m in BUY.finditer(text) if not inside_backref(m.start())]
            + [(m.start(), "SELL") for m in SELL.finditer(text) if not inside_backref(m.start())]
        )
        for match in PAIR.finditer(text):
            ticker, price, pos = match.group(1), match.group(2), match.start()
            if ticker in NOT_TICKERS:
                continue
            if SKIP.search(text[max(0, pos - 220):pos + 40]):
                continue
            before = [kind for at, kind in marks if at < pos]
            if not before:
                continue
            row = {
                "date": message["date"],
                "time": message["time"],
                "action": before[-1],
                "ticker": ticker,
                "price": round(float(price.replace(",", "")), 4),
                "quote": text[max(0, pos - 90):pos + 70].strip(),
            }
            key = (row["date"], row["action"], row["ticker"], row["price"])
            if key in seen:
                continue
            seen.add(key)
            actions.append(row)
    return sorted(actions, key=lambda r: (r["date"], r["time"], r["ticker"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a Discord export into a trade list")
    parser.add_argument("export", help="path to the .docx export")
    parser.add_argument("--output", default="data/trader_discord_trades.csv")
    args = parser.parse_args()

    actions = extract_actions(split_messages(read_paragraphs(Path(args.export))))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "time", "action", "ticker", "price", "quote"])
        writer.writeheader()
        writer.writerows(actions)

    buys = sum(1 for a in actions if a["action"] == "BUY")
    print(f"{len(actions)} acties ({buys} koop, {len(actions) - buys} verkoop) "
          f"over {len({a['ticker'] for a in actions})} tickers -> {output}")


if __name__ == "__main__":
    main()
