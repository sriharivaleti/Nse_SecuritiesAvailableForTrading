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

const metricLabels = [
  ["marketCapCrore", "Market Cap"],
  ["freeFloatMarketCapCrore", "Free Float Market Cap"],
  ["sector", "Sector"],
  ["industry", "Industry"],
  ["basicIndustry", "Basic Industry"],
  ["symbolPE", "Stock P/E"],
  ["sectorPE", "Sector P/E"],
  ["estimatedEPS", "Estimated EPS"],
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
  if (key === "changePercent" || key === "dailyVolatility" || key === "annualVolatility") {
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
    historyStatus.textContent = "No close-price history";
    historyTable.innerHTML = `
      <tr><th>Dates</th><td>N/A</td></tr>
      <tr><th>Close</th><td>N/A</td></tr>
    `;
    return;
  }

  historyStatus.textContent = `${history.length} sessions`;
  const dateCells = history.map((item) => `<th>${item.date}</th>`).join("");
  const closeCells = history
    .map((item) => `<td>${formatNumber(item.close, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>`)
    .join("");
  historyTable.innerHTML = `
    <tr><th>Dates</th>${dateCells}</tr>
    <tr><th>Close</th>${closeCells}</tr>
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
  const typed = searchInput.value.trim().toUpperCase();
  if (typed && /^[A-Z0-9&-]+$/.test(typed)) return typed;
  return state.selected?.symbol || "";
}

async function refreshStock() {
  const symbol = getRefreshSymbol();
  if (!symbol) {
    actionStatus.textContent = "Type a stock symbol first.";
    searchInput.focus();
    return;
  }

  refreshButton.disabled = true;
  refreshButton.textContent = "...";
  actionStatus.textContent = `Refreshing ${symbol}...`;
  try {
    const response = await fetch(`/api/stock?symbol=${encodeURIComponent(symbol)}`, { method: "POST" });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || result.errorOutput || result.output || "Updater failed");
    await loadData();
    const refreshed = state.stocks.find((stock) => stock.symbol === symbol);
    if (refreshed) {
      selectStock(symbol);
      actionStatus.textContent = `${symbol} updated.`;
    } else {
      actionStatus.textContent = `${symbol} is below 1000 Cr market cap or data was unavailable.`;
    }
  } catch (error) {
    actionStatus.textContent = `${symbol} refresh failed.`;
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
