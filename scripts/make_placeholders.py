#!/usr/bin/env python3
"""生成三张配图的占位 PNG（明亮浅色调，标注用途）。

**为什么需要占位图**
- slidep 在引用的图片不存在时，会生成一个**损坏的 SVG 占位符**
  （嵌套 svg，validate 会报 MalformedXml）——交付件带着报错不合格；
- 用户要自己交给生图 Agent 出图，出图前 PPT 也需要能看。

所以这里生成三张**浅色调、带用途说明**的占位图。生图 Agent 出图后，
用同名文件覆盖 `assets/` 下的对应文件即可，无需改 PPT。

用法：
    uv run --with pillow python scripts/make_placeholders.py
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path("docs/作品集/参赛/知迹答辩/assets")
BG = (247, 249, 252)
INK = (30, 62, 140)
SUB = (110, 120, 140)
LINE = (214, 220, 229)

FONTS = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]


def font(size: int):
    for f in FONTS:
        p = pathlib.Path(f)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default()


def make(name: str, w: int, h: int, title: str, desc: str, badge: str) -> None:
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)

    # 斜向淡色网格，暗示「这是待替换的图位」
    for x in range(0, w, 48):
        d.line([(x, 0), (x, h)], fill=(240, 243, 247), width=1)
    for y in range(0, h, 48):
        d.line([(0, y), (w, y)], fill=(240, 243, 247), width=1)

    # 边框
    d.rectangle([6, 6, w - 7, h - 7], outline=LINE, width=2)

    # 中央：图标位（一个简化的取景框 + 圆点）
    cx, cy = w // 2, int(h * 0.36)
    r = min(w, h) // 7
    d.rounded_rectangle(
        [cx - r * 2, cy - r * 3 // 2, cx + r * 2, cy + r * 3 // 2],
        radius=10, outline=(170, 190, 220), width=3,
    )
    d.ellipse([cx - r // 2, cy - r // 3, cx + r // 2, cy + r // 3],
              outline=(170, 190, 220), width=3)
    d.polygon(
        [(cx + r // 3, cy - r // 5), (cx + r * 4 // 3, cy + r // 2), (cx - r // 3, cy + r // 2)],
        fill=(196, 210, 232),
    )

    # 标题
    f1 = font(int(h * 0.085))
    bbox = d.textbbox((0, 0), title, font=f1)
    d.text(((w - (bbox[2] - bbox[0])) / 2, cy + int(h * 0.13)), title, font=f1, fill=INK)

    # 说明
    f2 = font(int(h * 0.052))
    for i, line in enumerate(desc):
        bb = d.textbbox((0, 0), line, font=f2)
        d.text(((w - (bb[2] - bb[0])) / 2, cy + int(h * 0.24) + i * int(h * 0.075)),
               line, font=f2, fill=SUB)

    # 角标
    f3 = font(int(h * 0.042))
    bb = d.textbbox((0, 0), badge, font=f3)
    d.rounded_rectangle(
        [w - (bb[2] - bb[0]) - 44, 26, w - 22, 26 + (bb[3] - bb[1]) + 18],
        radius=8, fill=(232, 239, 248),
    )
    d.text((w - (bb[2] - bb[0]) - 33, 32), badge, font=f3, fill=INK)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    im.save(path, "PNG")
    print(f"✓ {path}  ({w}×{h})")


def main() -> int:
    make(
        "p01-cover-desk.png", 1240, 1440,
        "封面配图",
        ["浅米白书桌 · 整理好的资料与笔记本", "右上 45° 柔光 · 3D 写实 · 无人"],
        "待生图",
    )
    make(
        "p07-gate.png", 1600, 900,
        "写入确认配图",
        ["半透明挡板拦住悬浮的笔 · 后方待写入卡片", "明亮浅色调 · 3D 写实 · 无人"],
        "待生图",
    )
    make(
        "p16-closing-desk.png", 1040, 1440,
        "收束配图",
        ["与封面同一张书桌 · 资料 / 答题纸 / 日历", "同一套光线与材质 · 3D 写实 · 无人"],
        "待生图",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
