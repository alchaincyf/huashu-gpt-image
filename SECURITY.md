# 安全策略 / Security Policy

## 怎么报告安全问题

**请不要开公开 issue。** 用下面任一渠道私下告诉我：

- GitHub 的 [Security Advisories](https://github.com/alchaincyf/huashu-gpt-image/security/advisories/new)（推荐，全程私密）
- 邮件：alchaincyf@gmail.com，标题带 `[SECURITY]`

我会在 **72 小时内**回一句确认收到，并在修复后于此文件的「已知问题」一节里记录。

如果你已经公开报告了，也没关系——这个仓库此前没有这份文件，没有渠道可循是我的问题，不是报告者的问题。

## 支持的版本

只维护 `master` 分支的最新提交。这是一个个人工具项目，没有长期支持分支。

## 已知问题

### ✅ 已修复 · `chatgpt-web-bridge` 本地桥无鉴权、且对任意来源开放 CORS

**状态：已修复。** 报告者 [@Wayhhow](https://github.com/Wayhhow)（issue #1 / PR #2）。

**问题**：`chatgpt-web-bridge/server.py` 在 `127.0.0.1:8765` 上提供的四个接口没有任何鉴权，
并且对所有响应返回 `Access-Control-Allow-Origin: *`。
绑定回环地址挡不住浏览器发起的跨源请求——你在浏览器里打开的任意一个网页都可以
`fetch('http://127.0.0.1:8765/...')`，而那个 `*` 让它能读到响应体。
（`server.py` 注释和 README 里原先写的「只监听 127.0.0.1，不对外暴露」是一个误导性的说法，已一并改掉。）

**影响**：在桥运行期间，一个恶意网页可以通过 `/poll` 读走待处理任务（含 `--ref` 参考图的完整 base64）、
通过 `/result` 伪造生成结果让 CLI 把攻击者提供的字节写进 `--out`、通过 `/submit` 消耗你已登录账号的额度。

**修复**（`48aeab6` → PR #2 `c34ffff` → `afd1b9d`）：

- **Origin / Host 白名单**：非扩展源的请求一律 403，且不回 `Access-Control-Allow-Origin`；Host 头伪造（DNS rebinding）同样 403
- **一次性 token**：`/result` 提交结果必须带对应任务的 token，用错/复用即拒
- **自定义头要求**：挡掉无 Origin 无自定义头的「盲打」请求
- **请求体上限**：由 `BRIDGE_MAX_BODY` 控制，超限返回 413
- `afd1b9d` 另补两个口子：非 ASCII token 触发 `hmac.compare_digest` 抛 `TypeError` 的崩点，以及「桥假装在线」

**升级方式**：拉 `master` 最新提交即可，无需改配置。

> 修复前那三条缓解建议（用完就关、别在同一浏览器浏览不受信任网页、换端口不构成防护）
> 对**还没升级**的用户仍然成立。已升级的不需要再照做。

## 这个项目不保护什么

说清楚边界，免得误报：

- **`scripts/` 下的脚本会调用你本机已登录的 ChatGPT / Codex 会话**，这是它的设计目的，不是漏洞。
- **本仓库不保存、不上传任何凭证。** 如果你发现了任何形式的外发端点，那是真问题，请按上面的渠道报告。
- 生成的图片和中间产物落在你自己指定的路径下，本项目不做清理。
