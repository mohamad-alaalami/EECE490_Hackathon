const API_BASE =
  window.location.hostname === "localhost" &&
  !window.location.port.startsWith("500")
    ? "http://localhost:5001"
    : "";

const API = {
  branches: `${API_BASE}/api/branches`,
  clusters: `${API_BASE}/api/cluster-summary`,
  branchDetail: (branchName) =>
    `${API_BASE}/api/branch/${encodeURIComponent(branchName)}`,
};

const mockBranches = [
  {
    branch: "Stories Zalka",
    cluster: 2,
    health_score: 74.2,
    gap_profit: 12345,
    avg_revenue: 56000,
    margin: 0.31,
    growth: 0.08,
    volatility: 0.12,
    bev_share: 0.68,
    food_share: 0.32,
  },
  {
    branch: "Stories Hamra",
    cluster: 1,
    health_score: 62.4,
    gap_profit: 20800,
    avg_revenue: 49000,
    margin: 0.27,
    growth: 0.03,
    volatility: 0.16,
    bev_share: 0.73,
    food_share: 0.27,
  },
  {
    branch: "Stories Mar Mikhael",
    cluster: 0,
    health_score: 83.1,
    gap_profit: 6900,
    avg_revenue: 62000,
    margin: 0.34,
    growth: 0.1,
    volatility: 0.09,
    bev_share: 0.64,
    food_share: 0.36,
  },
  {
    branch: "Stories Verdun",
    cluster: 1,
    health_score: 58.9,
    gap_profit: 25650,
    avg_revenue: 44000,
    margin: 0.23,
    growth: -0.01,
    volatility: 0.2,
    bev_share: 0.76,
    food_share: 0.24,
  },
];

const mockClusters = [
  {
    cluster: 0,
    count: 6,
    avg_margin: 0.29,
    avg_growth: 0.04,
    avg_volatility: 0.1,
    avg_bev_share: 0.7,
    avg_food_share: 0.3,
  },
  {
    cluster: 1,
    count: 8,
    avg_margin: 0.25,
    avg_growth: 0.01,
    avg_volatility: 0.17,
    avg_bev_share: 0.74,
    avg_food_share: 0.26,
  },
  {
    cluster: 2,
    count: 5,
    avg_margin: 0.33,
    avg_growth: 0.09,
    avg_volatility: 0.08,
    avg_bev_share: 0.66,
    avg_food_share: 0.34,
  },
];

const mockBranchMonthly = {
  "Stories Zalka": {
    branch: "Stories Zalka",
    monthly: [
      { month: "2025-01", revenue: 42000, profit: 12000 },
      { month: "2025-02", revenue: 39000, profit: 11000 },
      { month: "2025-03", revenue: 46000, profit: 13800 },
      { month: "2025-04", revenue: 51000, profit: 15000 },
      { month: "2025-05", revenue: 56000, profit: 17400 },
    ],
  },
};

const state = {
  branches: [],
  clusters: [],
  detailByBranch: {},
  selectedBranch: null,
  sortKey: "health_score",
  sortDirection: "desc",
  searchTerm: "",
  usingMock: false,
};

const elements = {
  loading: document.getElementById("state-loading"),
  error: document.getElementById("state-error"),
  errorText: document.getElementById("error-text"),
  sourceChip: document.getElementById("data-source-chip"),
  pageTitle: document.getElementById("page-title"),
  navTabs: [...document.querySelectorAll(".nav-tab")],
  pages: {
    overview: document.getElementById("page-overview"),
    clusters: document.getElementById("page-clusters"),
    "branch-detail": document.getElementById("page-branch-detail"),
  },
  kpiTotalBranches: document.getElementById("kpi-total-branches"),
  kpiTotalGap: document.getElementById("kpi-total-gap"),
  kpiLowestHealth: document.getElementById("kpi-lowest-health"),
  search: document.getElementById("branch-search"),
  tableBody: document.getElementById("branches-tbody"),
  tableHeaders: [...document.querySelectorAll("#branches-table th[data-sort]")],
  clustersGrid: document.getElementById("clusters-grid"),
  clusterCanvas: document.getElementById("cluster-canvas"),
  clusterLegend: document.getElementById("cluster-legend"),
  detailName: document.getElementById("detail-branch-name"),
  detailClusterBadge: document.getElementById("detail-cluster-badge"),
  detailHealth: document.getElementById("detail-health"),
  detailGap: document.getElementById("detail-gap"),
  detailMargin: document.getElementById("detail-margin"),
  detailVolatility: document.getElementById("detail-volatility"),
  monthlyTbody: document.getElementById("monthly-tbody"),
  revenueCanvas: document.getElementById("revenue-canvas"),
};

