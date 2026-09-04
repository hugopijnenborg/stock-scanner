from __future__ import annotations

import pandas as pd

# Curated universe agreed for the scanner. This intentionally replaces the
# previous dynamic "largest U.S. companies" universe. Only these companies
# are downloaded, scored and shown by the dashboard.
CURATED_UNIVERSE = {
    # Technology, AI and software
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta Platforms", "AVGO": "Broadcom", "AMD": "AMD", "INTC": "Intel", "QCOM": "Qualcomm",
    "MU": "Micron Technology", "AMAT": "Applied Materials", "LRCX": "Lam Research", "KLAC": "KLA",
    "ANET": "Arista Networks", "CSCO": "Cisco", "DELL": "Dell Technologies", "IBM": "IBM", "ORCL": "Oracle",
    "CRM": "Salesforce", "ADBE": "Adobe", "NOW": "ServiceNow", "PLTR": "Palantir Technologies", "ADSK": "Autodesk",
    "INTU": "Intuit", "PANW": "Palo Alto Networks", "CRWD": "CrowdStrike", "FTNT": "Fortinet", "NET": "Cloudflare",
    "MRVL": "Marvell Technology", "SMCI": "Super Micro Computer", "VRT": "Vertiv", "COHR": "Coherent", "LITE": "Lumentum",
    "CIEN": "Ciena", "WDC": "Western Digital", "STX": "Seagate Technology", "HPE": "Hewlett Packard Enterprise",
    "NTAP": "NetApp", "FI": "Fiserv", "PYPL": "PayPal", "XYZ": "Block", "SNOW": "Snowflake", "DDOG": "Datadog",
    "WDAY": "Workday", "HUBS": "HubSpot", "MDB": "MongoDB", "VEEV": "Veeva Systems", "GTLB": "GitLab",
    "PATH": "UiPath", "TXN": "Texas Instruments", "ON": "ON Semiconductor", "TER": "Teradyne", "TSM": "Taiwan Semiconductor",
    "MSCI": "MSCI",

    # Consumer and internet
    "TSLA": "Tesla", "NFLX": "Netflix", "UBER": "Uber", "ABNB": "Airbnb", "BKNG": "Booking Holdings",
    "SPOT": "Spotify", "DASH": "DoorDash", "HOOD": "Robinhood Markets", "APP": "AppLovin", "DUOL": "Duolingo",
    "NKE": "Nike", "SBUX": "Starbucks", "MCD": "McDonald's", "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot",
    "LOW": "Lowe's", "TGT": "Target", "TJX": "TJX Companies", "CMG": "Chipotle Mexican Grill", "GM": "General Motors",
    "F": "Ford", "CELH": "Celsius Holdings", "BABA": "Alibaba", "HIMS": "Hims & Hers Health", "ZETA": "Zeta Global",
    "KO": "Coca-Cola", "PG": "Procter & Gamble", "RCL": "Royal Caribbean",

    # Financial
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs", "MS": "Morgan Stanley", "BLK": "BlackRock",
    "SCHW": "Charles Schwab", "V": "Visa", "MA": "Mastercard", "AXP": "American Express", "SPGI": "S&P Global",
    "MCO": "Moody's", "CME": "CME Group", "COIN": "Coinbase", "SOFI": "SoFi Technologies", "IBKR": "Interactive Brokers",
    "BX": "Blackstone", "WFC": "Wells Fargo", "C": "Citigroup", "KKR": "KKR", "NDAQ": "Nasdaq",

    # Energy, electricity and infrastructure
    "XOM": "Exxon Mobil", "CVX": "Chevron", "COP": "ConocoPhillips", "OXY": "Occidental Petroleum", "NEE": "NextEra Energy",
    "CEG": "Constellation Energy", "VST": "Vistra", "GEV": "GE Vernova", "ETN": "Eaton", "PWR": "Quanta Services",
    "CAT": "Caterpillar", "DE": "Deere", "WM": "Waste Management", "RSG": "Republic Services", "AEP": "American Electric Power",
    "DUK": "Duke Energy", "SO": "Southern Company", "WULF": "TeraWulf", "PCG": "PG&E", "APLD": "Applied Digital",
    "FCX": "Freeport-McMoRan", "VLO": "Valero Energy", "PSX": "Phillips 66", "MPLX": "MPLX", "NUE": "Nucor", "OKE": "ONEOK",
    "D": "Dominion Energy", "FANG": "Diamondback Energy", "DVN": "Devon Energy", "SRE": "Sempra", "EOG": "EOG Resources",
    "KMI": "Kinder Morgan", "LNG": "Cheniere Energy",

    # Healthcare
    "LLY": "Eli Lilly", "JNJ": "Johnson & Johnson", "UNH": "UnitedHealth Group", "ABBV": "AbbVie", "MRK": "Merck",
    "PFE": "Pfizer", "NVO": "Novo Nordisk", "AMGN": "Amgen", "GILD": "Gilead Sciences", "VRTX": "Vertex Pharmaceuticals",
    "REGN": "Regeneron Pharmaceuticals", "MRNA": "Moderna", "ISRG": "Intuitive Surgical", "TMO": "Thermo Fisher Scientific",
    "DHR": "Danaher", "ABT": "Abbott Laboratories", "MDT": "Medtronic", "ELV": "Elevance Health", "MCK": "McKesson",
    "CI": "The Cigna Group", "BSX": "Boston Scientific", "COR": "Cencora",

    # Industry, defense and transport
    "BA": "Boeing", "RTX": "RTX", "LMT": "Lockheed Martin", "NOC": "Northrop Grumman", "GD": "General Dynamics",
    "GE": "GE Aerospace", "HON": "Honeywell", "UNP": "Union Pacific", "UPS": "UPS", "FDX": "FedEx", "DAL": "Delta Air Lines",
    "AAL": "American Airlines", "HWM": "Howmet Aerospace", "LHX": "L3Harris Technologies", "FIX": "Comfort Systems USA",
    "URI": "United Rentals", "PCAR": "Paccar", "TDG": "TransDigm", "EMR": "Emerson Electric", "ITW": "Illinois Tool Works",
    "GWW": "W.W. Grainger", "MSI": "Motorola Solutions", "ECL": "Ecolab", "SHW": "Sherwin-Williams", "CTAS": "Cintas",
    "APD": "Air Products", "AME": "AMETEK", "FAST": "Fastenal", "KEYS": "Keysight Technologies", "CVNA": "Carvana",

    # Real estate, hospitality and related
    "EQIX": "Equinix", "DLR": "Digital Realty", "PLD": "Prologis", "AMT": "American Tower", "CCI": "Crown Castle",
    "WELL": "Welltower", "SPG": "Simon Property Group", "O": "Realty Income", "PSA": "Public Storage", "MAR": "Marriott",
    "HLT": "Hilton",

    # Telecom and media
    "VZ": "Verizon", "T": "AT&T", "WBD": "Warner Bros. Discovery", "CMCSA": "Comcast", "DIS": "Walt Disney",

    # Extra growth companies outside the S&P 500
    "ASTS": "AST SpaceMobile", "RKLB": "Rocket Lab", "CRWV": "CoreWeave", "IREN": "IREN", "NBIS": "Nebius",
    "AAOI": "Applied Optoelectronics", "AMKR": "Amkor Technology", "NVTS": "Navitas Semiconductor", "ASML": "ASML",
    "CCJ": "Cameco", "OKLO": "Oklo", "SMR": "NuScale Power", "ITCI": "Intellia Therapeutics", "RGTI": "Rigetti Computing",
    "IONQ": "IonQ", "TEM": "Tempus AI", "RDDT": "Reddit", "ONDS": "Ondas Holdings", "FN": "Fabrinet",

    # Final additions agreed
    "ARM": "Arm Holdings", "ALAB": "Astera Labs", "CRDO": "Credo Technology", "CLS": "Celestica", "BE": "Bloom Energy",
    "MSTR": "Strategy",
}


def load_top_us_stocks(limit: int | None = None) -> pd.DataFrame:
    """Return the fixed curated scanner universe."""
    rows = [{"ticker": ticker, "company_name": name} for ticker, name in CURATED_UNIVERSE.items()]
    frame = pd.DataFrame(rows)
    if limit is not None:
        frame = frame.head(limit)
    return frame.reset_index(drop=True)


if __name__ == "__main__":
    df = load_top_us_stocks()
    print(f"Loaded curated universe: {len(df)} stocks")
    print(df.to_string(index=False))