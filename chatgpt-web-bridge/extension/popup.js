const DEFAULT_BRIDGE = "http://127.0.0.1:8765";

async function load() {
  const { bridgeUrl } = await chrome.storage.local.get("bridgeUrl");
  document.getElementById("bridgeUrl").value = bridgeUrl || DEFAULT_BRIDGE;
  check();
}

async function check() {
  const base = (document.getElementById("bridgeUrl").value || DEFAULT_BRIDGE).replace(/\/+$/, "");
  const el = document.getElementById("status");
  try {
    const r = await fetch(base + "/health", { headers: { "X-Bridge-Client": "huashu-gpt-image-ext" } });
    const j = await r.json();
    el.textContent = "桥在线 ✓ (pending " + j.pending + ")";
    el.className = "ok";
  } catch (e) {
    el.textContent = "桥未启动 — 先跑 server.py";
    el.className = "bad";
  }
}

document.getElementById("save").addEventListener("click", async () => {
  const url = document.getElementById("bridgeUrl").value.trim() || DEFAULT_BRIDGE;
  await chrome.storage.local.set({ bridgeUrl: url });
  check();
});

load();