init();

function init() {
  bindEvents();
  loadData();
}

function bindEvents() {
  elements.navTabs.forEach((tab) => {
    tab.addEventListener("click", () => setPage(tab.dataset.page));
  });

  elements.search.addEventListener("input", (event) => {
    state.searchTerm = event.target.value.toLowerCase().trim();
    renderOverviewTable();
  });

  elements.tableHeaders.forEach((header) => {
    header.dataset.label = header.textContent.trim();
    header.addEventListener("click", () => {
      const key = header.dataset.sort;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = key === "branch" ? "asc" : "desc";
      }
      renderOverviewTable();
    });
  });
}

async function loadData() {
  showLoading(true);
  showError("");
  try {
    const [branches, clusters] = await Promise.all([
      fetchJson(API.branches),
      fetchJson(API.clusters),
    ]);
    state.branches = branches;
    state.clusters = clusters;
    elements.sourceChip.textContent = "Processed CSV Data";
  } catch (error) {
    state.branches = [];
    state.clusters = [];
    elements.sourceChip.textContent = "Backend Error";
    showError(`Failed to load processed data from backend. (${error.message})`);
  } finally {
    showLoading(false);
    hydrateUI();
  }
}

function hydrateUI() {
  renderOverviewKPIs();
  renderOverviewTable();
  renderClusters();
  if (state.branches.length > 0) {
    openBranchDetail(state.branches[0].branch, false);
  }
}

function renderOverviewKPIs() {
  const totalBranches = state.branches.length;
  const totalGap = state.branches.reduce((sum, b) => sum + Number(b.gap_profit || 0), 0);
  const lowest = [...state.branches].sort((a, b) => a.health_score - b.health_score)[0];

  elements.kpiTotalBranches.textContent = String(totalBranches);
  elements.kpiTotalGap.textContent = formatCurrency(totalGap);
  elements.kpiLowestHealth.textContent = lowest ? lowest.branch : "-";
}

function renderOverviewTable() {
  const rows = getProcessedBranches();
  elements.tableBody.innerHTML = "";
  for (const branch of rows) {
    const tr = document.createElement("tr");
    tr.classList.add("clickable");
    tr.innerHTML = `
      <td>${escapeHtml(branch.branch)}</td>
      <td>${branch.cluster}</td>
      <td>${formatNumber(branch.health_score, 1)}</td>
      <td>${formatCurrency(branch.gap_profit)}</td>
      <td>${formatCurrency(branch.avg_revenue)}</td>
      <td>${formatPercent(branch.margin)}</td>
      <td>${formatPercent(branch.growth)}</td>
      <td>${formatPercent(branch.volatility)}</td>
    `;
    tr.addEventListener("click", () => openBranchDetail(branch.branch, true));
    elements.tableBody.appendChild(tr);
  }

  updateSortIndicators();
}

function getProcessedBranches() {
  const filtered = state.branches.filter((b) =>
    b.branch.toLowerCase().includes(state.searchTerm)
  );
  const direction = state.sortDirection === "asc" ? 1 : -1;
  return filtered.sort((a, b) => {
    const va = a[state.sortKey];
    const vb = b[state.sortKey];
    if (typeof va === "string") return va.localeCompare(vb) * direction;
    return (Number(va) - Number(vb)) * direction;
  });
}

function updateSortIndicators() {
  elements.tableHeaders.forEach((th) => {
    const key = th.dataset.sort;
    const active = key === state.sortKey;
    const arrow = !active ? "" : state.sortDirection === "asc" ? " ▲" : " ▼";
    th.textContent = `${th.dataset.label || th.textContent}${arrow}`;
  });
}

