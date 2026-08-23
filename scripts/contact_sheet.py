#!/usr/bin/env python3
"""
把抠出的透明 PNG 拼成一张预览图（contact sheet），用于肉眼验证抠图质量。

用法：
  python3 contact_sheet.py --input extracted_dir --out sheet.png
  python3 contact_sheet.py --input extracted_dir --grid 3 3 --cell 320

默认按文件名数字前缀排序（extract_grid.py 输出的 01_, 02_ ... 格式）。
"""
import argparse
import glob
import os
import re
from pathlib import Path

from PIL import Image


def natural_sort_key(path):
    name = os.path.basename(path)
    m = re.match(r'^(\d+)', name)
    return (int(m.group(1)) if m else 999999, name)


def build_sheet(input_dir, out_path, rows=None, cols=None, cell=320, pad=20,
                bg_color=(245, 245, 245, 255)):
    files = sorted(glob.glob(os.path.join(input_dir, '*.png')), key=natural_sort_key)
    if not files:
        raise RuntimeError(f'No PNG files found in {input_dir}')

    n = len(files)
    if rows is None or cols is None:
        import math
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

    w = cell * cols + pad * (cols + 1)
    h = cell * rows + pad * (rows + 1)
    canvas = Image.new('RGBA', (w, h), bg_color)

    for i, f in enumerate(files):
        r, c = i // cols, i % cols
        im = Image.open(f).convert('RGBA')
        iw, ih = im.size
        scale = (cell - 20) / max(iw, ih)
        new_size = (int(iw * scale), int(ih * scale))
        im = im.resize(new_size, Image.LANCZOS)
        x = pad + c * (cell + pad) + (cell - im.width) // 2
        y = pad + r * (cell + pad) + (cell - im.height) // 2
        canvas.paste(im, (x, y), im)

    canvas.save(out_path)
    return canvas.size, n


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, help='Directory of extracted PNGs')
    parser.add_argument('--out', default='contact_sheet.png', help='Output path')
    parser.add_argument('--grid', nargs=2, type=int, metavar=('ROWS', 'COLS'),
                        help='Grid layout (auto if not specified)')
    parser.add_argument('--cell', type=int, default=320, help='Cell size in pixels')
    parser.add_argument('--pad', type=int, default=20, help='Padding between cells')

    args = parser.parse_args()
    rows, cols = (args.grid or (None, None))
    size, n = build_sheet(args.input, args.out, rows, cols, args.cell, args.pad)
    print(f'Saved {args.out}: {size[0]}x{size[1]}, {n} images')


if __name__ == '__main__':
    main()
