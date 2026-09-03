#!/usr/bin/env python3
"""server.py — chatgpt-web-bridge 的本地中继（纯标准库，无需 pip install）。

为什么需要它？
  Chrome MV3 扩展的 service worker 不能监听本地端口，CLI 脚本也没法直接喊扩展。
  于是用这个本地 HTTP 服务做「中继信箱」：
    CLI 脚本  --POST /submit-->  [server]  <--GET /poll(长轮询)--  Chrome 扩展
    CLI 脚本  <--返回图片------  [server]  <--POST /result------  Chrome 扩展
  扩展在你已登录的真实 Chrome 里驱动 chatgpt.com 生图，吃网页版额度，不按 API 计费。

跑法：
  python3 server.py            # 默认 127.0.0.1:8765
  PORT=9000 python3 server.py  # 换端口（扩展 options 里也要改成同一个）

只监听 127.0.0.1——但这挡不住浏览器里的任意网页，见下方「三道门」。
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import random
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8765"))

# 单张图生成给足时间：网页版排队 + 生成实测 30-120s
SUBMIT_TIMEOUT = int(os.environ.get("BRIDGE_SUBMIT_TIMEOUT", "300"))
# 扩展长轮询的挂起时长（短于浏览器/SW 的超时，避免被掐）
POLL_HOLD = int(os.environ.get("BRIDGE_POLL_HOLD", "25"))

# === 防风控节流（主力账号必开）===
# 自动化 chatgpt.com 违反 ToS，账号被风控的下行非对称。这两道闸把行为压到像真人、限量。
DAILY_CAP = int(os.environ.get("BRIDGE_DAILY_CAP", "80"))   # 每日生成上限
MIN_GAP = float(os.environ.get("BRIDGE_MIN_GAP", "8"))      # 两次派发最小间隔（秒）
MAX_GAP = float(os.environ.get("BRIDGE_MAX_GAP", "20"))     # 随机抖动到人类节奏的上限

_last_dispatch = [0.0]
_day_bucket = [""]
_day_count = [0]

# === 三道门（本地服务的最小防护）===
# 「只绑 127.0.0.1」只挡住了局域网，挡不住浏览器：你打开的任意网页都能对 127.0.0.1
# 发跨源请求。没有这三道门时，恶意页面可以 GET /poll 偷走待处理任务（含 --ref 参考图
# 的 base64）、POST /result 把任意字节塞进 CLI 的 --out、POST /submit 白烧你网页版额度。
#   1. Host 白名单        —— 挡 DNS rebinding（攻击者域名解析到 127.0.0.1，Host 就不是本地名）
#   2. Origin 白名单      —— 只放行 chrome-extension:// 和「没有 Origin」的本地 CLI，拒绝 http(s) 网页
#   3. X-Bridge-Client 头 —— 网页的「简单请求」带不了自定义头，加了就必须先过预检，而预检卡在第 2 道门
# /health 不要求第 3 道门，方便 `curl 127.0.0.1:8765/health`；它只返回在线状态和计数。
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
EXT_ORIGIN_PREFIX = "chrome-extension://"
CLIENT_HEADER = "X-Bridge-Client"
# 参考图走 base64 进 body，留足余量；同时防止本地请求用超大 Content-Length 吃满内存
MAX_BODY = int(os.environ.get("BRIDGE_MAX_BODY", str(32 * 1024 * 1024)))

_jobs_pending: "queue.Queue[dict]" = queue.Queue()
_results: dict[str, dict] = {}
_events: dict[str, threading.Event] = {}
_job_tokens: dict[str, str] = {}  # jobId -> resultToken，只有取到活的那一方才知道，用来绑定 /result
_lock = threading.Lock()
_last_poll_ts = [0.0]  # 扩展最近一次来取活的时间，用于 /health 判断扩展是否在线


def _now() -> float:
    return time.time()


def _roll_day():
    """日切则清零计数。调用方需已持 _lock。"""
    today = time.strftime("%Y-%m-%d", time.localtime())
    if _day_bucket[0] != today:
        _day_bucket[0] = today
        _day_count[0] = 0


def _pace_before_dispatch():
    """派发前按人类节奏 sleep，让两次生成间隔随机化到 MIN_GAP~MAX_GAP 秒。"""
    gap = random.uniform(MIN_GAP, MAX_GAP)
    elapsed = _now() - _last_dispatch[0]
    if _last_dispatch[0] and elapsed < gap:
        time.sleep(gap - elapsed)
    _last_dispatch[0] = _now()


class Handler(BaseHTTPRequestHandler):
    _acao: str | None = None  # 本次请求可回显的 Access-Control-Allow-Origin

    # 静默默认日志，自己控制输出
    def log_message(self, *a):  # noqa
        pass

    def _send(self, code: int, obj: dict | None = None):
        body = b"" if obj is None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # 只对 chrome 扩展回显 ACAO；网页源在 _guard 里已经被拒，绝不回 "*"
        if self._acao:
            self.send_header("Access-Control-Allow-Origin", self._acao)
        self.send_header("Vary", "Origin")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _host_ok(self) -> bool:
        """第 1 道门：Host 必须是本地名，挡 DNS rebinding。"""
        host = self.headers.get("Host") or ""
        if not host:
            return True  # 浏览器一定带 Host；空的只可能是本地非浏览器客户端
        name = host.split("]")[0] + "]" if host.startswith("[") else host.split(":")[0]
        return name in ALLOWED_HOSTS

    def _origin_ok(self) -> bool:
        """第 2 道门：只放行扩展源和无 Origin 的本地 CLI。顺带记下要回显的 ACAO。"""
        origin = self.headers.get("Origin")
        if not origin:
            self._acao = None  # 本地 CLI / 扩展特权 fetch，本来就不需要 CORS
            return True
        if origin.startswith(EXT_ORIGIN_PREFIX):
            self._acao = origin
            return True
        self._acao = None
        return False

    def _guard(self, need_client_header: bool = True) -> bool:
        if not self._host_ok():
            self._send(403, {"error": "bad Host：只接受 127.0.0.1 / localhost"})
            return False
        if not self._origin_ok():
            self._send(403, {"error": "cross-origin denied：网页不能调用本地桥"})
            return False
        if need_client_header and not self.headers.get(CLIENT_HEADER):
            self._send(403, {"error": f"missing {CLIENT_HEADER} header"})
            return False
        return True

    def _read_json(self) -> dict | None:
        """返回 None 表示已经自己回过错误响应，调用方直接 return。"""
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n <= 0:
            return {}
        if n > MAX_BODY:
            self._send(413, {"error": f"body too large：{n} > {MAX_BODY}（调 BRIDGE_MAX_BODY）"})
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        if not self._guard(need_client_header=False):
            return
        self.send_response(204)
        self.send_header("Content-Length", "0")
        if self._acao:
            self.send_header("Access-Control-Allow-Origin", self._acao)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", f"Content-Type, {CLIENT_HEADER}")
            self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            if not self._guard(need_client_header=False):
                return
            ext_online = (_now() - _last_poll_ts[0]) < (POLL_HOLD + 10)
            with _lock:
                _roll_day()
                used, cap = _day_count[0], DAILY_CAP
            self._send(200, {
                "ok": True,
                "extensionConnected": ext_online,
                "lastPollAgo": round(_now() - _last_poll_ts[0], 1) if _last_poll_ts[0] else None,
                "pending": _jobs_pending.qsize(),
                "dailyUsed": used,
                "dailyCap": cap,
            })
            return
        if self.path.startswith("/poll"):
            if not self._guard():
                return
            _last_poll_ts[0] = _now()
            job = self._next_live_job(_now() + POLL_HOLD)
            if job is None:
                self._send(204)  # 没活，扩展该重新轮询
                return
            _pace_before_dispatch()   # 人类节奏间隔，防风控
            with _lock:
                _roll_day()
                _day_count[0] += 1
            self._send(200, job)
            return
        self._send(404, {"error": "not found"})

    def _next_live_job(self, deadline: float) -> dict | None:
        """取一个提交方还在等的任务。

        提交方 /submit 超时离开后，任务会烂在队列里；老逻辑照样把它派给扩展，
        白烧一次网页版额度还没人收结果。这里顺手把这种僵尸任务丢掉。
        """
        while True:
            remaining = deadline - _now()
            if remaining <= 0:
                return None
            try:
                job = _jobs_pending.get(timeout=remaining)
            except queue.Empty:
                return None
            with _lock:
                if job["jobId"] in _events:
                    return job
                _job_tokens.pop(job["jobId"], None)  # 已超时，连 token 一起清

    def do_POST(self):
        if self.path.startswith("/submit"):
            if not self._guard():
                return
            self._handle_submit()
            return
        if self.path.startswith("/result"):
            if not self._guard():
                return
            self._handle_result()
            return
        self._send(404, {"error": "not found"})

    def _handle_submit(self):
        data = self._read_json()
        if data is None:
            return
        prompt = data.get("prompt")
        if not prompt:
            self._send(400, {"error": "missing prompt"})
            return
        with _lock:
            _roll_day()
            if _day_count[0] >= DAILY_CAP:
                self._send(429, {"ok": False,
                                 "error": f"今日网页版生成已达上限 {DAILY_CAP} 张（防风控闸）。"
                                          f"明日恢复，或回退 codex/API 路。"})
                return
        job_id = uuid.uuid4().hex
        result_token = uuid.uuid4().hex
        ev = threading.Event()
        with _lock:
            _events[job_id] = ev
            _job_tokens[job_id] = result_token
        job = {
            "jobId": job_id,
            # 只有从 /poll 取到这个任务的一方才知道 resultToken，回 /result 时必须带上，
            # 免得别的本地进程/页面替这个任务交一份伪造结果
            "resultToken": result_token,
            "prompt": prompt,
            "size": data.get("size"),
            "quality": data.get("quality"),
            "refImages": data.get("refImages") or [],  # [{name, mime, b64}]
        }
        _jobs_pending.put(job)
        timeout = int(data.get("timeout") or SUBMIT_TIMEOUT)
        got = ev.wait(timeout=timeout)
        with _lock:
            res = _results.pop(job_id, None)
            _events.pop(job_id, None)
            if not got:
                _job_tokens.pop(job_id, None)
        if not got or res is None:
            self._send(504, {"ok": False, "error": f"timeout {timeout}s（扩展没在线或生图超时）"})
            return
        self._send(200, res)

    def _handle_result(self):
        data = self._read_json()
        if data is None:
            return
        job_id = data.get("jobId")
        if not job_id:
            self._send(400, {"error": "missing jobId"})
            return
        token = str(data.get("resultToken") or "")
        with _lock:
            expected = _job_tokens.get(job_id)
        if not expected or not hmac.compare_digest(token, expected):
            self._send(403, {"error": "bad or expired resultToken"})
            return
        with _lock:
            _job_tokens.pop(job_id, None)
            ev = _events.get(job_id)
            if ev is None:
                # 提交方已经超时走了，别把结果留在内存里（老逻辑会一直堆着）
                stale = True
            else:
                stale = False
                _results[job_id] = {
                    "ok": bool(data.get("ok")),
                    "imageBase64": data.get("imageBase64"),
                    "mime": data.get("mime") or "image/png",
                    "error": data.get("error"),
                }
        if stale:
            self._send(410, {"ok": False, "error": "job expired：提交方已超时离开"})
            return
        ev.set()
        self._send(200, {"ok": True})


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[bridge] listening http://{HOST}:{PORT}  (submit_timeout={SUBMIT_TIMEOUT}s)")
    print(f"[bridge] 健康检查: curl http://{HOST}:{PORT}/health")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] 退出")
        srv.shutdown()


if __name__ == "__main__":
    main()