function renderClusters() {
  drawClusterMap(state.branches);
  elements.clustersGrid.innerHTML = "";
  for (const c of state.clusters) {
    const card = document.createElement("article");
    card.className = "card cluster-card";
    card.innerHTML = `
      <div class="cluster-title">
        <h3>Cluster ${c.cluster}</h3>
        <p>${c.count} branches</p>
      </div>
      <div class="cluster-stats">
        <div class="cluster-stat"><p>Avg Margin</p><strong>${formatPercent(c.avg_margin)}</strong></div>
        <div class="cluster-stat"><p>Avg Growth</p><strong>${formatPercent(c.avg_growth)}</strong></div>
        <div class="cluster-stat"><p>Avg Volatility</p><strong>${formatPercent(c.avg_volatility)}</strong></div>
        <div class="cluster-stat"><p>Mix (Bev/Food)</p><strong>${formatPercent(c.avg_bev_share)} / ${formatPercent(c.avg_food_share)}</strong></div>
      </div>
      <div class="profile-row">
        <span><small>Margin</small><small>${formatPercent(c.avg_margin)}</small></span>
        <div class="bar-shell"><div class="bar-fill" style="width:${clamp01(c.avg_margin) * 100}%"></div></div>
      </div>
      <div class="profile-row">
        <span><small>Growth</small><small>${formatPercent(c.avg_growth)}</small></span>
        <div class="bar-shell"><div class="bar-fill" style="width:${clamp01(Math.max(c.avg_growth, 0)) * 100}%"></div></div>
      </div>
      <div class="profile-row">
        <span><small>Volatility (inverse)</small><small>${formatPercent(c.avg_volatility)}</small></span>
        <div class="bar-shell"><div class="bar-fill" style="width:${(1 - clamp01(c.avg_volatility)) * 100}%"></div></div>
      </div>
      <div class="profile-row">
        <span><small>Beverage Share</small><small>${formatPercent(c.avg_bev_share)}</small></span>
        <div class="bar-shell"><div class="bar-fill" style="width:${clamp01(c.avg_bev_share) * 100}%"></div></div>
      </div>
    `;
    elements.clustersGrid.appendChild(card);
  }
}

async function openBranchDetail(branchName, switchPage) {
  const branch = state.branches.find((b) => b.branch === branchName);
  if (!branch) return;

  state.selectedBranch = branchName;
  if (switchPage) setPage("branch-detail");

  elements.detailName.textContent = branch.branch;
  elements.detailClusterBadge.textContent = `Cluster ${branch.cluster}`;
  elements.detailHealth.textContent = formatNumber(branch.health_score, 1);
  elements.detailGap.textContent = formatCurrency(branch.gap_profit);
  elements.detailMargin.textContent = formatPercent(branch.margin);
  elements.detailVolatility.textContent = formatPercent(branch.volatility);

  let detail = state.detailByBranch[branchName];
  if (!detail) {
    try {
      detail = await fetchJson(API.branchDetail(branchName));
    } catch (error) {
      detail = {
        branch: branchName,
        monthly: [],
      };
    }
    state.detailByBranch[branchName] = detail;
  }

  renderMonthlyTable(detail.monthly || []);
  drawRevenueChart(detail.monthly || []);
}

function drawClusterMap(branches) {
  const canvas = elements.clusterCanvas;
  const legend = elements.clusterLegend;
  const ctx = canvas?.getContext("2d");
  if (!canvas || !ctx || !legend) return;

  const points = (branches || []).filter(
    (b) => Number.isFinite(Number(b.pca_1)) && Number.isFinite(Number(b.pca_2))
  );
  legend.innerHTML = "";

  const ratio = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 980;
  const cssHeight = 460;
  canvas.width = Math.floor(cssWidth * ratio);
  canvas.height = Math.floor(cssHeight * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  const w = cssWidth;
  const h = cssHeight;
  const pad = { left: 62, right: 24, top: 24, bottom: 50 };
  ctx.clearRect(0, 0, w, h);

  if (!points.length) {
    ctx.fillStyle = "#557365";
    ctx.font = "14px Manrope";
    ctx.fillText("No PCA cluster points available.", 20, 30);
    return;
  }

  const xs = points.map((p) => Number(p.pca_1));
  const ys = points.map((p) => Number(p.pca_2));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  ctx.strokeStyle = "#dcebe2";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + (i / 4) * plotH;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();
  }
  for (let i = 0; i <= 4; i += 1) {
    const x = pad.left + (i / 4) * plotW;
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, h - pad.bottom);
    ctx.stroke();
  }

  ctx.strokeStyle = "#9ab8a8";
  ctx.lineWidth = 1.25;
  ctx.beginPath();
  ctx.moveTo(pad.left, h - pad.bottom);
  ctx.lineTo(w - pad.right, h - pad.bottom);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, h - pad.bottom);
  ctx.stroke();

  const colorMap = ["#2b7bba", "#f08a24", "#3ea95b"];
  const seenClusters = [...new Set(points.map((p) => Number(p.cluster)).sort((a, b) => a - b))];

  seenClusters.forEach((clusterId) => {
    const color = colorMap[clusterId] || "#777";
    const chip = document.createElement("span");
    chip.innerHTML = `<i style="background:${color}"></i>Cluster ${clusterId}`;
    legend.appendChild(chip);
  });

  points.forEach((p) => {
    const x = pad.left + ((Number(p.pca_1) - minX) / spanX) * plotW;
    const y = h - pad.bottom - ((Number(p.pca_2) - minY) / spanY) * plotH;
    const cluster = Number(p.cluster);
    ctx.fillStyle = colorMap[cluster] || "#777";
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.2;
    ctx.stroke();
  });

  ctx.fillStyle = "#365a49";
  ctx.font = "13px Manrope";
  ctx.fillText("Principal Component 1", w / 2 - 60, h - 16);
  ctx.save();
  ctx.translate(18, h / 2 + 70);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Principal Component 2", 0, 0);
  ctx.restore();
}

