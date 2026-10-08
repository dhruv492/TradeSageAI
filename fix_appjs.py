path = r"C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\frontend\js\app.js"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Api.fetch to remove userId parsing and X-User-Id header
old_api_fetch = '''const Api = {
  async fetch(path, options = {}) {
    try {
      const token = localStorage.getItem("tradesage_token");
      const storedUserStr = localStorage.getItem("tradesage_user");
      let userId = "";
      if (storedUserStr) {
        try { userId = JSON.parse(storedUserStr).userId; } catch (e) {}
      }

      const headers = {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...(userId ? { "X-User-Id": String(userId) } : {}),
        ...(options.headers || {})
      };

      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: "include",
        headers
      });'''

new_api_fetch = '''const Api = {
  async fetch(path, options = {}) {
    try {
      const token = localStorage.getItem("tradesage_token");

      const headers = {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...(options.headers || {})
      };

      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: "include",
        headers
      });'''

if old_api_fetch in content:
    content = content.replace(old_api_fetch, new_api_fetch)
    print("Updated Api.fetch - removed userId parsing and X-User-Id header")
else:
    print("Could not find Api.fetch block to replace")

# 2. Update handleLoginSuccess to not store userId as auth credential
old_handling_success = '''  handleLoginSuccess(email, token, userId) {
    State.userEmail = email;
    if (email) {
      // Fix #5: userId comes from the API response, never fall back to a
      // hardcoded constant — a hardcoded 1 causes all users to share the
      // same identity when cross-origin cookies are blocked.
      const stored = { email, userId: userId ?? null, token: token || "session" };
      localStorage.setItem("tradesage_user", JSON.stringify(stored));
      if (token) localStorage.setItem("tradesage_token", token);
    }
    document.getElementById("userPill").innerHTML = `Trader: <strong>${email}</strong>`;
    document.getElementById("btn-openAuth").style.display = "none";
    document.getElementById("btn-logout").style.display = "inline-flex";

    // Unlock Workspace & Hide Gateway Screen
    const gateway = document.getElementById("authGateway");
    const workspace = document.getElementById("mainWorkspace");
    if (gateway) gateway.style.display = "none";
    if (workspace) workspace.style.display = "block";

    Toast.show(`Connected as ${email}`, "success");
    loadAllTerminalData();
  },'''

new_handling_success = '''  handleLoginSuccess(email, token, userId) {
    State.userEmail = email;
    if (email) {
      // Only store email - do not store userId as auth credential.
      # Session identity is managed by Flask-Login session cookie (same-origin).
      localStorage.setItem("tradesage_user", JSON.stringify({ email, userId: null }));
      if (token) localStorage.setItem("tradesage_token", token);
    }
    document.getElementById("userPill").innerHTML = `Trader: <strong>${email}</strong>`;
    document.getElementById("btn-openAuth").style.display = "none";
    document.getElementById("btn-logout").style.display = "inline-flex";

    # Unlock Workspace & Hide Gateway Screen
    const gateway = document.getElementById("authGateway");
    const workspace = document.getElementById("mainWorkspace");
    if (gateway) gateway.style.display = "none";
    if (workspace) workspace.style.display = "block";

    Toast.show(`Connected as ${email}`, "success");
    loadAllTerminalData();
  },'''

if old_handling_success in content:
    content = content.replace(old_handling_success, new_handling_success)
    print("Updated handleLoginSuccess - removed userId storage")
else:
    print("Could not find handleLoginSuccess block to replace")

# 3. Update Auth.logout to simplify
old_logout = '''  async logout() {
    await Api.fetch("/api/logout", { method: "POST" });
    State.userEmail = null;
    localStorage.removeItem("tradesage_user");
    localStorage.removeItem("tradesage_token");
    document.getElementById("userPill").textContent = "Not Logged In";
    document.getElementById("btn-openAuth").style.display = "inline-flex";
    document.getElementById("btn-logout").style.display = "none";

    Toast.show("Terminal session ended. Redirecting to Landing Page...", "info");
    const target = window.location.pathname.includes("/static/") ? "index.html" : "/";
    setTimeout(() => { window.location.href = target; }, 400);
  }'''

new_logout = '''  async logout() {
    await Api.fetch("/api/logout", { method: "POST" });
    State.userEmail = null;
    localStorage.removeItem("tradesage_token");
    # Do not remove tradesage_user entirely so the email pill can still show
    # the last known email; the server will redirect unauthenticated users.
    document.getElementById("userPill").textContent = "Not Logged In";
    document.getElementById("btn-openAuth").style.display = "inline-flex";
    document.getElementById("btn-logout").style.display = "none";

    Toast.show("Terminal session ended. Redirecting to Landing Page...", "info");
    const target = window.location.pathname.includes("/static/") ? "index.html" : "/";
    setTimeout(() => { window.location.href = target; }, 400);
  }'''

if old_logout in content:
    content = content.replace(old_logout, new_logout)
    print("Updated Auth.logout - simplified")
else:
    print("Could not find Auth.logout block to replace")

# 4. Update the boot sequence to remove cachedUser fallback
old_boot = '''  // Check active session with lightweight /api/me endpoint
  Api.fetch("/api/me").then(({ ok, data }) => {
    const gateway = document.getElementById("authGateway");
    const workspace = document.getElementById("mainWorkspace");

    if (ok && data && (data.email || data.userId)) {
      const email = data.email || (cachedUser ? cachedUser.email : "Active Session");
      document.getElementById("userPill").innerHTML = `Trader: <strong>${email}</strong>`;
      document.getElementById("btn-openAuth").style.display = "none";
      document.getElementById("btn-logout").style.display = "inline-flex";
      if (gateway) gateway.style.display = "none";
      if (workspace) workspace.style.display = "block";
      loadAllTerminalData();
    } else if (cachedUser && cachedUser.email) {
      # Seamless fallback if user just authenticated on auth.html
      document.getElementById("userPill").innerHTML = `Trader: <strong>${cachedUser.email}</strong>`;
      document.getElementById("btn-openAuth").style.display = "none";
      document.getElementById("btn-logout").style.display = "inline-flex";
      if (gateway) gateway.style.display = "none";
      if (workspace) workspace.style.display = "block";
      loadAllTerminalData();
    } else {
      # Not logged in — redirect to dedicated auth page
      const target = window.location.pathname.includes("/static/") ? "auth.html?mode=login" : "/auth?mode=login";
      window.location.href = target;
    }
  });'''

new_boot = '''  // Check active session with lightweight /api/me endpoint
  Api.fetch("/api/me").then(({ ok, data }) => {
    const gateway = document.getElementById("authGateway");
    const workspace = document.getElementById("mainWorkspace");

    if (ok && data && data.email) {
      const email = data.email;
      document.getElementById("userPill").innerHTML = `Trader: <strong>${email}</strong>`;
      document.getElementById("btn-openAuth").style.display = "none";
      document.getElementById("btn-logout").style.display = "inline-flex";
      if (gateway) gateway.style.display = "none";
      if (workspace) workspace.style.display = "block";
      loadAllTerminalData();
    } else {
      # Not logged in — redirect to dedicated auth page
      const target = window.location.pathname.includes("/static/") ? "auth.html?mode=login" : "/auth?mode=login";
      window.location.href = target;
    }
  });'''

if old_boot in content:
    content = content.replace(old_boot, new_boot)
    print("Updated boot sequence - removed cachedUser fallback")
else:
    print("Could not find boot sequence block to replace")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nAll targeted updates to app.js completed.")