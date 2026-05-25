const state = {
  stocks: [],
  selected: null,
  query: "",
};

const stockList = document.querySelector("#stockList");
const stockCount = document.querySelector("#stockCount");
const lastUpdated = document.querySelector("#lastUpdated");
const searchInput = document.querySelector("#searchInput");
const refreshButton = document.querySelector("#refreshButton");
const actionStatus = document.querySelector("#actionStatus");
const emptyState = document.querySelector("#emptyState");
const stockDetail = document.querySelector("#stockDetail");
const detailExchange = document.querySelector("#detailExchange");
const detailTitle = document.querySelector("#detailTitle");
const detailName = document.querySelector("#detailName");
const detailPrice = document.querySelector("#detailPrice");
const historyTable = document.querySelector("#historyTable");
const historyStatus = document.querySelector("#historyStatus");
const metricGrid = document.querySelector("#metricGrid");
const recommendationGrid = document.querySelector("#recommendationGrid");

const metricLabels = [
  ["marketCapCrore", "Market Cap"],
  ["freeFloatMarketCapCrore", "Free Float Market Cap"],
  ["sector", "Sector"],
  ["industry", "Industry"],
  ["basicIndustry", "Basic Industry"],
  ["symbolPE", "Stock P/E"],
  ["sectorPE", "Sector P/E"],
  ["estimatedEPS", "Estimated EPS"],
  ["bookValue", "Book Value"],
  ["dividendYield", "Dividend Yield"],
  ["roce", "ROCE"],
  ["roe", "ROE"],
  ["faceValue", "Face Value"],
  ["issuedSize", "Issued Shares"],
  ["previousClose", "Previous Close"],
  ["vwap", "VWAP"],
  ["changePercent", "Change"],
  ["fiftyTwoWeekHigh", "52W High"],
  ["fiftyTwoWeekHighDate", "52W High Date"],
  ["fiftyTwoWeekLow", "52W Low"],
  ["fiftyTwoWeekLowDate", "52W Low Date"],
  ["tradedVolumeLakhs", "Traded Volume"],
  ["tradedValueCrore", "Traded Value"],
  ["dailyVolatility", "Daily Volatility"],
  ["annualVolatility", "Annual Volatility"],
  ["tradingStatus", "Trading Status"],
];

function formatDate(value) {
  if (!value) return "Not updated";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatNumber(value, options = {}) {
  if (value === null || value === undefined || value === "") return "N/A";
  if (typeof value === "string") return value;
  return new Intl.NumberFormat("en-IN", options).format(value);
}

function formatMetric(key, value) {
  if (value === null || value === undefined || value === "") return "N/A";
  if (key === "marketCapCrore") return `${formatNumber(value, { maximumFractionDigits: 0 })} Cr`;
  if (key === "freeFloatMarketCapCrore" || key === "tradedValueCrore") {
    return `${formatNumber(value, { maximumFractionDigits: 0 })} Cr`;
  }
  if (key === "tradedVolumeLakhs") {
    return `${formatNumber(value, { maximumFractionDigits: 2 })} L`;
  }
  if (key === "changePercent" || key === "dailyVolatility" || key === "annualVolatility" || key === "dividendYield" || key === "roce" || key === "roe") {
    return `${formatNumber(value, { maximumFractionDigits: 2 })}%`;
  }
  if (typeof value === "number") return formatNumber(value, { maximumFractionDigits: 2 });
  return String(value).replaceAll("_", " ");
}

function getFilteredStocks() {
  const query = state.query.trim().toLowerCase();
  if (!query) return state.stocks;
  return state.stocks.filter((stock) => {
    return stock.symbol.toLowerCase().includes(query) || stock.name.toLowerCase().includes(query);
  });
}

function renderList() {
  const filtered = getFilteredStocks();
  stockCount.textContent = `${filtered.length} stocks`;

  if (!filtered.length) {
    stockList.innerHTML = '<div class="message">No matching stocks yet. Type a symbol and press refresh.</div>';
    return;
  }

  stockList.innerHTML = filtered
    .map((stock) => {
      const active = state.selected?.symbol === stock.symbol ? " active" : "";
      return `
        <button class="stock-row${active}" type="button" data-symbol="${stock.symbol}" role="option" aria-selected="${active ? "true" : "false"}">
          <span>
            <span class="symbol">${stock.symbol}</span>
            <span class="stock-name">${stock.name}</span>
          </span>
          <span class="stock-cap">${formatMetric("marketCapCrore", stock.fundamentals.marketCapCrore)}</span>
        </button>
      `;
    })
    .join("");
}

function renderHistory(stock) {
  const history = stock.history || [];
  if (!history.length) {
    historyStatus.textContent = "No price history";
    historyTable.innerHTML = `
      <tr><th>Dates</th><td>N/A</td></tr>
      <tr><th>Open</th><td>N/A</td></tr>
      <tr><th>High</th><td>N/A</td></tr>
      <tr><th>Low</th><td>N/A</td></tr>
      <tr><th>Close</th><td>N/A</td></tr>
    `;
    return;
  }

  historyStatus.textContent = `${history.length} sessions`;
  const dateCells = history.map((item) => `<th>${item.date}</th>`).join("");
  const row = (label, key) => {
    const cells = history
      .map((item) => `<td>${formatNumber(item[key], { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>`)
      .join("");
    return `<tr><th>${label}</th>${cells}</tr>`;
  };
  historyTable.innerHTML = `
    <tr><th>Dates</th>${dateCells}</tr>
    ${row("Open", "open")}
    ${row("High", "high")}
    ${row("Low", "low")}
    ${row("Close", "close")}
  `;
}

function recommendationClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "buy") return "buy";
  if (normalized === "avoid") return "avoid";
  return "watch";
}

