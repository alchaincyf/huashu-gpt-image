#!/usr/bin/env python3
"""gen_via_chatgpt_web.py — 走 ChatGPT 网页版额度的生图链路（第三条路，额度耗尽时的 fallback）。

和 gen_via_codex.py 的关系：
  - gen_via_codex.py：默认路，走 codex 的 $imagegen，吃 codex 那个**较紧**的订阅额度桶。
  - 本脚本：codex 桶 429/耗尽时切过来，驱动你已登录的 chatgpt.com 网页版生图，
    吃**网页版那个更宽**的额度桶。不需要 OPENAI_API_KEY，不按 API 计费。

依赖一套本地桥（见 ../chatgpt-web-bridge/）：
  1. 跑起本地中继：  python3 ../chatgpt-web-bridge/server.py
  2. Chrome 装上 ../chatgpt-web-bridge/extension（开发者模式加载已解压扩展）
  3. Chrome 里保持登录 chatgpt.com
本脚本只管 POST 任务给中继、把回来的图写到 --out，接口尽量对齐 gen_via_codex.py。

用法：
  python3 gen_via_chatgpt_web.py --prompt "Kenya Hara 风格的越窑青瓷茶碗特写" --out 配图/x.png --size 1410x600
  python3 gen_via_chatgpt_web.py --batch jobs.jsonl --concurrency 2   # 浏览器侧实际串行执行
  python3 gen_via_chatgpt_web.py --health                              # 只检查桥/扩展是否在线

退出码：0 成功 / 1 有失败 / 2 用法或桥不可用。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BRIDGE = os.environ.get("BRIDGE_URL", "http://127.0.0.1:8765").rstrip("/")
SUBMIT_TIMEOUT = int(os.environ.get("GEN_WEB_TIMEOUT", "300"))

# 只跟本地桥通信，彻底绕开系统/公司 HTTP 代理（否则 127.0.0.1 会被代理 502）
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def _http(method: str, path: str, payload: dict | None = None, timeout: int = 320) -> tuple[int, dict]:
    url = BRIDGE + path
    data = None
    # 桥要求这个自定义头，用来区分「本地客户端」和「浏览器里的任意网页」（见 server.py 三道门）
    headers = {"X-Bridge-Client": "huashu-gpt-image-cli"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _opener.open(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body[:200]}
    except urllib.error.URLError as e:
        return 0, {"error": f"连不上本地桥 {BRIDGE}（server.py 没跑？）: {e}"}


def check_health() -> tuple[bool, str]:
    code, j = _http("GET", "/health", timeout=10)
    if code != 200:
        return False, j.get("error", f"桥不可用 (HTTP {code})")
    if not j.get("extensionConnected"):
        return False, "本地桥在线，但 Chrome 扩展没连上（确认扩展已加载 + chatgpt.com 已登录）"
    return True, "桥 + 扩展均在线"


def _verify_size(out: Path) -> str:
    try:
        from PIL import Image  # noqa
        with Image.open(out) as im:
            return f"{im.width}x{im.height}"
    except Exception:
        try:
            r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(out)],
                               capture_output=True, text=True, timeout=15)
            w = h = "?"
            for ln in r.stdout.splitlines():
                if "pixelWidth" in ln:
                    w = ln.split(":")[-1].strip()
                if "pixelHeight" in ln:
                    h = ln.split(":")[-1].strip()
            return f"{w}x{h}"
        except Exception:
            return "?"


def _build_prompt(prompt: str, size: str | None, quality: str | None) -> str:
    """网页版没有 --size/--quality 参数，把尺寸/质量诉求拼进自然语言。"""
    parts = [prompt]
    if size:
        parts.append(f"图片尺寸严格 {size} 像素。")
    if quality:
        parts.append("用最高质量渲染。" if quality == "high" else f"质量 {quality}。")
    # 逼模型直接出图，别回文字/追问（否则 content.js 等不到 <img>）
    parts.append("请直接生成这张图片，不要追问、不要只回文字。")
    return " ".join(parts)


def _load_refs(refs) -> list[dict]:
    out = []
    for r in refs or []:
        p = Path(r)
        if not p.exists():
            raise FileNotFoundError(f"参考图不存在: {r}")
        out.append({
            "name": p.name,
            "mime": "image/png" if p.suffix.lower() == ".png" else "image/jpeg",
            "b64": base64.b64encode(p.read_bytes()).decode("ascii"),
        })
    return out


def generate_one(prompt: str, out: str, size=None, quality=None, ref=None) -> tuple[bool, str]:
    out_path = Path(out)
    try:
        refs = _load_refs([ref] if isinstance(ref, str) else ref) if ref else []
    except FileNotFoundError as e:
        return False, str(e)
    payload = {
        "prompt": _build_prompt(prompt, size, quality),
        "size": size, "quality": quality,
        "refImages": refs, "timeout": SUBMIT_TIMEOUT,
    }
    code, j = _http("POST", "/submit", payload, timeout=SUBMIT_TIMEOUT + 20)
    if code == 0:
        return False, j.get("error", "桥不可用")
    if code == 504:
        return False, j.get("error", "超时（扩展没在线或生图超时）")
    if code != 200 or not j.get("ok"):
        return False, j.get("error", f"生成失败 (HTTP {code})")
    b64 = j.get("imageBase64")
    if not b64:
        return False, "桥返回成功但没有图片数据"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    dims = _verify_size(out_path)
    note = ""
    if size and dims != "?" and dims.replace(" ", "") != size.replace(" ", ""):
        note = f" ⚠️尺寸{dims}≠请求{size}（网页版不保证精确尺寸，需手动 sips 后处理）"
    return True, f"{out_path} [{dims}]{note}"


def run_batch(jobs, concurrency) -> int:
    _eprint(f"批量 {len(jobs)} 张，提交并发 {concurrency}（浏览器侧串行执行，慢属正常）")
    failed = 0

    def _do(i, job):
        ok, msg = generate_one(job["prompt"], job["out"], job.get("size"),
                               job.get("quality"), job.get("ref"))
        return i, ok, msg

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_do, i, j) for i, j in enumerate(jobs, 1)]
        for fut in as_completed(futs):
            i, ok, msg = fut.result()
            _eprint(f"{'✅' if ok else '❌'} [{i}/{len(jobs)}] {msg}")
            if not ok:
                failed += 1
    _eprint(f"完成：{len(jobs) - failed} 成功 / {failed} 失败")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="走 ChatGPT 网页版额度的生图链路")
    ap.add_argument("--prompt")
    ap.add_argument("--out")
    ap.add_argument("--size", help="如 1410x600；网页版不保证精确，脚本会校验并提示")
    ap.add_argument("--quality", choices=["low", "medium", "high"])
    ap.add_argument("--ref", action="append", help="参考图路径（图生图，实验性）")
    ap.add_argument("--batch", help="JSONL 文件，每行一个 job")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--health", action="store_true", help="只检查桥+扩展是否在线")
    args = ap.parse_args()

    if args.health:
        ok, msg = check_health()
        _eprint(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 2

    ok, msg = check_health()
    if not ok:
        _eprint("❌ " + msg)
        _eprint("   先跑 `python3 chatgpt-web-bridge/server.py`，并在 Chrome 加载扩展、登录 chatgpt.com。")
        return 2

    if args.batch:
        path = Path(args.batch)
        if not path.exists():
            _eprint(f"Error: 批量文件不存在 {path}")
            return 2
        jobs = []
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            ln = raw.strip()
            if not ln or ln.startswith("#"):
                continue
            job = json.loads(ln)
            if "prompt" not in job or "out" not in job:
                _eprint(f"Error: 第 {n} 行缺 prompt 或 out")
                return 2
            jobs.append(job)
        return run_batch(jobs, max(1, args.concurrency))

    if not args.prompt or not args.out:
        _eprint("Error: 单图模式需要 --prompt 和 --out（或用 --batch / --health）")
        return 2
    ok, msg = generate_one(args.prompt, args.out, args.size, args.quality, args.ref)
    _eprint(("✅ " if ok else "❌ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
