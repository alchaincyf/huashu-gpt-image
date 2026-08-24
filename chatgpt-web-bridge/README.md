# ChatGPT Web 生图桥

把 **chatgpt.com 网页版**的生图能力桥接成一个本地 API，给 `huashu-gpt-image` skill 当**第三条生成路**。

## 为什么要它

| 路 | 吃哪个额度桶 | 何时用 |
|---|---|---|
| `gen_via_codex.py`（默认）| codex 的 `$imagegen` 订阅桶——**较紧**，用几次就 429 | 日常默认 |
| `gen_via_chatgpt_web.py`（本桥）| **网页版**订阅桶——Plus/Pro **宽得多** | codex 桶耗尽时 fallback |
| API 路径 | 按量计费 | 要透明底/精确参数/大批量 |

codex 和网页版虽然都是 ChatGPT 订阅，但**限流是两个独立的桶**——这正是本桥的价值。

## 架构（为什么要本地中继）

Chrome MV3 扩展的 service worker 不能监听端口，CLI 也没法直接喊扩展，所以用一个本地 HTTP 中继当「信箱」：

```
gen_via_chatgpt_web.py  --POST /submit-->  server.py  <--GET /poll(长轮询)--  Chrome 扩展
gen_via_chatgpt_web.py  <----图片字节----  server.py  <--POST /result-------  Chrome 扩展
                                                              ↓ 在你已登录的真实 Chrome 里
                                                          驱动 chatgpt.com 生图
```

扩展跑在**你真实的、已登录的 Chrome** 里，所以反爬检测最低、不需要 API key、不按量计费。

## 安全边界：为什么「只绑 127.0.0.1」不够

`server.py` 只监听 `127.0.0.1`，这挡住了局域网里的别人，**挡不住你自己浏览器里打开的任意网页**——网页能对 `127.0.0.1` 发跨源请求。所以桥在应用层加了三道门：

| 门 | 做什么 | 挡住什么 |
|---|---|---|
| Host 白名单 | 只接受 `127.0.0.1` / `localhost` / `::1` | DNS rebinding（攻击者域名解析到 127.0.0.1，Host 就露馅） |
| Origin 白名单 | 只放行 `chrome-extension://` 和「没有 Origin」的本地 CLI，`http(s)://` 网页直接 403，且**从不回 `ACAO: *`** | 恶意页面读 `/poll` 偷走待处理任务——里面有 `--ref` 参考图的完整 base64 |
| `X-Bridge-Client` 头 | `/submit` `/poll` `/result` 必带 | 网页的「简单请求」带不了自定义头；一加就必须先过预检，而预检卡在上一道门。这条同时堵住了「读不到响应但照样把任务从队列里抢走」的盲打 |

另外两条：

- **`/result` 绑 `resultToken`**：`/poll` 派任务时附一个一次性 token，回 `/result` 必须带对，否则 403。没有它，任何能猜到 `jobId` 的一方都能替你的任务交一份伪造结果，而 CLI 会把那些字节直接写进 `--out`。
- **请求体上限** `BRIDGE_MAX_BODY`（默认 32 MiB）：超了返 413，不再照着 `Content-Length` 分配内存。

`/health` 不要求自定义头，`curl http://127.0.0.1:8765/health` 照旧能用——它只返回在线状态和计数。

> 门再多也只是**纵深**，不是隔离。桥开着就意味着本机上任何能执行代码的东西都能驱动你已登录的 ChatGPT 账号。**用完就把 `server.py` 关掉**，别常驻。

## 一次性安装（约 3 分钟）

### 1. 装扩展

1. Chrome 打开 `chrome://extensions`
2. 右上角打开「开发者模式」
3. 点「加载已解压的扩展程序」，选这个目录下的 `extension/` 文件夹
4. 确认 Chrome 里 **chatgpt.com 已登录**（Plus 账号）

### 2. 跑本地中继

```bash
python3 ~/.claude/skills/huashu-gpt-image/chatgpt-web-bridge/server.py
```

保持这个终端开着（或用 `&` / launchd 常驻）。换端口：`PORT=9000 python3 server.py`，扩展 popup 里也要改成同一个。

### 3. 验证

```bash
python3 ~/.claude/skills/huashu-gpt-image/scripts/gen_via_chatgpt_web.py --health
# ✅ 桥 + 扩展均在线
```

## 用法（接口对齐 gen_via_codex.py）

```bash
# 单图
python3 scripts/gen_via_chatgpt_web.py --prompt "Kenya Hara 风格的越窑青瓷茶碗特写" --out 配图/x.png --size 1410x600

# 批量（浏览器侧串行执行，慢属正常）
python3 scripts/gen_via_chatgpt_web.py --batch jobs.jsonl --concurrency 2
```

## 防风控节流（主力账号务必保持开启）

自动化 chatgpt.com 违反 OpenAI ToS，主力账号被风控的下行是非对称的。`server.py` 内置两道闸，把行为压到像真人、限量：

| 环境变量 | 默认 | 作用 |
|---|---|---|
| `BRIDGE_DAILY_CAP` | `80` | 每日生成上限，超了 `/submit` 直接返回 429 |
| `BRIDGE_MIN_GAP` / `BRIDGE_MAX_GAP` | `8` / `20` | 两次派发之间随机间隔（秒），模拟人类节奏 |

`--health` 会显示 `dailyUsed / dailyCap`。**别为了快把间隔调到 0 或上限调很高**——那等于把「像机器人」的特征重新暴露出来。批量场景宁可慢。

## 故障排查

| 现象 | 原因 / 解法 |
|---|---|
| `--health` 说桥不可用 | `server.py` 没跑，或端口被占 |
| `--health` 说扩展没连 | 扩展没加载 / Chrome 没开 / popup 里桥地址写错 |
| 扩展点开 popup 显示「桥未启动」 | 同上；macOS 系统代理可能劫持 localhost → 系统代理设置里把 `127.0.0.1,localhost` 加进「忽略代理」 |
| 等图超时 | chatgpt.com 改版导致选择器失效 → 见 `extension/content.js` 顶部 `SELECTORS`，对着真实 DOM 校准带 `❗TODO` 的项 |
| 报「限流/上限」 | 网页版桶也到顶了，等恢复或回退 codex 路 |
| 请求返 403 `missing X-Bridge-Client` | 自己写脚本调桥时漏了这个头（见上方「安全边界」），加 `-H 'X-Bridge-Client: my-script'` |
| 请求返 403 `cross-origin denied` | 从网页/DevTools console 里调桥——这是**设计如此**，只有扩展和本地 CLI 能调 |
| 扩展报 403 `bad or expired resultToken` | 扩展是旧版（`background.js` 还没回传 `resultToken`）→ 在 `chrome://extensions` 点一下「重新加载」 |

## ⚠️ 选择器维护

`extension/content.js` 顶部的 `SELECTORS` 是唯一的 DOM 依赖。ChatGPT 改版后只改这里。带 `❗TODO(DOM校准)` 的项需要对着当前 chatgpt.com 的真实 DOM 确认（输入框、发送键、生成图节点、限流文案）。
