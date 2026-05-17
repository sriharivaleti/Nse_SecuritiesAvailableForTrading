import argparse
import http.cookiejar
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "stocks.json"
CSV_FILES = [
    (ROOT / "EQUITY_L.csv", "NSE"),
    (ROOT / "SME_EQUITY_L.csv", "NSE_SME"),
]
DEFAULT_THRESHOLD_CRORE = 1000
INR_PER_CRORE = 10_000_000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
}


class DataClient:
    def __init__(self):
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(cookie_jar))
        self.nse_ready = False

    def get_json(self, url, referer="https://www.nseindia.com/", retries=2, pause=0.8):
        last_error = None
        for attempt in range(retries + 1):
            try:
                request = Request(url, headers={**HEADERS, "Referer": referer})
                with self.opener.open(request, timeout=25) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < retries:
                    time.sleep(pause * (attempt + 1))
        raise last_error

    def ensure_nse(self):
        if self.nse_ready:
            return
        self.get_json("https://www.nseindia.com/api/marketStatus", retries=1)
        self.nse_ready = True

    def get_nse_json(self, url, symbol):
        self.ensure_nse()
        referer = f"https://www.nseindia.com/get-quotes/equity?symbol={quote(symbol)}"
        return self.get_json(url, referer=referer)


def get_json(url, retries=2, pause=0.8):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return DataClient().get_json(url, retries=0)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(pause * (attempt + 1))
    raise last_error


def clean_row(row):
    return {str(key).strip().replace(" ", "_").upper(): str(value).strip() for key, value in row.items() if key}


def read_securities():
    securities = []
    seen = set()
    for csv_path, segment in CSV_FILES:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw_row in csv.DictReader(handle):
                row = clean_row(raw_row)
                symbol = row.get("SYMBOL", "").strip()
                name = row.get("NAME_OF_COMPANY", "")
                series = row.get("SERIES", "")
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                securities.append(
                    {
                        "symbol": symbol,
                        "name": name.strip() or symbol,
                        "series": series,
                        "segment": segment,
                        "isin": row.get("ISIN_NUMBER", ""),
                        "listingDate": row.get("DATE_OF_LISTING", ""),
                    }
                )
    return securities


def yahoo_symbol(symbol):
    return f"{symbol}.NS"


def raw_value(value):
    if isinstance(value, dict):
        return value.get("raw")
    return value


def fetch_nse_quote(client, symbol):
    encoded = quote(symbol)
    quote_url = f"https://www.nseindia.com/api/quote-equity?symbol={encoded}"
    trade_url = f"https://www.nseindia.com/api/quote-equity?symbol={encoded}&section=trade_info"
    quote_data = client.get_nse_json(quote_url, symbol)
    try:
        trade_data = client.get_nse_json(trade_url, symbol)
    except Exception:
        trade_data = {}
    return quote_data, trade_data


def fetch_history(client, symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(yahoo_symbol(symbol))}?range=1mo&interval=1d"
    data = client.get_json(url, referer="https://finance.yahoo.com/", retries=1)
    result = data.get("chart", {}).get("result") or []
    if not result:
        return []

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    history = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%d-%b")
        history.append({"date": date, "close": round(float(close), 2)})
    return history[-10:]


def to_float(value):
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def build_fundamentals(quote_data, trade_data):
    price_info = quote_data.get("priceInfo", {})
    security_info = quote_data.get("securityInfo", {})
    metadata = quote_data.get("metadata", {})
    industry_info = quote_data.get("industryInfo", {})
    trade_info = trade_data.get("marketDeptOrderBook", {}).get("tradeInfo", {})

    last_price = to_float(price_info.get("lastPrice"))
    market_cap_crore = to_float(trade_info.get("totalMarketCap"))
    if market_cap_crore is None:
        issued_size = to_float(security_info.get("issuedSize"))
        if issued_size and last_price:
            market_cap_crore = (issued_size * last_price) / INR_PER_CRORE

    symbol_pe = to_float(metadata.get("pdSymbolPe"))
    estimated_eps = round(last_price / symbol_pe, 2) if last_price and symbol_pe else None
    week = price_info.get("weekHighLow", {})

    return {
        "marketCapCrore": round(market_cap_crore, 2) if market_cap_crore is not None else None,
        "freeFloatMarketCapCrore": to_float(trade_info.get("ffmc")),
        "lastPrice": last_price,
        "close": to_float(price_info.get("close")),
        "previousClose": to_float(price_info.get("previousClose")),
        "changePercent": to_float(price_info.get("pChange")),
        "vwap": to_float(price_info.get("vwap")),
        "currency": "INR",
        "macro": industry_info.get("macro"),
        "sector": industry_info.get("sector"),
        "industry": industry_info.get("industry"),
        "basicIndustry": industry_info.get("basicIndustry"),
        "symbolPE": symbol_pe,
        "sectorPE": to_float(metadata.get("pdSectorPe")),
        "estimatedEPS": estimated_eps,
        "faceValue": to_float(security_info.get("faceValue")),
        "issuedSize": to_float(security_info.get("issuedSize")),
        "fiftyTwoWeekHigh": to_float(week.get("max")),
        "fiftyTwoWeekHighDate": week.get("maxDate"),
        "fiftyTwoWeekLow": to_float(week.get("min")),
        "fiftyTwoWeekLowDate": week.get("minDate"),
        "tradedVolumeLakhs": to_float(trade_info.get("totalTradedVolume")),
        "tradedValueCrore": to_float(trade_info.get("totalTradedValue")),
        "dailyVolatility": to_float(trade_info.get("cmDailyVolatility")),
        "annualVolatility": to_float(trade_info.get("cmAnnualVolatility")),
        "tradingStatus": security_info.get("tradingStatus"),
        "classOfShare": security_info.get("classOfShare"),
    }


