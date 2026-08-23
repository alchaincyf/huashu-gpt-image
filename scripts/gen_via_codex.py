#!/usr/bin/env python3
"""gen_via_codex.py — 走 codex 订阅额度的 GPT-image-2 生成链路（不需 OPENAI_API_KEY）。

huashu-gpt-image 负责把 prompt 写到 9.5 分，这个脚本负责把图真的生出来。
底层调用 `codex exec -s workspace-write` 里的内置 $imagegen skill（gpt-image-2），
吃的是 codex login 的 ChatGPT 订阅额度，不按 API 计费。

为什么不直接调 ~/.codex/skills/.system/imagegen/scripts/image_gen.py？
  那个 fallback CLI 精确控参数（--size/--quality/--n/generate-batch 并发），
  但 hardcode 要 OPENAI_API_KEY、按量计费。花叔选了走订阅额度，所以走 codex agent。
  代价：尺寸/quality 靠自然语言指令传给 agent，agent 生成后自己 sips 后处理到目标尺寸。

用法：
  # 单图
  python gen_via_codex.py --prompt "Anthropic 风格的越文化青铜器特写" \
      --out 配图/bronze.png --size 1410x600 --quality high

  # 图生图（参考图改写）。-i 用 stdin 传 prompt 规避 codex 变长参数吞 prompt 的陷阱
  python gen_via_codex.py --prompt "改成蓝色调" --out out.png --ref base.png

  # 多参考图叠加：花叔品牌资产 + 产品 logo（封面涉及具体 AI 产品时）。ref 传 PNG（底层 -i 不吃 SVG）
  python gen_via_codex.py --prompt "用参考图1的花叔像素品牌 DNA 生成封面，参考图2是 ChatGPT 官方 logo 用于画面里的产品标识" \
      --out 配图/封面.png --size 1600x900 --quality high \
      --ref _archive/像素品牌资产.png --ref "04-写作参考/品牌Logo库/OpenAI/ChatGPT.png"

  # 批量并发（JSONL，每行一个 job：{"prompt":..., "out":..., "size":..., "quality":...}）
  python gen_via_codex.py --batch jobs.jsonl --concurrency 3

退出码：0 全部成功 / 1 有失败。失败的 job 会打印到 stderr，不中断其余。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CODEX_GEN_DIR = Path.home() / ".codex" / "generated_images"
# codex exec 单张实测 150-280s（high+大图），给足超时；可用环境变量覆盖
PER_IMAGE_TIMEOUT = int(os.environ.get("GEN_IMAGE_TIMEOUT", "600"))


def _eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def _build_codex_prompt(prompt: str, out: str, size: str | None, quality: str | None) -> str:
    """构造给 codex agent 的中文生成指令。保持简短——agent 自己会调 $imagegen。"""
    lines = [f"用 $imagegen 生成图片，保存到 {out}。"]
    if size:
        lines.append(f"尺寸严格 {size} 像素（生成后如不符请裁剪/缩放到精确尺寸）。")
    if quality:
        lines.append(f"quality 用 {quality}。")
    lines.append(f"图片内容：{prompt}")
    lines.append("只生成这一张图，保存后直接结束，不要追问、不要多余解释。")
    return "\n".join(lines)


def _snapshot_gen_dir() -> set[Path]:
    if not CODEX_GEN_DIR.exists():
        return set()
    return set(CODEX_GEN_DIR.rglob("*.png"))


def _rescue_latest(before: set[Path], out: Path) -> bool:
    """codex 没把图搬到 out 时的兜底：把本次新生成的最新 png 拷过去。"""
    after = _snapshot_gen_dir()
    new = after - before
    if not new:
        return False
    latest = max(new, key=lambda p: p.stat().st_mtime)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(latest.read_bytes())
    return True


def _verify_size(out: Path) -> str:
    """返回 'WxH' 或 '?'。优先 PIL，回退 sips。"""
    try:
        from PIL import Image  # noqa
        with Image.open(out) as im:
            return f"{im.width}x{im.height}"
    except Exception:
        try:
            r = subprocess.run(
                ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(out)],
                capture_output=True, text=True, timeout=15,
            )
            w = h = "?"
            for ln in r.stdout.splitlines():
                if "pixelWidth" in ln:
                    w = ln.split(":")[-1].strip()
                if "pixelHeight" in ln:
                    h = ln.split(":")[-1].strip()
            return f"{w}x{h}"
        except Exception:
            return "?"


def generate_one(prompt: str, out: str, size: str | None = None,
                 quality: str | None = None, ref=None) -> tuple[bool, str]:
    """生成一张图。返回 (成功, 信息)。
    ref 可为单个路径 str，或多个路径的 list（如 品牌资产 + 产品 logo 一起喂）。"""
    out_path = Path(out)
    full_prompt = _build_codex_prompt(prompt, str(out_path), size, quality)

    cmd = ["codex", "exec", "-s", "workspace-write"]
    refs = [] if not ref else ([ref] if isinstance(ref, str) else list(ref))
    for r in refs:
        if not Path(r).exists():
            return False, f"参考图不存在: {r}"
        cmd += ["-i", r]
    cmd += ["-"]  # prompt 从 stdin 读，规避 -i 变长参数吞 prompt

    before = _snapshot_gen_dir()
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, input=full_prompt, capture_output=True, text=True,
            timeout=PER_IMAGE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"超时 (>{PER_IMAGE_TIMEOUT}s)"
    dt = time.time() - t0

    if not out_path.exists():
        if not _rescue_latest(before, out_path):
            tail = (r.stderr or r.stdout or "")[-300:]
            return False, f"未产出文件 ({dt:.0f}s). codex 末尾输出: {tail}"

    dims = _verify_size(out_path)
    size_note = ""
    if size and dims != "?" and dims.replace(" ", "") != size.replace(" ", ""):
        size_note = f" ⚠️尺寸{dims}≠请求{size}"
    return True, f"{out_path} [{dims}] {dt:.0f}s{size_note}"


def run_batch(jobs: list[dict], concurrency: int) -> int:
    _eprint(f"批量 {len(jobs)} 张，并发 {concurrency}")
    failed = 0

    def _do(i: int, job: dict) -> tuple[int, bool, str]:
        ok, msg = generate_one(
            prompt=job["prompt"], out=job["out"],
            size=job.get("size"), quality=job.get("quality"), ref=job.get("ref"),
        )
        return i, ok, msg

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_do, i, j) for i, j in enumerate(jobs, 1)]
        for fut in as_completed(futs):
            i, ok, msg = fut.result()
            mark = "✅" if ok else "❌"
            _eprint(f"{mark} [{i}/{len(jobs)}] {msg}")
            if not ok:
                failed += 1
    _eprint(f"完成：{len(jobs) - failed} 成功 / {failed} 失败")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="走 codex 订阅额度的 gpt-image-2 生成链路")
    ap.add_argument("--prompt", help="图片内容描述（单图模式）")
    ap.add_argument("--out", help="输出路径（单图模式）")
    ap.add_argument("--size", help="如 1410x600；非标比例也可，agent 会后处理")
    ap.add_argument("--quality", choices=["low", "medium", "high"], help="密集/中文/卡牌用 high")
    ap.add_argument("--ref", action="append",
                    help="参考图路径（图生图）。可多次传入叠加多张参考图，"
                         "如 --ref 像素品牌资产.png --ref 品牌Logo库/OpenAI/ChatGPT.svg")
    ap.add_argument("--batch", help="JSONL 文件，每行一个 job")
    ap.add_argument("--concurrency", type=int, default=3, help="批量并发数（默认3，订阅额度勿过高）")
    args = ap.parse_args()

    # 前置：确认 codex 在
    if not subprocess.run(["which", "codex"], capture_output=True).returncode == 0:
        _eprint("Error: 找不到 codex CLI。先装 codex 并 codex login。")
        return 2

    if args.batch:
        path = Path(args.batch)
        if not path.exists():
            _eprint(f"Error: 批量文件不存在 {path}")
            return 2
        jobs = []
        for ln_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            ln = raw.strip()
            if not ln or ln.startswith("#"):
                continue
            try:
                job = json.loads(ln)
            except json.JSONDecodeError as e:
                _eprint(f"Error: 第 {ln_no} 行 JSON 解析失败: {e}")
                return 2
            if "prompt" not in job or "out" not in job:
                _eprint(f"Error: 第 {ln_no} 行缺 prompt 或 out")
                return 2
            jobs.append(job)
        if not jobs:
            _eprint("Error: 批量文件没有有效 job")
            return 2
        return run_batch(jobs, max(1, args.concurrency))

    if not args.prompt or not args.out:
        _eprint("Error: 单图模式需要 --prompt 和 --out（或用 --batch）")
        return 2
    ok, msg = generate_one(args.prompt, args.out, args.size, args.quality, args.ref)
    _eprint(("✅ " if ok else "❌ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
