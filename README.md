# Nse Securities Available For Trading

Local two-panel NSE stock screener. Users can type a stock symbol or company name, fetch live web data on demand, and save the result into `data/stocks.json`.

## Run

```powershell
node server.js
```

Open `http://localhost:3001`.

Type a symbol or company name such as `RELIANCE`, `TCS`, or `Tata Consultancy` into the search box and press the refresh button. The app fetches price history and fundamentals from the internet, saves the stock, and adds it to the left panel.

## Daily 5 PM Update

Register the Windows scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_daily_update.ps1
```

The task runs `scripts/update_data.py` every day at 5:00 PM for a bulk refresh. On-demand refresh from the website is usually the friendlier workflow.

## Notes

- Price history comes from Yahoo Finance chart data.
- Fundamentals come from Screener.in.
- Recommendation labels are simple rule-based educational signals, not financial advice.
- Some symbols may not have complete web coverage; missing fields show as `N/A`.
