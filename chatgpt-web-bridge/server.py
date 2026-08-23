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

只监听 127.0.0.1，不对外暴露。
"""
from __future__ import annotations

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

_jobs_pending: "queue.Queue[dict]" = queue.Queue()
_results: dict[str, dict] = {}
_events: dict[str, threading.Event] = {}
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
    # 静默默认日志，自己控制输出
    def log_message(self, *a):  # noqa
        pass

    def _send(self, code: int, obj: dict | None = None):
        body = b"" if obj is None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # 扩展从 chatgpt.com 标签外的 SW 发请求，允许跨源
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        if self.path.startswith("/health"):
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
            _last_poll_ts[0] = _now()
            try:
                job = _jobs_pending.get(timeout=POLL_HOLD)
            except queue.Empty:
                self._send(204)  # 没活，扩展该重新轮询
                return
            _pace_before_dispatch()   # 人类节奏间隔，防风控
            with _lock:
                _roll_day()
                _day_count[0] += 1
            self._send(200, job)
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/submit"):
            self._handle_submit()
            return
        if self.path.startswith("/result"):
            self._handle_result()
            return
        self._send(404, {"error": "not found"})

    def _handle_submit(self):
        data = self._read_json()
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
        ev = threading.Event()
        with _lock:
            _events[job_id] = ev
        job = {
            "jobId": job_id,
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
        if not got or res is None:
            self._send(504, {"ok": False, "error": f"timeout {timeout}s（扩展没在线或生图超时）"})
            return
        self._send(200, res)

    def _handle_result(self):
        data = self._read_json()
        job_id = data.get("jobId")
        if not job_id:
            self._send(400, {"error": "missing jobId"})
            return
        with _lock:
            _results[job_id] = {
                "ok": bool(data.get("ok")),
                "imageBase64": data.get("imageBase64"),
                "mime": data.get("mime") or "image/png",
                "error": data.get("error"),
            }
            ev = _events.get(job_id)
        if ev:
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
