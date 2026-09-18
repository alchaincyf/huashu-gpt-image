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
    // 只看「fetch 通了」会得到一个假的在线状态：server.py 升级后旧扩展的 /poll 全被 403，
    // 而 /health 豁免了那道门照样返回 200 —— 用户看到「在线」，生图却全部 504。
    if (j.lastPollRejected) {
      el.textContent = "桥在线，但扩展被拒 — " + j.lastPollRejected.reason;
      el.className = "bad";
    } else if (j.extensionConnected === false) {
      el.textContent = "桥在线，扩展未连上 — 打开一个 chatgpt.com 标签页，或重载扩展";
      el.className = "bad";
    } else {
      el.textContent = "桥在线 ✓ (pending " + j.pending + ")";
      el.className = "ok";
    }
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