def load_existing_payload(output):
    if not output.exists():
        return {"stocks": []}
    try:
        return json.loads(output.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"stocks": []}


def find_security(securities, symbol):
    normalized = symbol.strip().upper()
    for security in securities:
        if security["symbol"].upper() == normalized:
            return security
    return None


def fetch_stock(client, security, threshold_crore):
    quote_data, trade_data = fetch_nse_quote(client, security["symbol"])
    fundamentals = build_fundamentals(quote_data, trade_data)
    market_cap_crore = fundamentals.get("marketCapCrore")
    if market_cap_crore is None or market_cap_crore < threshold_crore:
        return None

    try:
        history = fetch_history(client, security["symbol"])
    except Exception as error:
        print(f"History skipped for {security['symbol']}: {error}", file=sys.stderr)
        history = []

    return {
        **security,
        "exchange": "NSE",
        "fundamentals": fundamentals,
        "history": history,
    }


def write_payload(output, threshold_crore, stocks):
    stocks.sort(key=lambda stock: stock["symbol"])
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "thresholdCrore": threshold_crore,
        "source": "EQUITY_L.csv, SME_EQUITY_L.csv, NSE quote data, Yahoo Finance chart data",
        "stockCount": len(stocks),
        "stocks": stocks,
    }
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Update NSE screener data from NSE and Yahoo chart data.")
    parser.add_argument("--threshold-crore", type=float, default=DEFAULT_THRESHOLD_CRORE)
    parser.add_argument("--limit", type=int, default=0, help="Limit symbols for a quick test run.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="JSON output path.")
    parser.add_argument("--symbol", help="Update one symbol and merge it into the existing output file.")
    args = parser.parse_args()

    securities = read_securities()
    if args.limit:
        securities = securities[: args.limit]

    if not securities:
        print("No securities found in input CSV files.", file=sys.stderr)
        return 1

    client = DataClient()

    if args.symbol:
        security = find_security(securities, args.symbol)
        if not security:
            print(f"{args.symbol.upper()} was not found in EQUITY_L.csv or SME_EQUITY_L.csv.", file=sys.stderr)
            return 2

        existing = load_existing_payload(args.output)
        existing_stocks = [stock for stock in existing.get("stocks", []) if stock.get("symbol") != security["symbol"]]
        try:
            stock = fetch_stock(client, security, args.threshold_crore)
        except Exception as error:
            print(f"Update failed for {security['symbol']}: {error}", file=sys.stderr)
            return 1

        if stock:
            existing_stocks.append(stock)
            write_payload(args.output, args.threshold_crore, existing_stocks)
            print(f"Updated {security['symbol']} in {args.output}")
        else:
            write_payload(args.output, args.threshold_crore, existing_stocks)
            print(f"{security['symbol']} is below {args.threshold_crore:g} Cr market cap or market cap was unavailable.")
        return 0

    selected = []

    for security in securities:
        try:
            stock = fetch_stock(client, security, args.threshold_crore)
        except Exception as error:
            print(f"NSE quote skipped for {security['symbol']}: {error}", file=sys.stderr)
            continue

        if not stock:
            continue

        selected.append(stock)
        time.sleep(0.35)

    write_payload(args.output, args.threshold_crore, selected)
    print(f"Wrote {len(selected)} stocks to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
