#!/usr/bin/env python3
"""
从 GPT-image-2 生成的网格图中抠出独立透明 PNG。

两种模式：
  --mode=bbox    按 content bbox 等分切（默认，适合均匀网格）
  --mode=density 按像素密度扫描切（适合 5×5 或不均匀网格）

用法：
  python3 extract_grid.py input.png --grid 4 4 --out out_dir
  python3 extract_grid.py input.png --grid 5 5 --mode density --out out_dir
  python3 extract_grid.py input.png --grid 3 3 --names "ryu,ken,chunli,..."

Pure PIL + numpy, no third-party deps beyond those.
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image


BG_THRESHOLD = 240  # RGB 全部 > 此值算背景
ROW_DENSITY_MIN = 50  # density 模式：一行至少多少非白像素才算有内容
SEGMENT_MIN_SIZE = 30  # density 模式：一段内容的最小高/宽


def load_image(path):
    img = np.array(Image.open(path).convert('RGB'))
    return img


def find_content_bbox(img, bg_threshold=BG_THRESHOLD):
    is_content = ~((img[:, :, 0] > bg_threshold) &
                   (img[:, :, 1] > bg_threshold) &
                   (img[:, :, 2] > bg_threshold))
    ys, xs = np.where(is_content)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def scan_segments(density_1d, threshold, min_size):
    """沿一维密度数组找出连续高密度段（返回 [(start, end), ...]）"""
    in_seg = density_1d > threshold
    segments = []
    start = None
    for i, v in enumerate(in_seg):
        if v and start is None:
            start = i
        elif not v and start is not None:
            segments.append((start, i - 1))
            start = None
    if start is not None:
        segments.append((start, len(in_seg) - 1))
    return [s for s in segments if s[1] - s[0] + 1 >= min_size]


def density_scan_cells(img, rows, cols, bg_threshold=BG_THRESHOLD):
    """按像素密度扫描，返回 rows×cols 个 cell 的精确坐标。"""
    is_content = ~((img[:, :, 0] > bg_threshold) &
                   (img[:, :, 1] > bg_threshold) &
                   (img[:, :, 2] > bg_threshold))

    row_density = is_content.sum(axis=1)
    row_segments = scan_segments(row_density, ROW_DENSITY_MIN, SEGMENT_MIN_SIZE)
    if len(row_segments) != rows:
        print(f'WARN: density scan found {len(row_segments)} rows, expected {rows}',
              file=sys.stderr)
        if len(row_segments) > rows:
            row_segments = sorted(row_segments, key=lambda s: s[1] - s[0], reverse=True)[:rows]
            row_segments.sort()

    cells = []
    for r_idx, (y0, y1) in enumerate(row_segments):
        row_slice = is_content[y0:y1 + 1, :]
        col_density = row_slice.sum(axis=0)
        col_segments = scan_segments(col_density, ROW_DENSITY_MIN // 2, SEGMENT_MIN_SIZE)
        if len(col_segments) != cols:
            print(f'WARN: row {r_idx} found {len(col_segments)} cols, expected {cols}',
                  file=sys.stderr)
            if len(col_segments) > cols:
                col_segments = sorted(col_segments, key=lambda s: s[1] - s[0], reverse=True)[:cols]
                col_segments.sort()
        for c_idx, (x0, x1) in enumerate(col_segments):
            cells.append((x0, y0, x1, y1))
    return cells


def bbox_equal_cells(img, rows, cols, bg_threshold=BG_THRESHOLD):
    """按 content bbox 等分，返回 rows×cols 个 cell 坐标。"""
    bbox = find_content_bbox(img, bg_threshold)
    if bbox is None:
        raise RuntimeError('No content found — image appears to be all white')
    x0, y0, x1, y1 = bbox
    cell_w = (x1 - x0 + 1) / cols
    cell_h = (y1 - y0 + 1) / rows
    cells = []
    for r in range(rows):
        for c in range(cols):
            cx0 = int(x0 + c * cell_w)
            cy0 = int(y0 + r * cell_h)
            cx1 = int(x0 + (c + 1) * cell_w) - 1
            cy1 = int(y0 + (r + 1) * cell_h) - 1
            cells.append((cx0, cy0, cx1, cy1))
    return cells


def extract_cell_rgba(img, x0, y0, x1, y1, bg_threshold=BG_THRESHOLD, pad=8):
    """从 cell 区域提取透明 PNG 数据。"""
    cell = img[y0:y1 + 1, x0:x1 + 1]
    rgba = np.dstack([cell, np.full(cell.shape[:2], 255, dtype=np.uint8)])

    cr, cg, cb = cell[:, :, 0].astype(int), cell[:, :, 1].astype(int), cell[:, :, 2].astype(int)
    is_bg = (cr > bg_threshold) & (cg > bg_threshold) & (cb > bg_threshold)
    rgba[is_bg, 3] = 0

    lum = np.maximum.reduce([cr, cg, cb])
    sat = np.maximum.reduce([cr, cg, cb]) - np.minimum.reduce([cr, cg, cb])
    near_bg = (lum > 225) & (sat < 15) & ~is_bg
    fade = ((255 - lum).clip(0, 30) * 255 // 30).astype(np.uint8)
    rgba[near_bg, 3] = fade[near_bg]

    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > 20)
    if len(ys) == 0:
        return rgba
    t = max(0, ys.min() - pad)
    b = min(rgba.shape[0] - 1, ys.max() + pad)
    le = max(0, xs.min() - pad)
    ri = min(rgba.shape[1] - 1, xs.max() + pad)
    return rgba[t:b + 1, le:ri + 1]


def main():
    parser = argparse.ArgumentParser(
        description='Extract transparent PNGs from a GPT-image-2 grid image',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument('input', help='Input grid image path')
    parser.add_argument('--grid', nargs=2, type=int, metavar=('ROWS', 'COLS'),
                        required=True, help='Grid dimensions')
    parser.add_argument('--mode', choices=['bbox', 'density'], default='bbox',
                        help='bbox: equal split of content bbox (default) / density: scan rows/cols')
    parser.add_argument('--out', default='extracted', help='Output directory')
    parser.add_argument('--names', default='',
                        help='Comma-separated names (in reading order); auto-numbered if empty')
    parser.add_argument('--bg', type=int, default=BG_THRESHOLD,
                        help=f'Background threshold, default {BG_THRESHOLD}')
    parser.add_argument('--pad', type=int, default=8, help='Tight-crop padding in pixels')

    args = parser.parse_args()
    rows, cols = args.grid
    total = rows * cols

    if args.names:
        names = [n.strip() for n in args.names.split(',')]
        if len(names) != total:
            print(f'ERROR: {len(names)} names provided, expected {total}', file=sys.stderr)
            sys.exit(1)
    else:
        names = [f'{i + 1:02d}' for i in range(total)]

    img = load_image(args.input)
    H, W = img.shape[:2]
    print(f'Canvas: {W}x{H}, grid: {rows}x{cols}, mode: {args.mode}')

    if args.mode == 'bbox':
        cells = bbox_equal_cells(img, rows, cols, args.bg)
    else:
        cells = density_scan_cells(img, rows, cols, args.bg)

    os.makedirs(args.out, exist_ok=True)
    for idx, (x0, y0, x1, y1) in enumerate(cells):
        rgba = extract_cell_rgba(img, x0, y0, x1, y1, args.bg, args.pad)
        out_path = Path(args.out) / f'{idx + 1:02d}_{names[idx]}.png'
        Image.fromarray(rgba, 'RGBA').save(out_path)
        print(f'  {out_path.name}: {rgba.shape[1]}x{rgba.shape[0]}')

    print(f'Done. {total} files saved to {args.out}/')


if __name__ == '__main__':
    main()
