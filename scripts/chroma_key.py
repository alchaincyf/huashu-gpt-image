#!/usr/bin/env python3
"""全局色距抠图：去掉所有接近背景色的像素(含封闭口袋) → 透明PNG。
适用前提：主体配色里不含背景色。软阈值做抗锯齿，再内缩去毛边。
用法: python chroma_key.py in.png out.png [tol_low=62] [tol_high=110] [erode=2]"""
import sys
from PIL import Image, ImageFilter

def key(inp, outp, tol_low=62, tol_high=110, erode=2):
    im = Image.open(inp).convert("RGBA")
    W, H = im.size
    px = im.load()
    corners = [px[0,0], px[W-1,0], px[0,H-1], px[W-1,H-1]]
    bg = tuple(sum(c[i] for c in corners)//4 for i in range(3))
    # 生成alpha：色距<low→0(透明)，>high→255(实)，中间线性过渡(抗锯齿)
    alpha = Image.new("L", (W, H), 255)
    ap = alpha.load()
    for y in range(H):
        for x in range(W):
            r,g,b,_ = px[x,y]
            d = abs(r-bg[0])+abs(g-bg[1])+abs(b-bg[2])
            if d <= tol_low: ap[x,y] = 0
            elif d >= tol_high: ap[x,y] = 255
            else: ap[x,y] = int(255*(d-tol_low)/(tol_high-tol_low))
    if erode:
        alpha = alpha.filter(ImageFilter.MinFilter(int(erode)*2+1))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(alpha)
    bbox = im.getbbox()
    if bbox: im = im.crop(bbox)
    im.save(outp)
    print(f"{outp}: {im.size}  bg={bg}")

if __name__=="__main__":
    a=sys.argv
    key(a[1],a[2],
        int(a[3]) if len(a)>3 else 62,
        int(a[4]) if len(a)>4 else 110,
        float(a[5]) if len(a)>5 else 2)
