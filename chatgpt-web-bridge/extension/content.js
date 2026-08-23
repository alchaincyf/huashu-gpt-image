// content.js — 在 chatgpt.com 页面里真正驱动生图的部分。
//
// ⚠️ 选择器是最脆弱的一环：ChatGPT 改版会失效。本文件把所有 DOM 依赖收敛到顶部
//    SELECTORS 常量 + 几个 find* 函数，改版时只改这里。带 ❗TODO 的需对着真实 DOM 校准。
//
// 流程：收到 background 的 GENERATE → 填 prompt（如有参考图先附上）→ 点发送
//      → 等最后一条 assistant 消息里出现生成图 → 把图 URL/字节回传 background。

const SELECTORS = {
  // ❗TODO(DOM校准): 输入框。当前 chatgpt.com 是 ProseMirror contenteditable
  composer: [
    'div#prompt-textarea[contenteditable="true"]',
    'div.ProseMirror[contenteditable="true"]',
    'textarea#prompt-textarea',
    'textarea[data-testid="prompt-textarea"]',
  ],
  // ❗TODO(DOM校准): 发送按钮
  sendButton: [
    'button[data-testid="send-button"]',
    'button[aria-label*="Send"]',
    'button[aria-label*="发送"]',
  ],
  // ❗TODO(DOM校准): 附件/上传图片的 file input（图生图用）
  fileInput: [
    'input[type="file"]',
  ],
  // ❗TODO(DOM校准): assistant 回复气泡
  assistantTurn: [
    'div[data-message-author-role="assistant"]',
    'article[data-testid^="conversation-turn"]',
  ],
  // 生成出来的图：oaiusercontent / files 域，或 alt 含 generated
  generatedImg: [
    'img[src*="oaiusercontent.com"]',
    'img[src*="/backend-api/"]',
    'img[alt*="Generated"]',
  ],
};

const GEN_TIMEOUT_MS = 240000; // 等生图 240s

function $first(selList, root = document) {
  for (const sel of selList) {
    const el = root.querySelector(sel);
    if (el) return el;
  }
  return null;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---- 填入 prompt ----
async function setComposerText(text) {
  const el = $first(SELECTORS.composer);
  if (!el) throw new Error("找不到输入框（composer 选择器需校准）");
  el.focus();
  if (el.tagName === "TEXTAREA") {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
    setter.call(el, text);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  } else {
    // contenteditable / ProseMirror：用 execCommand 插入最稳，事件链完整
    el.textContent = "";
    document.execCommand("insertText", false, text);
    el.dispatchEvent(new InputEvent("input", { bubbles: true }));
  }
  await sleep(150);
}

// ---- 附参考图（图生图，实验性）----
async function attachRefImages(refImages) {
  if (!refImages || !refImages.length) return;
  const input = $first(SELECTORS.fileInput);
  if (!input) throw new Error("找不到文件上传 input（图生图选择器需校准）");
  const dt = new DataTransfer();
  for (const ref of refImages) {
    const bin = atob(ref.b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    dt.items.add(new File([arr], ref.name || "ref.png", { type: ref.mime || "image/png" }));
  }
  input.files = dt.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
  await sleep(3000); // 等上传完成（粗略）
}

// ---- 点发送 ----
async function clickSend() {
  const btn = $first(SELECTORS.sendButton);
  if (btn && !btn.disabled) {
    btn.click();
    return;
  }
  // 兜底：回车
  const el = $first(SELECTORS.composer);
  if (el) {
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  }
}

// ---- 等生成图出现 ----
function waitForImage(sinceCount) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    const tick = () => {
      // 找最后一条 assistant 回复里的生成图
      const turns = [];
      for (const sel of SELECTORS.assistantTurn) {
        document.querySelectorAll(sel).forEach((n) => turns.push(n));
      }
      const last = turns[turns.length - 1];
      if (last) {
        const img = $first(SELECTORS.generatedImg, last) || $first(SELECTORS.generatedImg);
        if (img && img.src && img.naturalWidth > 32) {
          resolve(img.src);
          return;
        }
        // ❗TODO(DOM校准): 检测限流/报错文案
        const txt = (last.innerText || "").toLowerCase();
        if (/rate limit|too many|limit reached|额度|上限|稍后再试|try again later/.test(txt)) {
          reject(new Error("网页版报限流/上限：" + txt.slice(0, 120)));
          return;
        }
      }
      if (Date.now() - t0 > GEN_TIMEOUT_MS) {
        reject(new Error("等生成图超时（" + GEN_TIMEOUT_MS / 1000 + "s）"));
        return;
      }
      setTimeout(tick, 1200);
    };
    tick();
  });
}

// ---- 尽量在页面内把图转成 base64（拿不到就回传 URL 让 background 取）----
async function tryFetchBytes(url) {
  try {
    const r = await fetch(url);
    const blob = await r.blob();
    const b64 = await new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(String(fr.result).split(",")[1]);
      fr.onerror = rej;
      fr.readAsDataURL(blob);
    });
    return { b64, mime: blob.type || "image/png" };
  } catch (e) {
    return null;
  }
}

async function runJob(job) {
  await setComposerText(job.prompt);
  if (job.refImages && job.refImages.length) {
    await attachRefImages(job.refImages);
    await setComposerText(job.prompt); // 上传可能清空输入，补一次
  }
  await sleep(300);
  await clickSend();
  const url = await waitForImage();
  const bytes = await tryFetchBytes(url);
  return {
    imageUrl: url,
    imageBase64: bytes ? bytes.b64 : null,
    mime: bytes ? bytes.mime : "image/png",
  };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "GENERATE") {
    sendResponse({ ack: true }); // 立刻 ack，避免长任务卡住消息通道
    runJob(msg.job)
      .then((res) => {
        chrome.runtime.sendMessage({ type: "GENERATE_RESULT", jobId: msg.job.jobId, ok: true, ...res });
      })
      .catch((err) => {
        chrome.runtime.sendMessage({ type: "GENERATE_RESULT", jobId: msg.job.jobId, ok: false, error: String(err && err.message || err) });
      });
    return true;
  }
});
