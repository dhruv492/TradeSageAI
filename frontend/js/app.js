/**
 * Module      : app.js
 * Date        : 2026-09-03
 * Author      : Dhruv
 * Modification History:
 *     2026-09-03 - Added Theme manager (Dark/Light toggle with localStorage),
 *                  dynamic canvas theme re-rendering, and refined terminal controllers.
 * Synopsis    : Complete application controller for TradeSage AI trading terminal.
 */

const API_BASE = "http://localhost:5000";

const State = {
  activeTab: "overview",
  authMode: "login",
  equityPoints: [],
  userEmail: null
};

/* --- THEME MANAGER (DARK / LIGHT TOGGLE) --- */
const Theme = {
  current: "dark",

  init() {
    const saved = localStorage.getItem("tradesage-theme");
    if (saved) {
      this.current = saved;
    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
      this.current = "light";
    } else {
      this.current = "dark";
    }
    this.apply(this.current);
  },

  toggle() {
    this.current = this.current === "dark" ? "light" : "dark";
    localStorage.setItem("tradesage-theme", this.current);
    this.apply(this.current);
  },

  apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const btn = document.getElementById("btn-themeToggle");
    if (btn) {
      btn.innerHTML = theme === "dark"
        ? `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`
        : `<svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>`;
      btn.title = `Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`;
    }
    // Redraw chart if visible
    if (State.equityPoints && State.equityPoints.length > 0) {
      Backtest.drawChart(State.equityPoints);
    }
  }
};

/* --- TOAST MESSAGING --- */
const Toast = {
  show(message, type = "info", duration = 3500) {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const msg = document.createElement("div");
    msg.className = `toast-msg ${type}`;
    msg.textContent = message;
    stack.appendChild(msg);

    setTimeout(() => {
      msg.style.opacity = "0";
      msg.style.transform = "translateX(10px)";
      msg.style.transition = "all 0.2s ease";
      setTimeout(() => msg.remove(), 200);
    }, duration);
  }
};

/* --- NETWORK API CLIENT --- */
const Api = {
  async fetch(path, options = {}) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {})
        }
      });
      const data = await res.json().catch(() => ({}));
      if (data && data.detail && !data.error) {
        data.error = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
      if (res.status === 401 && path !== "/api/login" && path !== "/api/register" && path !== "/api/portfolio") {
        Toast.show("Please log in or register an account first.", "info");
        if (typeof Auth !== "undefined" && Auth.openModal) {
          Auth.openModal();
        }
      }
      return { ok: res.ok, status: res.status, data };
    } catch (err) {
      return { ok: false, status: 0, data: { error: `Server offline (${err.message})` } };
    }
  }
};

/* --- NAVIGATION & TAB ROUTING --- */
function switchTab(tabKey) {
  State.activeTab = tabKey;
  document.querySelectorAll(".term-tab").forEach(tab => tab.classList.remove("active"));
  document.querySelectorAll(".tab-workspace").forEach(view => view.classList.remove("active"));

  const targetTab = Array.from(document.querySelectorAll(".term-tab")).find(t => t.getAttribute("data-tab") === tabKey);
  if (targetTab) targetTab.classList.add("active");

  const targetView = document.getElementById(`tab-${tabKey}`);
  if (targetView) targetView.classList.add("active");

  if (tabKey === "backtest" && State.equityPoints.length > 0) {
    setTimeout(() => Backtest.drawChart(State.equityPoints), 50);
  }
}

/* --- MODAL CONTROLS --- */
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("active");
}

