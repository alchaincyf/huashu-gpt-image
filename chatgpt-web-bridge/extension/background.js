// background.js — service worker：本地桥 <-> chatgpt.com 标签页 的调度中枢
//
// 流程：长轮询 server 的 /poll 拿任务 → 找/建 chatgpt.com 标签 → 把任务交给 content.js
//       → content.js 生完图通过 runtime 消息回传 → 这里取图片字节 → POST /result。
//
// MV3 service worker 随时可能被杀，所以：
//   1. 用 chrome.alarms 每 20s 唤醒一次，重启轮询循环；
//   2. 当前任务存在 storage.session，SW 重启后不会重复派发；
//   3. content.js 用 runtime.sendMessage 回传结果，这个动作本身会唤醒被杀的 SW。

const DEFAULT_BRIDGE = "http://127.0.0.1:8765";
// 桥要求这个自定义头：网页发不出带自定义头的「简单请求」，所以这一行就把
// 「任意网页偷 /poll 里的任务」这条路堵死了（详见 server.py 的「三道门」）。
const CLIENT_HEADERS = { "X-Bridge-Client": "huashu-gpt-image-ext" };

async function bridgeBase() {
  const { bridgeUrl } = await chrome.storage.local.get("bridgeUrl");
  return (bridgeUrl || DEFAULT_BRIDGE).replace(/\/+$/, "");
}

let polling = false;

async function pollLoop() {
  if (polling) return;
  polling = true;
  try {
    // 有正在处理的任务就先不抢新活
    const { activeJob } = await chrome.storage.session.get("activeJob");
    if (activeJob) {
      polling = false;
      return;
    }
    const base = await bridgeBase();
    let resp;
    try {
      resp = await fetch(base + "/poll", { method: "GET", headers: CLIENT_HEADERS });
    } catch (e) {
      // 桥没开，安静退出，等下次 alarm 再试
      polling = false;
      return;
    }
    if (resp.status === 204) {
      polling = false;
      // 立刻再轮询，保持 SW 温热
      setTimeout(() => pollLoop(), 50);
      return;
    }
    if (!resp.ok) {
      polling = false;
      return;
    }
    const job = await resp.json();
    await chrome.storage.session.set({ activeJob: job });
    polling = false;
    dispatchJob(job).catch((e) => reportError(job.jobId, String(e)));
  } catch (e) {
    polling = false;
  }
}

async function ensureChatGptTab() {
  const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*", "https://chat.openai.com/*"] });
  if (tabs.length) return tabs[0];
  const tab = await chrome.tabs.create({ url: "https://chatgpt.com/", active: false });
  // 等加载完成
  await new Promise((resolve) => {
    const listener = (tabId, info) => {
      if (tabId === tab.id && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(resolve, 15000); // 兜底
  });
  return tab;
}

async function dispatchJob(job) {
  const tab = await ensureChatGptTab();
  // content.js 是声明式注入，但保险起见再注入一次（幂等）
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
  } catch (e) { /* 已注入会报错，忽略 */ }
  // 重试几次 sendMessage，给页面留出 ready 时间
  for (let i = 0; i < 5; i++) {
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "GENERATE", job });
      return; // 派发成功；结果走 runtime 消息回来
    } catch (e) {
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
  await reportError(job.jobId, "无法把任务交给 chatgpt.com 标签页（content.js 未就绪）");
}

// content.js 生完图回传
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "GENERATE_RESULT") {
    handleResult(msg).finally(() => sendResponse({ ack: true }));
    return true; // 异步
  }
});

async function handleResult(msg) {
  const { jobId, ok, imageUrl, imageBase64, mime, error } = msg;
  // resultToken 必须在清掉 activeJob 之前取出来，否则回 /result 会被桥 403
  const resultToken = await tokenFor(jobId);
  try {
    if (!ok) {
      await reportError(jobId, error || "content.js 报告失败", resultToken);
      return;
    }
    let b64 = imageBase64;
    let m = mime || "image/png";
    if (!b64 && imageUrl) {
      const r = await fetch(imageUrl); // SW 有 oaiusercontent host 权限
      const blob = await r.blob();
      m = blob.type || m;
      b64 = await blobToBase64(blob);
    }
    if (!b64) {
      await reportError(jobId, "没拿到图片字节", resultToken);
      return;
    }
    await postResult({ jobId, resultToken, ok: true, imageBase64: b64, mime: m });
  } catch (e) {
    await reportError(jobId, "取图片字节失败: " + String(e), resultToken);
  } finally {
    await chrome.storage.session.remove("activeJob");
    setTimeout(() => pollLoop(), 50);
  }
}

// 当前任务的 resultToken（存在 storage.session 的 activeJob 里，随任务一起从 /poll 拿到）
async function tokenFor(jobId) {
  const { activeJob } = await chrome.storage.session.get("activeJob");
  return activeJob && activeJob.jobId === jobId ? activeJob.resultToken : undefined;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result).split(",")[1]);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}

async function postResult(payload) {
  const base = await bridgeBase();
  try {
    await fetch(base + "/result", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...CLIENT_HEADERS },
      body: JSON.stringify(payload),
    });
  } catch (e) { /* 桥可能已关，忽略 */ }
}

async function reportError(jobId, error, resultToken) {
  const token = resultToken ?? (await tokenFor(jobId));
  await chrome.storage.session.remove("activeJob");
  await postResult({ jobId, resultToken: token, ok: false, error });
  setTimeout(() => pollLoop(), 50);
}

// 保活 + 启动
chrome.alarms.create("keepalive", { periodInMinutes: 0.34 }); // ~20s
chrome.alarms.onAlarm.addListener(() => pollLoop());
chrome.runtime.onStartup.addListener(() => pollLoop());
chrome.runtime.onInstalled.addListener(() => pollLoop());
pollLoop();