function renderRecommendation(stock) {
  const rec = stock.recommendation || {};
  recommendationGrid.innerHTML = `
    <div class="recommendation-card ${recommendationClass(rec.shortTerm)}">
      <span>Short Term</span>
      <strong>${rec.shortTerm || "N/A"}</strong>
      <p>${rec.shortTermReason || "Not enough data."}</p>
    </div>
    <div class="recommendation-card ${recommendationClass(rec.longTerm)}">
      <span>Long Term</span>
      <strong>${rec.longTerm || "N/A"}</strong>
      <p>${rec.longTermReason || "Not enough data."}</p>
    </div>
    <p class="recommendation-note">${rec.method || "Educational rule-based view from fetched market data; not financial advice."}</p>
  `;
}

function renderMetrics(stock) {
  metricGrid.innerHTML = metricLabels
    .map(([key, label]) => {
      const value = stock.fundamentals[key];
      return `
        <div class="metric-card">
          <span>${label}</span>
          <strong>${formatMetric(key, value)}</strong>
        </div>
      `;
    })
    .join("");
}

function selectStock(symbol) {
  state.selected = state.stocks.find((stock) => stock.symbol === symbol) || state.stocks[0] || null;
  if (!state.selected) return;

  emptyState.hidden = true;
  stockDetail.hidden = false;
  detailExchange.textContent = `${state.selected.series || "EQ"} / ${state.selected.exchange || "NSE"}`;
  detailTitle.textContent = state.selected.symbol;
  detailName.textContent = state.selected.name;
  detailPrice.textContent = formatMetric("lastPrice", state.selected.fundamentals.lastPrice);

  renderHistory(state.selected);
  renderRecommendation(state.selected);
  renderMetrics(state.selected);
  renderList();
}

async function loadData() {
  const response = await fetch("data/stocks.json", { cache: "no-store" });
  if (!response.ok) throw new Error("data/stocks.json was not found");
  const data = await response.json();
  state.stocks = Array.isArray(data.stocks) ? data.stocks : [];
  lastUpdated.textContent = formatDate(data.generatedAt);
  renderList();
  if (state.stocks.length) {
    const nextSymbol = state.selected && state.stocks.some((stock) => stock.symbol === state.selected.symbol)
      ? state.selected.symbol
      : state.stocks[0].symbol;
    selectStock(nextSymbol);
  } else {
    state.selected = null;
    emptyState.hidden = false;
    stockDetail.hidden = true;
  }
}

function getRefreshSymbol() {
  const typed = searchInput.value.trim();
  if (typed) return typed;
  return state.selected?.symbol || "";
}

async function refreshStock() {
  const query = getRefreshSymbol();
  if (!query) {
    actionStatus.textContent = "Type a stock symbol or company name first.";
    searchInput.focus();
    return;
  }

  refreshButton.disabled = true;
  refreshButton.textContent = "...";
  actionStatus.textContent = `Fetching ${query} from internet...`;
  try {
    const response = await fetch(`/api/stock?symbol=${encodeURIComponent(query)}`, { method: "POST" });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || result.errorOutput || result.output || "Updater failed");
    const resolvedSymbol = result.output?.match(/Updated\s+([A-Z0-9&-]+)/)?.[1] || query.trim().toUpperCase();
    await loadData();
    const refreshed = state.stocks.find((stock) => stock.symbol === resolvedSymbol);
    if (refreshed) {
      selectStock(resolvedSymbol);
      searchInput.value = resolvedSymbol;
      state.query = resolvedSymbol;
      actionStatus.textContent = `${resolvedSymbol} fetched and saved.`;
    } else {
      actionStatus.textContent = `${query} could not be saved. Try the exact NSE symbol.`;
    }
  } catch (error) {
    actionStatus.textContent = `${query} fetch failed.`;
    stockList.innerHTML = `<div class="message">${error.message}</div>`;
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = "R";
  }
}

stockList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-symbol]");
  if (button) selectStock(button.dataset.symbol);
});

searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  renderList();
});

refreshButton.addEventListener("click", refreshStock);

loadData().catch((error) => {
  stockList.innerHTML = `<div class="message">${error.message}. Run the updater to create the dataset.</div>`;
});
