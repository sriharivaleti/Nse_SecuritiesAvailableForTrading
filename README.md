# NSE 1000 Crore Screener

Local two-panel screener built from `EQUITY_L.csv` and `SME_EQUITY_L.csv`.

## Run

```powershell
python scripts/update_data.py
node server.js
```

Open `http://localhost:3000`.

To build one stock while testing, type a symbol such as `RELIANCE` into the search box and press the refresh button. If the stock market cap is at least 1000 Cr, it is added to the left panel.

## Daily 5 PM Update

Register the Windows scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_daily_update.ps1
```

The task runs `scripts/update_data.py` every day at 5:00 PM and refreshes `data/stocks.json`.

## Notes

- The CSV files only provide stock identity details, so market cap and fundamentals are fetched from NSE, while the two-week close-price series is fetched from Yahoo Finance chart data.
- The 1000 crore filter means market capitalization greater than or equal to INR 10,000,000,000.
- Some SME symbols may not have complete Yahoo Finance coverage; missing fields show as `N/A`.
