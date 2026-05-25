import argparse
import csv
import html
import http.cookiejar
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "stocks.json"
CSV_FILES = [
    (ROOT / "EQUITY_L.csv", "NSE"),
    (ROOT / "SME_EQUITY_L.csv", "NSE_SME"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


class DataClient:
    def __init__(self):
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(cookie_jar))

    def get_json(self, url, referer="https://finance.yahoo.com/", retries=2, pause=0.8):
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

    def get_text(self, url, referer="https://www.screener.in/", retries=2, pause=0.8):
        last_error = None
        for attempt in range(retries + 1):
            try:
                request = Request(url, headers={**HEADERS, "Accept": "text/html,*/*", "Referer": referer})
                with self.opener.open(request, timeout=25) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except (HTTPError, URLError, TimeoutError) as error:
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
                symbol = row.get("SYMBOL", "").strip().upper()
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                securities.append(
                    {
                        "symbol": symbol,
                        "name": row.get("NAME_OF_COMPANY", "").strip() or symbol,
                        "series": row.get("SERIES", "") or "EQ",
                        "segment": segment,
                        "isin": row.get("ISIN_NUMBER", ""),
                        "listingDate": row.get("DATE_OF_LISTING", ""),
                    }
                )
    return securities


def normalize_symbol(value):
    return value.strip().upper().removesuffix(".NS")


def yahoo_symbol(symbol):
    return f"{symbol}.NS"


def to_float(value):
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def fetch_yahoo_search(client, query):
    params = urlencode({"q": query, "quotesCount": 8, "newsCount": 0})
    url = f"https://query2.finance.yahoo.com/v1/finance/search?{params}"
    return client.get_json(url, retries=1)


def resolve_security(client, query):
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Enter a stock symbol or company name.")

    normalized = normalize_symbol(cleaned)
    if " " not in normalized:
        try:
            chart_meta, _ = fetch_chart(client, normalized)
            return {
                "symbol": normalized,
                "name": chart_meta.get("longName") or chart_meta.get("shortName") or normalized,
                "series": "EQ",
                "segment": "EQUITY",
                "isin": "",
                "listingDate": "",
                "sector": None,
                "industry": None,
            }
        except Exception:
            pass

    matches = []
    try:
        matches = fetch_yahoo_search(client, cleaned).get("quotes") or []
    except Exception:
        matches = []

    nse_matches = [
        item
        for item in matches
        if item.get("quoteType") == "EQUITY"
        and (item.get("exchange") == "NSI" or str(item.get("symbol", "")).endswith(".NS"))
    ]

    bse_matches = [
        item
        for item in matches
        if item.get("quoteType") == "EQUITY"
        and (item.get("exchange") == "BSE" or str(item.get("symbol", "")).endswith(".BO"))
    ]

    if nse_matches or bse_matches:
        exact_matches = [item for item in nse_matches if normalize_symbol(item.get("symbol", "")) == normalized]
        match = exact_matches[0] if exact_matches else (nse_matches[0] if nse_matches else bse_matches[0])
        symbol = normalize_symbol(str(match.get("symbol", "")).removesuffix(".BO"))
        fetch_chart(client, symbol)
        return {
            "symbol": symbol,
            "name": match.get("longname") or match.get("shortname") or symbol,
            "series": "EQ",
            "segment": "EQUITY",
            "isin": "",
            "listingDate": "",
            "sector": match.get("sector"),
            "industry": match.get("industry"),
        }

    symbol = normalize_symbol(cleaned)
    if " " in symbol:
        raise ValueError(f"No NSE equity match found for '{query}'. Try the exact NSE symbol, for example RELIANCE.")

    return {
        "symbol": symbol,
        "name": symbol,
        "series": "EQ",
        "segment": "EQUITY",
        "isin": "",
        "listingDate": "",
        "sector": None,
        "industry": None,
    }


def fetch_chart(client, symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(yahoo_symbol(symbol))}?range=1mo&interval=1d"
    data = client.get_json(url, retries=1)
    result = data.get("chart", {}).get("result") or []
    if not result:
        raise ValueError(f"No Yahoo chart data found for {symbol}.")

    chart = result[0]
    meta = chart.get("meta", {})
    timestamps = chart.get("timestamp") or []
    quote_data = chart.get("indicators", {}).get("quote", [{}])[0]
    opens = quote_data.get("open") or []
    highs = quote_data.get("high") or []
    lows = quote_data.get("low") or []
    closes = quote_data.get("close") or []

    history = []
    for timestamp, open_price, high, low, close in zip(timestamps, opens, highs, lows, closes):
        if close is None:
            continue
        history.append(
            {
                "date": datetime.fromtimestamp(timestamp, timezone.utc).strftime("%d-%b"),
                "open": round(float(open_price), 2) if open_price is not None else None,
                "high": round(float(high), 2) if high is not None else None,
                "low": round(float(low), 2) if low is not None else None,
                "close": round(float(close), 2),
            }
        )
    return meta, history[-10:]


def fetch_screener_fundamentals(client, symbol):
    url = f"https://www.screener.in/company/{quote(symbol)}/consolidated/"
    page = client.get_text(url)
    ratios = {}

    top_ratios_match = re.search(r'<ul id="top-ratios">(.*?)</ul>', page, flags=re.S)
    if top_ratios_match:
        for block in re.findall(r"<li.*?</li>", top_ratios_match.group(1), flags=re.S):
            name_match = re.search(r'<span class="name">\s*(.*?)\s*</span>', block, flags=re.S)
            value_match = re.search(r'<span class="nowrap value">\s*(.*?)\s*</span>', block, flags=re.S)
            if not name_match or not value_match:
                continue
            name = html.unescape(re.sub(r"<.*?>", " ", name_match.group(1))).strip()
            value_text = html.unescape(re.sub(r"<.*?>", " ", value_match.group(1)))
            value_text = re.sub(r"\s+", " ", value_text).strip()
            number_match = re.search(r"-?[\d,.]+", value_text)
            ratios[name] = {
                "raw": value_text,
                "number": to_float(number_match.group(0)) if number_match else None,
            }

    title_match = re.search(r"<h1[^>]*>\s*(.*?)\s*</h1>", page, flags=re.S)
    company_name = None
    if title_match:
        company_name = html.unescape(re.sub(r"<.*?>", " ", title_match.group(1))).strip()

    return {"companyName": company_name, "ratios": ratios, "url": url}


def ratio_number(screener_data, name):
    return screener_data.get("ratios", {}).get(name, {}).get("number")


def ratio_raw(screener_data, name):
    return screener_data.get("ratios", {}).get(name, {}).get("raw")


def build_fundamentals(security, chart_meta, screener_data):
    last_price = to_float(chart_meta.get("regularMarketPrice"))
    previous_close = to_float(chart_meta.get("chartPreviousClose"))
    current_price = ratio_number(screener_data, "Current Price") or last_price
    symbol_pe = ratio_number(screener_data, "Stock P/E")

    return {
        "marketCapCrore": ratio_number(screener_data, "Market Cap"),
        "freeFloatMarketCapCrore": None,
        "lastPrice": current_price,
        "close": last_price,
        "previousClose": previous_close,
        "changePercent": ((last_price - previous_close) / previous_close * 100) if last_price and previous_close else None,
        "vwap": None,
        "currency": chart_meta.get("currency") or "INR",
        "macro": None,
        "sector": security.get("sector"),
        "industry": security.get("industry"),
        "basicIndustry": security.get("industry"),
        "symbolPE": symbol_pe,
        "sectorPE": None,
        "estimatedEPS": round(current_price / symbol_pe, 2) if current_price and symbol_pe else None,
        "bookValue": ratio_number(screener_data, "Book Value"),
        "dividendYield": ratio_number(screener_data, "Dividend Yield"),
        "roce": ratio_number(screener_data, "ROCE"),
        "roe": ratio_number(screener_data, "ROE"),
        "faceValue": ratio_number(screener_data, "Face Value"),
        "issuedSize": None,
        "fiftyTwoWeekHigh": to_float(chart_meta.get("fiftyTwoWeekHigh")),
        "fiftyTwoWeekHighDate": None,
        "fiftyTwoWeekLow": to_float(chart_meta.get("fiftyTwoWeekLow")),
        "fiftyTwoWeekLowDate": None,
        "tradedVolumeLakhs": to_float(chart_meta.get("regularMarketVolume")) / 100000
        if chart_meta.get("regularMarketVolume")
        else None,
        "tradedValueCrore": None,
        "dailyVolatility": None,
        "annualVolatility": None,
        "tradingStatus": "Active",
        "classOfShare": "Equity",
        "screenerUrl": screener_data.get("url"),
        "rawCurrentPrice": ratio_raw(screener_data, "Current Price"),
    }


def average(values):
    numbers = [value for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def build_recommendation(fundamentals, history):
    close_prices = [item.get("close") for item in history]
    latest_close = close_prices[-1] if close_prices else fundamentals.get("lastPrice")
    avg_close = average(close_prices)
    first_close = close_prices[0] if close_prices else None
    recent_return = ((latest_close - first_close) / first_close * 100) if latest_close and first_close else None
    pe = fundamentals.get("symbolPE")
    high = fundamentals.get("fiftyTwoWeekHigh")
    low = fundamentals.get("fiftyTwoWeekLow")

    short_score = 0
    short_reasons = []
    if latest_close and avg_close and latest_close >= avg_close:
        short_score += 1
        short_reasons.append("price is above the recent 10-session average")
    elif latest_close and avg_close:
        short_reasons.append("price is below the recent 10-session average")

    if recent_return is not None and recent_return > 0:
        short_score += 1
        short_reasons.append(f"recent 10-session return is positive ({recent_return:.2f}%)")
    elif recent_return is not None:
        short_reasons.append(f"recent 10-session return is weak ({recent_return:.2f}%)")

    if latest_close and high and high > 0 and latest_close >= high * 0.9:
        short_reasons.append("price is close to its 52-week high")
    elif latest_close and high:
        short_score += 1
        short_reasons.append("price is not close to its 52-week high")

    long_score = 0
    long_reasons = []
    if pe and pe <= 30:
        long_score += 1
        long_reasons.append("stock P/E is within a moderate range")
    elif pe:
        long_reasons.append("stock P/E is elevated")

    if fundamentals.get("roe") and fundamentals["roe"] >= 15:
        long_score += 1
        long_reasons.append("ROE is strong")
    elif fundamentals.get("roe") is not None:
        long_reasons.append("ROE is modest")

    if fundamentals.get("marketCapCrore") and fundamentals["marketCapCrore"] >= 1000:
        long_score += 1
        long_reasons.append("market cap is above 1000 Cr")

    if latest_close and high and low and high > low:
        range_position = (latest_close - low) / (high - low)
        if 0.25 <= range_position <= 0.85:
            long_score += 1
            long_reasons.append("price is not stretched at the 52-week extreme")
        elif range_position > 0.85:
            long_reasons.append("price is close to its 52-week high")
        else:
            long_reasons.append("price is near its 52-week low")

    def label(score):
        if score >= 2:
            return "Buy"
        if score == 1:
            return "Watch"
        return "Avoid"

    return {
        "shortTerm": label(short_score),
        "shortTermReason": "; ".join(short_reasons) or "not enough recent price data",
        "longTerm": label(long_score),
        "longTermReason": "; ".join(long_reasons) or "not enough valuation data",
        "method": "Educational rule-based view using Yahoo Finance price data and Screener.in fundamentals; not financial advice.",
    }


def load_existing_payload(output):
    if not output.exists():
        return {"stocks": []}
    try:
        return json.loads(output.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"stocks": []}


def fetch_stock(client, security, threshold_crore=None):
    chart_meta, history = fetch_chart(client, security["symbol"])
    screener_data = fetch_screener_fundamentals(client, security["symbol"])
    if screener_data.get("companyName"):
        security["name"] = screener_data["companyName"]

    fundamentals = build_fundamentals(security, chart_meta, screener_data)
    market_cap_crore = fundamentals.get("marketCapCrore")
    if threshold_crore and (market_cap_crore is None or market_cap_crore < threshold_crore):
        return None

    return {
        **security,
        "exchange": "NSE",
        "fundamentals": fundamentals,
        "history": history,
        "recommendation": build_recommendation(fundamentals, history),
        "dataSources": [
            fundamentals.get("screenerUrl"),
            "https://query1.finance.yahoo.com/v8/finance/chart",
            "https://query2.finance.yahoo.com/v1/finance/search",
        ],
    }


def write_payload(output, threshold_crore, stocks):
    stocks.sort(key=lambda stock: stock["symbol"])
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "thresholdCrore": threshold_crore,
        "source": "Yahoo Finance chart/search data and Screener.in fundamentals",
        "stockCount": len(stocks),
        "stocks": stocks,
    }
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Fetch and save NSE stock data on demand.")
    parser.add_argument("--threshold-crore", type=float, default=None)
    parser.add_argument("--limit", type=int, default=0, help="Limit CSV symbols for a bulk run.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="JSON output path.")
    parser.add_argument("--symbol", help="Stock symbol or company name to fetch and merge into the output file.")
    args = parser.parse_args()

    client = DataClient()

    if args.symbol:
        existing = load_existing_payload(args.output)
        try:
            security = resolve_security(client, args.symbol)
            existing_stocks = [stock for stock in existing.get("stocks", []) if stock.get("symbol") != security["symbol"]]
            stock = fetch_stock(client, security, args.threshold_crore)
        except Exception as error:
            print(f"Update failed for {args.symbol}: {error}", file=sys.stderr)
            return 1

        if stock:
            existing_stocks.append(stock)
            write_payload(args.output, args.threshold_crore, existing_stocks)
            print(f"Updated {security['symbol']} in {args.output}")
        else:
            write_payload(args.output, args.threshold_crore, existing_stocks)
            print(f"{security['symbol']} did not pass the configured market-cap filter.")
        return 0

    securities = read_securities()
    if args.limit:
        securities = securities[: args.limit]
    if not securities:
        print("No securities found in input CSV files.", file=sys.stderr)
        return 1

    selected = []
    for security in securities:
        try:
            stock = fetch_stock(client, security, args.threshold_crore)
        except Exception as error:
            print(f"Stock skipped for {security['symbol']}: {error}", file=sys.stderr)
            continue
        if stock:
            selected.append(stock)
            write_payload(args.output, args.threshold_crore, selected)
        time.sleep(0.35)

    print(f"Wrote {len(selected)} stocks to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
