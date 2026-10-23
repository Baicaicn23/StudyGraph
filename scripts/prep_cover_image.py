#!/usr/bin/env python3
"""封面/收束氛围图预处理：裁到 PPT 图位比例，并把左缘（可加顶缘）压成深蓝渐变。

为什么用"烘焙渐变"而不是 PNG 透明通道：python-pptx 写出去的图片透明度在
PowerPoint 与 HTML 渲染器上的表现不一致，直接把书桌图的左缘混成本页背景色
（#0E203D），在两种渲染器里都不会露出接缝。

用法：
    python3 scripts/prep_cover_image.py 输入.png 输出.png \
        --size 1740x2208 --fade-left 0.34 --fade-top 0.10
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

NAVY = (14, 32, 61)          # 封面深蓝，与 build_deck.py 的 C((14, 32, 61)) 一致


def smoothstep(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def crop_to_ratio(im: Image.Image, ratio: float, anchor: str = "top") -> Image.Image:
    """按目标宽高比裁切；anchor=top 表示保住画面上部（往下裁）。"""
    w, h = im.size
    if w / h > ratio:                       # 太宽 → 裁两侧
        nw = round(h * ratio)
        left = (w - nw) // 2
        return im.crop((left, 0, left + nw, h))
    nh = round(w / ratio)                    # 太高 → 裁底部
    top = 0 if anchor == "top" else (h - nh) // 2
    return im.crop((0, top, w, top + nh))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--size", default="1740x2208", help="输出像素 WxH")
    ap.add_argument("--fade-left", type=float, default=0.34, help="左缘渐变宽度占比")
    ap.add_argument("--fade-top", type=float, default=0.0, help="顶缘渐变高度占比")
    ap.add_argument("--fade-bottom", type=float, default=0.0, help="底缘渐变高度占比")
    ap.add_argument("--bg", default="14,32,61", help="混入的背景色 r,g,b（要和版面底色一致）")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help=">1 会把深蓝往渐变区里压得更狠（边缘看起来更像雾化）")
    ap.add_argument("--dim-left", type=float, default=1.0,
                    help="渐变区内图片的曝光系数（1.0=不压暗；0.5=左缘压到半亮），"
                         "压暗后再混深蓝，接缝处不会出现亮度陡坡")
    args = ap.parse_args()

    global NAVY
    NAVY = tuple(int(v) for v in args.bg.split(","))
    out_w, out_h = (int(v) for v in args.size.lower().split("x"))
    im = Image.open(args.src).convert("RGB")
    im = crop_to_ratio(im, out_w / out_h).resize((out_w, out_h), Image.LANCZOS)

    navy = Image.new("RGB", im.size, NAVY)
    src_px, navy_px = im.load(), navy.load()

    fw = int(out_w * args.fade_left)
    fh_t = int(out_h * args.fade_top)
    fh_b = int(out_h * args.fade_bottom)

    out = Image.new("RGB", im.size)
    out_px = out.load()
    for y in range(out_h):
        for x in range(out_w):
            a = 1.0
            if fw:
                a *= smoothstep(x / fw) ** args.gamma
            if fh_t and y < fh_t:
                a *= smoothstep(y / fh_t)
            if fh_b and y > out_h - fh_b:
                a *= smoothstep((out_h - y) / fh_b)
            if a >= 0.999:
                out_px[x, y] = src_px[x, y]
                continue
            r, g, b = src_px[x, y]
            if args.dim_left < 1.0 and fw and x < fw:
                # 渐变区内把照片本身压暗（像被左侧深色遮光），再混深蓝
                gain = args.dim_left + (1.0 - args.dim_left) * smoothstep(x / fw)
                r, g, b = round(r * gain), round(g * gain), round(b * gain)
            nr, ng, nb = navy_px[x, y]
            out_px[x, y] = (round(nr + (r - nr) * a),
                            round(ng + (g - ng) * a),
                            round(nb + (b - nb) * a))

    dst = Path(args.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, optimize=True)
    print(f"✓ {dst}  ({out_w}×{out_h}, {dst.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