function renderMonthlyTable(monthly) {
  elements.monthlyTbody.innerHTML = "";
  if (!monthly.length) {
    elements.monthlyTbody.innerHTML = `<tr><td colspan="3">No monthly data available.</td></tr>`;
    return;
  }
  for (const row of monthly) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.month)}</td>
      <td>${formatCurrency(row.revenue)}</td>
      <td>${formatCurrency(row.profit)}</td>
    `;
    elements.monthlyTbody.appendChild(tr);
  }
}

function drawRevenueChart(monthly) {
  const canvas = elements.revenueCanvas;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const ratio = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 980;
  const cssHeight = 320;
  canvas.width = Math.floor(cssWidth * ratio);
  canvas.height = Math.floor(cssHeight * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  const w = cssWidth;
  const h = cssHeight;
  const pad = { left: 55, right: 20, top: 18, bottom: 40 };
  const pw = w - pad.left - pad.right;
  const ph = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  if (!monthly.length) {
    ctx.fillStyle = "#557365";
    ctx.font = "14px Manrope";
    ctx.fillText("No monthly data to plot.", 20, 28);
    return;
  }

  const values = monthly.map((m) => Number(m.revenue) || 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);

  ctx.strokeStyle = "#d8e9df";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = pad.top + (ph / 3) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();
  }

  const points = values.map((v, i) => {
    const x = pad.left + (i / Math.max(values.length - 1, 1)) * pw;
    const y = pad.top + ((max - v) / range) * ph;
    return { x, y, v, label: monthly[i].month };
  });

  ctx.beginPath();
  points.forEach((p, i) => {
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.strokeStyle = "#1f8a5b";
  ctx.lineWidth = 2.5;
  ctx.stroke();

  ctx.fillStyle = "rgba(31, 138, 91, 0.14)";
  ctx.beginPath();
  points.forEach((p, i) => {
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.lineTo(points[points.length - 1].x, h - pad.bottom);
  ctx.lineTo(points[0].x, h - pad.bottom);
  ctx.closePath();
  ctx.fill();

  points.forEach((p) => {
    ctx.fillStyle = "#1f8a5b";
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.fillStyle = "#3f6755";
  ctx.font = "12px Manrope";
  points.forEach((p) => {
    ctx.fillText(p.label, p.x - 18, h - 16);
  });
}

function setPage(pageName) {
  elements.navTabs.forEach((t) => t.classList.toggle("active", t.dataset.page === pageName));
  Object.keys(elements.pages).forEach((name) => {
    elements.pages[name].classList.toggle("active", name === pageName);
  });
  elements.pageTitle.textContent =
    pageName === "branch-detail"
      ? `Branch Detail${state.selectedBranch ? `: ${state.selectedBranch}` : ""}`
      : pageName.charAt(0).toUpperCase() + pageName.slice(1);
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function showLoading(show) {
  elements.loading.classList.toggle("hidden", !show);
}

function showError(message) {
  const hasError = Boolean(message);
  elements.error.classList.toggle("hidden", !hasError);
  elements.errorText.textContent = message || "";
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

function formatPercent(value) {
  return `${((Number(value) || 0) * 100).toFixed(1)}%`;
}

function formatNumber(value, digits = 0) {
  return Number(value || 0).toFixed(digits);
}

function clamp01(value) {
  return Math.min(1, Math.max(0, Number(value) || 0));
}

function escapeHtml(input) {
  return String(input)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

window.addEventListener("resize", () => {
  drawClusterMap(state.branches);
  if (!state.selectedBranch) return;
  const detail = state.detailByBranch[state.selectedBranch];
  if (detail) drawRevenueChart(detail.monthly || []);
});