/* --- AUTHENTICATION MODULE (FR-1) --- */
const Auth = {
  openModal() {
    this.setMode("login");
    openModal("modal-auth");
  },

  setMode(mode) {
    State.authMode = mode;
    const title = document.getElementById("lbl-authTitle");
    const submitBtn = document.getElementById("btn-authSubmit");
    const tabLogin = document.getElementById("btn-authTabLogin");
    const tabRegister = document.getElementById("btn-authTabRegister");

    if (mode === "login") {
      title.textContent = "Trader Login";
      submitBtn.textContent = "Sign In";
      tabLogin.classList.add("btn-primary");
      tabLogin.classList.remove("btn-subtle");
      tabRegister.classList.add("btn-subtle");
      tabRegister.classList.remove("btn-primary");
    } else {
      title.textContent = "Register New Account";
      submitBtn.textContent = "Register";
      tabRegister.classList.add("btn-primary");
      tabRegister.classList.remove("btn-subtle");
      tabLogin.classList.add("btn-subtle");
      tabLogin.classList.remove("btn-primary");
    }
  },

  async submit() {
    const email = document.getElementById("txt-authEmail").value.trim();
    const password = document.getElementById("txt-authPassword").value;
    if (!email || !password) {
      Toast.show("Please provide email and password.", "error");
      return;
    }

    const path = State.authMode === "login" ? "/api/login" : "/api/register";
    const { ok, data } = await Api.fetch(path, {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    if (!ok) {
      Toast.show(data.error || "Authentication failed.", "error");
      return;
    }

    if (State.authMode === "register") {
      Toast.show("Registered successfully. Logging in...", "success");
      const loginRes = await Api.fetch("/api/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      if (loginRes.ok) this.handleLoginSuccess(loginRes.data.email);
    } else {
      this.handleLoginSuccess(data.email);
    }
    closeModal("modal-auth");
  },

  handleLoginSuccess(email) {
    State.userEmail = email;
    document.getElementById("userPill").innerHTML = `Trader: <strong>${email}</strong>`;
    document.getElementById("btn-openAuth").style.display = "none";
    document.getElementById("btn-logout").style.display = "inline-flex";
    Toast.show(`Connected as ${email}`, "success");
    loadAllTerminalData();
  },

  async logout() {
    await Api.fetch("/api/logout", { method: "POST" });
    State.userEmail = null;
    document.getElementById("userPill").textContent = "Not Logged In";
    document.getElementById("btn-openAuth").style.display = "inline-flex";
    document.getElementById("btn-logout").style.display = "none";
    Toast.show("Disconnected session.", "info");
    Portfolio.reset();
  }
};

/* --- PORTFOLIO MODULE (FR-2, FR-6.1) --- */
const Portfolio = {
  async load() {
    const { ok, data } = await Api.fetch("/api/portfolio");
    if (!ok) return;

    const holdings = data.holdings || [];
    const totalPnl = data.totalPnl || 0;

    // Overview Metric Cell
    const totalPnlEl = document.getElementById("stat-totalPnl");
    totalPnlEl.textContent = `${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`;
    totalPnlEl.className = `metric-data mono ${totalPnl >= 0 ? "val-pos" : "val-neg"}`;

    document.getElementById("tabCountHoldings").textContent = holdings.length;

    // Holdings Table
    const tbody = document.getElementById("tbl-holdings-body");
    if (holdings.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 24px;">No holdings recorded. Click "+ Add Position" to start.</td></tr>`;
      return;
    }

    tbody.innerHTML = holdings.map(h => {
      const isPos = h.unrealizedPnl >= 0;
      const typeTag = h.assetType === "crypto" ? "tag-crypto" : "tag-stock";
      return `
        <tr>
          <td><strong class="mono">${h.assetSymbol}</strong></td>
          <td><span class="tag ${typeTag}">${h.assetType}</span></td>
          <td class="mono">${Number(h.quantity).toLocaleString()}</td>
          <td class="mono">$${Number(h.livePrice).toFixed(2)}</td>
          <td class="mono ${isPos ? 'val-pos' : 'val-neg'}">
            ${isPos ? '+' : ''}$${Number(h.unrealizedPnl).toFixed(2)} (${isPos ? '+' : ''}${Number(h.unrealizedPnlPct).toFixed(1)}%)
          </td>
          <td>
            <button class="btn btn-subtle btn-xs" onclick="Signals.quickAnalyze('${h.assetSymbol}', '${h.assetType}')">Inspect</button>
          </td>
        </tr>
      `;
    }).join("");

    this.loadComparison();
  },

  async loadComparison() {
    const { ok, data } = await Api.fetch("/api/portfolio/comparison");
    if (!ok) return;

    if (data.stock) {
      const pnl = data.stock.totalPnl || 0;
      const el = document.getElementById("stat-stockPnl");
      el.textContent = `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}`;
      el.className = `metric-data mono ${pnl >= 0 ? "val-pos" : "val-neg"}`;
      document.getElementById("stat-stockCount").textContent = `${data.stock.holdingCount} position(s)`;
    }

    if (data.crypto) {
      const pnl = data.crypto.totalPnl || 0;
      const el = document.getElementById("stat-cryptoPnl");
      el.textContent = `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}`;
      el.className = `metric-data mono ${pnl >= 0 ? "val-pos" : "val-neg"}`;
      document.getElementById("stat-cryptoCount").textContent = `${data.crypto.holdingCount} position(s)`;
    }
  },

  openAddModal() {
    document.getElementById("txt-holdDate").value = new Date().toISOString().split("T")[0];
    openModal("modal-addHolding");
  },

  async submitAdd() {
    const symbol = document.getElementById("txt-holdSymbol").value.trim().toUpperCase();
    const assetType = document.getElementById("cmb-holdType").value;
    const quantity = parseFloat(document.getElementById("txt-holdQty").value);
    const buyPrice = parseFloat(document.getElementById("txt-holdPrice").value);
    const buyDate = document.getElementById("txt-holdDate").value;

    if (!symbol || !buyDate || Number.isNaN(quantity) || Number.isNaN(buyPrice)) {
      Toast.show("Please enter valid position details.", "error");
      return;
    }

    const { ok, data } = await Api.fetch("/api/holdings", {
      method: "POST",
      body: JSON.stringify({ assetSymbol: symbol, assetType, quantity, buyPrice, buyDate })
    });

    if (!ok) {
      Toast.show(data.error || "Failed to record holding.", "error");
      return;
    }

    Toast.show(`Recorded position for ${symbol}`, "success");
    closeModal("modal-addHolding");
    document.getElementById("txt-holdSymbol").value = "";
    document.getElementById("txt-holdQty").value = "";
    document.getElementById("txt-holdPrice").value = "";
    this.load();
  },

  openCsvModal() {
    openModal("modal-csv");
  },

  async submitCsv() {
    const fileInput = document.getElementById("file-csvUpload");
    if (!fileInput.files.length) {
      Toast.show("Select a CSV file first.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
      const res = await fetch(`${API_BASE}/api/holdings/import`, {
        method: "POST",
        credentials: "include",
        body: formData
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        Toast.show(data.error || "Import error", "error");
        return;
      }
      Toast.show(`Imported ${data.imported} position(s)`, "success");
      closeModal("modal-csv");
      fileInput.value = "";
      this.load();
    } catch (err) {
      Toast.show(`Import failed: ${err.message}`, "error");
    }
  },

  reset() {
    document.getElementById("stat-totalPnl").textContent = "—";
    document.getElementById("stat-stockPnl").textContent = "—";
    document.getElementById("stat-cryptoPnl").textContent = "—";
    document.getElementById("tbl-holdings-body").innerHTML = `
      <tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 24px;">Log in to access your positions.</td></tr>
    `;
    document.getElementById("tabCountHoldings").textContent = "0";
  }
};

/* --- AI SIGNAL ENGINE & DIVERGENCE DETECTOR (FR-3) --- */
const Signals = {
  quickAnalyze(symbol, type) {
    document.getElementById("txt-signalSymbol").value = symbol;
    document.getElementById("cmb-signalType").value = type;
    switchTab("signal");
    this.generate();
  },

  async generate() {
    const symbol = document.getElementById("txt-signalSymbol").value.trim().toUpperCase();
    const assetType = document.getElementById("cmb-signalType").value;
    const btn = document.getElementById("btn-genSignals");
    const container = document.getElementById("modelsMatrix");
    const divAlert = document.getElementById("divergenceAlert");

    if (!symbol) {
      Toast.show("Asset symbol required.", "error");
      return;
    }

    btn.disabled = true;
    divAlert.style.display = "none";
    Toast.show(`Computing dual-model signals for ${symbol}... (~15s cold start)`, "info", 4000);

    const { ok, data } = await Api.fetch(`/api/signal?assetSymbol=${encodeURIComponent(symbol)}&assetType=${assetType}`);
    btn.disabled = false;

    if (!ok) {
      Toast.show(data.error || "Signal generation error.", "error");
      return;
    }

    Toast.show(`Signals ready for ${symbol}`, "success");
    this.renderMatrix(data.signals, symbol);
    Watchlist.load();
  },

  renderMatrix(signals, symbol) {
    const container = document.getElementById("modelsMatrix");
    const divAlert = document.getElementById("divergenceAlert");
    container.innerHTML = "";

    if (!signals || signals.length === 0) {
      container.innerHTML = `<div class="matrix-cell" style="grid-column: 1 / -1; text-align: center;">No signals generated.</div>`;
      return;
    }

    // SIGNATURE ELEMENT: Detect divergence between models
    if (signals.length >= 2) {
      const [m1, m2] = signals;
      if (m1.predictedDirection !== m2.predictedDirection) {
        divAlert.style.display = "flex";
        document.getElementById("divergenceMsg").textContent = 
          `${m1.modelUsed.toUpperCase()} predicted ${m1.predictedDirection.toUpperCase()} while ${m2.modelUsed.toUpperCase()} predicted ${m2.predictedDirection.toUpperCase()}. Exercise caution due to conflicting indicator signals.`;
      } else {
        divAlert.style.display = "none";
      }
    }

    signals.forEach(s => {
      const isLstm = s.modelUsed === "lstm";
      const modelName = isLstm ? "Shallow LSTM (Deep Neural Net)" : "Random Forest (Baseline)";
      const dir = (s.predictedDirection || "neutral").toLowerCase();
      const confPct = Math.round((s.confidenceScore || 0) * 100);

      const maxContr = Math.max(...(s.topContributingFeatures || []).map(f => Math.abs(f.contribution)), 0.001);
      const shapItems = (s.topContributingFeatures || []).map(f => {
        const val = f.contribution;
        const isPos = val >= 0;
        const pct = Math.min(Math.round((Math.abs(val) / maxContr) * 100), 100);
        return `
          <div class="shap-row">
            <span class="shap-label" title="${f.feature}">${f.feature}</span>
            <div class="shap-track">
              <div class="shap-bar ${isPos ? 'pos' : 'neg'}" style="width: ${pct}%;"></div>
            </div>
            <span class="mono ${isPos ? 'val-pos' : 'val-neg'}" style="text-align: right;">${isPos ? '+' : ''}${val.toFixed(3)}</span>
          </div>
        `;
      }).join("");

      const cell = document.createElement("div");
      cell.className = "matrix-cell";
      cell.innerHTML = `
        <div class="matrix-head">
          <span class="model-title">${modelName}</span>
          <span class="model-spec mono">${s.horizonDays}D Horizon</span>
        </div>

        <div class="signal-callout">
          <div>
            <div style="font-size: 11px; color: var(--text-dim); text-transform: uppercase;">Directional Bias</div>
            <div class="callout-dir ${dir}">${dir.toUpperCase()}</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 11px; color: var(--text-dim); text-transform: uppercase;">Confidence</div>
            <div class="mono" style="font-size: 18px; font-weight: 700;">${confPct}%</div>
          </div>
        </div>

        <div class="shap-box">
          <div class="shap-legend">
            <span>SHAP Factor Impact</span>
            <span>Weight</span>
          </div>
          ${shapItems || '<span style="color:var(--text-dim); font-size:12px;">No feature attribution.</span>'}
        </div>
      `;
      container.appendChild(cell);
    });
  }
};

/* --- STRATEGY BACKTESTER MODULE (FR-4) --- */
const Backtest = {
  async run() {
    const assetSymbol = document.getElementById("txt-backtestSymbol").value.trim().toUpperCase();
    const assetType = document.getElementById("cmb-backtestType").value;
    const modelUsed = document.getElementById("cmb-backtestModel").value;
    const btn = document.getElementById("btn-runBacktest");

    if (!assetSymbol) {
      Toast.show("Asset symbol required.", "error");
      return;
    }

    btn.disabled = true;
    Toast.show(`Running strategy backtest for ${assetSymbol}...`, "info", 2000);

    const { ok, data } = await Api.fetch("/api/backtest", {
      method: "POST",
      body: JSON.stringify({ assetSymbol, assetType, modelUsed })
    });

    btn.disabled = false;

    if (!ok) {
      Toast.show(data.error || "Backtest error.", "error");
      return;
    }

    Toast.show("Backtest evaluation complete.", "success");

    document.getElementById("stat-sharpeRatio").textContent = Number(data.sharpeRatio).toFixed(2);
    document.getElementById("stat-winRate").textContent = `${(Number(data.winRate) * 100).toFixed(1)}%`;
    document.getElementById("stat-maxDrawdown").textContent = `${(Number(data.maxDrawdown) * 100).toFixed(1)}%`;
    document.getElementById("stat-totalTrades").textContent = data.totalTrades;

    State.equityPoints = data.equityCurve || [];
    this.drawChart(State.equityPoints);
  },

  drawChart(points) {
    const canvas = document.getElementById("tbl-equityCanvas");
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = rect.width || 800;
    const height = 220;

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Read active CSS variables
    const computedStyles = getComputedStyle(document.documentElement);
    const colorGrid = computedStyles.getPropertyValue("--chart-grid").trim() || "#202534";
    const colorBaseline = computedStyles.getPropertyValue("--chart-baseline").trim() || "rgba(245, 158, 11, 0.45)";
    const colorLine = computedStyles.getPropertyValue("--chart-line").trim() || "#38bdf8";
    const colorFillStart = computedStyles.getPropertyValue("--chart-fill-start").trim() || "rgba(56, 189, 248, 0.28)";
    const colorFillEnd = computedStyles.getPropertyValue("--chart-fill-end").trim() || "rgba(56, 189, 248, 0.0)";
    const colorText = computedStyles.getPropertyValue("--text-dim").trim() || "#64748b";

    if (!points || points.length < 2) {
      ctx.fillStyle = colorText;
      ctx.font = "12.5px Plus Jakarta Sans, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Run a backtest above to render cumulative equity curve.", width / 2, height / 2);
      return;
    }

    const padX = 42;
    const padY = 20;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = (max - min) || 0.01;

    const getX = (i) => padX + (i / (points.length - 1)) * (width - padX * 2);
    const getY = (val) => height - padY - ((val - min) / range) * (height - padY * 2);

    // 1. Gridlines
    ctx.strokeStyle = colorGrid;
    ctx.lineWidth = 1;
    ctx.font = "11px JetBrains Mono, monospace";
    ctx.fillStyle = colorText;
    ctx.textAlign = "right";

    const steps = 4;
    for (let s = 0; s <= steps; s++) {
      const val = min + (range * s) / steps;
      const y = getY(val);
      ctx.beginPath();
      ctx.moveTo(padX, y);
      ctx.lineTo(width - padX, y);
      ctx.stroke();
      ctx.fillText(val.toFixed(2), padX - 8, y + 4);
    }

    // 2. Baseline at 1.0 (starting equity)
    const baseLineY = getY(1.0);
    ctx.strokeStyle = colorBaseline;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padX, baseLineY);
    ctx.lineTo(width - padX, baseLineY);
    ctx.stroke();
    ctx.setLineDash([]);

    // 3. Area Fill
    const gradient = ctx.createLinearGradient(0, padY, 0, height - padY);
    gradient.addColorStop(0, colorFillStart);
    gradient.addColorStop(1, colorFillEnd);

    ctx.beginPath();
    ctx.moveTo(getX(0), getY(points[0]));
    for (let i = 1; i < points.length; i++) ctx.lineTo(getX(i), getY(points[i]));
    ctx.lineTo(getX(points.length - 1), height - padY);
    ctx.lineTo(getX(0), height - padY);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // 4. Stroke
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(points[0]));
    for (let i = 1; i < points.length; i++) ctx.lineTo(getX(i), getY(points[i]));
    ctx.strokeStyle = colorLine;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
};

// Canvas Hover Tooltip
const chartCanvas = document.getElementById("tbl-equityCanvas");
if (chartCanvas) {
  chartCanvas.addEventListener("mousemove", (e) => {
    if (!State.equityPoints || State.equityPoints.length < 2) return;
    const rect = chartCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const padX = 42;
    const width = rect.width;

    if (x < padX || x > width - padX) return;

    const idx = Math.round(((x - padX) / (width - padX * 2)) * (State.equityPoints.length - 1));
    const val = State.equityPoints[idx];
    if (val !== undefined) {
      document.getElementById("lbl-chartHoverVal").innerHTML = `Trade #${idx + 1}: <strong>${val.toFixed(3)}x</strong> equity`;
    }
  });
}

/* --- WATCHLIST MODULE (FR-5) --- */
const Watchlist = {
  async load() {
    const { ok, data } = await Api.fetch("/api/watchlist");
    if (!ok) return;

    const list = data || [];
    document.getElementById("tabCountWatchlist").textContent = list.length;

    const alertCount = list.filter(item => item.signalChanged).length;
    document.getElementById("stat-alertsCount").textContent = alertCount;

    const tbody = document.getElementById("tbl-watchlist-body");
    if (list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 24px;">Watchlist is empty.</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(item => {
      const typeTag = item.assetType === "crypto" ? "tag-crypto" : "tag-stock";
      const alertBadge = item.signalChanged
        ? `<span class="tag tag-alert">Shift Detected</span>`
        : `<span style="color:var(--text-dim); font-size:12px;">Unchanged</span>`;

      return `
        <tr>
          <td><strong class="mono">${item.assetSymbol}</strong></td>
          <td><span class="tag ${typeTag}">${item.assetType}</span></td>
          <td class="mono"><strong>${(item.latestSignal || '—').toUpperCase()}</strong></td>
          <td>${alertBadge}</td>
          <td>
            <div class="control-row">
              <button class="btn btn-subtle btn-xs" onclick="Signals.quickAnalyze('${item.assetSymbol}', '${item.assetType}')">Inspect</button>
              <button class="btn btn-danger-outline btn-xs" onclick="Watchlist.remove(${item.watchlistId})">Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  },

  async add() {
    const symbol = document.getElementById("txt-watchSymbol").value.trim().toUpperCase();
    const assetType = document.getElementById("cmb-watchType").value;

    if (!symbol) {
      Toast.show("Asset symbol required.", "error");
      return;
    }

    const { ok, data } = await Api.fetch("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ assetSymbol: symbol, assetType })
    });

    if (!ok) {
      Toast.show(data.error || "Failed to add asset.", "error");
      return;
    }

    Toast.show(`Added ${symbol} to monitor`, "success");
    document.getElementById("txt-watchSymbol").value = "";
    this.load();
  },

  async remove(id) {
    const { ok } = await Api.fetch(`/api/watchlist/${id}`, { method: "DELETE" });
    if (ok) {
      Toast.show("Item removed.", "info");
      this.load();
    }
  }
};

/* --- AUDIT FEEDBACK LOOP MODULE (FR-6.2) --- */
const Audit = {
  async load() {
    const symbol = document.getElementById("txt-historySymbol").value.trim().toUpperCase();
    if (!symbol) return;

    const { ok, data } = await Api.fetch(`/api/signal-history?assetSymbol=${encodeURIComponent(symbol)}`);
    const tbody = document.getElementById("tbl-history-body");

    if (!ok || !data || data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 24px;">No historical audit records for ${symbol}.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map(row => {
      let outcomeTag = `<span class="tag" style="background:var(--bg-input); color:var(--text-dim); border:1px solid var(--border-subtle);">PENDING</span>`;
      if (row.status !== "pending") {
        outcomeTag = row.wasCorrect
          ? `<span class="tag tag-up">CORRECT</span>`
          : `<span class="tag tag-down">MISSED</span>`;
      }

      return `
        <tr>
          <td class="mono">${row.generatedAt ? row.generatedAt.slice(0, 10) : '—'}</td>
          <td><span class="tag ${row.modelUsed === 'lstm' ? 'tag-crypto' : 'tag-stock'}">${row.modelUsed}</span></td>
          <td class="mono"><strong>${(row.predictedDirection || '—').toUpperCase()}</strong></td>
          <td class="mono">${(row.actualDirection || '—').toUpperCase()}</td>
          <td>${outcomeTag}</td>
        </tr>
      `;
    }).join("");
  }
};

/* --- ADMIN MODULE (FR-7) --- */
const Admin = {
  async loadTracked() {
    const { ok, data } = await Api.fetch("/api/admin/tracked-assets");
    const tbody = document.getElementById("tbl-tracked-body");
    if (!ok || !data) return;

    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-dim); padding: 18px;">No tracked assets in registry.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map(a => `
      <tr>
        <td><strong class="mono">${a.assetSymbol}</strong></td>
        <td><span class="tag ${a.assetType === 'crypto' ? 'tag-crypto' : 'tag-stock'}">${a.assetType}</span></td>
        <td><button class="btn btn-danger-outline btn-xs" onclick="Admin.removeTracked(${a.trackedAssetId})">Remove</button></td>
      </tr>
    `).join("");
  },

  async addTracked() {
    const symbol = document.getElementById("txt-adminSymbol").value.trim().toUpperCase();
    const assetType = document.getElementById("cmb-adminType").value;
    if (!symbol) return;

    const { ok } = await Api.fetch("/api/admin/tracked-assets", {
      method: "POST",
      body: JSON.stringify({ assetSymbol: symbol, assetType })
    });

    if (ok) {
      Toast.show(`Tracked asset registered: ${symbol}`, "success");
      document.getElementById("txt-adminSymbol").value = "";
      this.loadTracked();
    }
  },

  async removeTracked(id) {
    const { ok } = await Api.fetch(`/api/admin/tracked-assets/${id}`, { method: "DELETE" });
    if (ok) {
      Toast.show("Asset unregistered.", "info");
      this.loadTracked();
    }
  },

  async loadConfig() {
    const { ok, data } = await Api.fetch("/api/admin/config");
    if (ok && data.retrainIntervalDays) {
      document.getElementById("txt-retrainDays").value = data.retrainIntervalDays;
    }
  },

  async saveConfig() {
    const days = parseInt(document.getElementById("txt-retrainDays").value, 10);
    if (!days) return;

    const { ok } = await Api.fetch("/api/admin/config", {
      method: "POST",
      body: JSON.stringify({ retrainIntervalDays: days })
    });

    if (ok) Toast.show(`Retrain interval configured to ${days} days.`, "success");
  },

  async checkHealth() {
    const el = document.getElementById("box-feedHealth");
    el.innerHTML = `<span style="color: var(--fin-neutral);">Testing data feeds...</span>`;

    const { ok, data } = await Api.fetch("/api/admin/health");
    if (!ok) {
      el.innerHTML = `<span class="val-neg">Health check diagnostic call failed.</span>`;
      return;
    }

    if (!data || data.length === 0) {
      el.innerHTML = `No tracked assets registered to test.`;
      return;
    }

    el.innerHTML = data.map(h => {
      const isOk = h.status.toLowerCase() === "ok";
      return `<div><span style="color:${isOk ? '#00d68f' : '#ff3b5c'}; font-weight:bold;">[${h.status.toUpperCase()}]</span> ${h.assetSymbol} (${h.source})</div>`;
    }).join("");
  }
};

/* --- INITIAL BOOT SEQUENCE --- */
function loadAllTerminalData() {
  Portfolio.load();
  Watchlist.load();
  Admin.loadTracked();
  Admin.loadConfig();
}

window.addEventListener("DOMContentLoaded", () => {
  Theme.init();

  // Check active session silently
  Api.fetch("/api/portfolio").then(({ ok }) => {
    if (ok) {
      document.getElementById("userPill").innerHTML = `Trader: <strong>Active Session</strong>`;
      document.getElementById("btn-openAuth").style.display = "none";
      document.getElementById("btn-logout").style.display = "inline-flex";
      loadAllTerminalData();
    } else {
      Portfolio.reset();
    }
  });

  // Empty canvas baseline
  Backtest.drawChart([]);
});

window.addEventListener("resize", () => {
  if (State.equityPoints.length > 0) {
    Backtest.drawChart(State.equityPoints);
  }
});
