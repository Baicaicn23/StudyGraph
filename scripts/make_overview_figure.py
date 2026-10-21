#!/usr/bin/env python3
"""知迹 · 方法总览插图生成器 —— 论文级 method overview figure（纯 SVG，无外部依赖）。

风格参照学术论文里的 method overview figure：
奶油纸底 + 圆角面板 + 虚线「放大」连接锥 + 顶部彩色图例条 + 微缩 3D 质感元素
（渐变球、倒角块、程序化生成的场缩略图）+ 每栏底部一行小标题。

内容全部来自本项目真实实现（见 docs/作品集/参赛/02-主张与证据核对表.md）。

用法：
    uv run python scripts/make_overview_figure.py            # 只出 SVG
    uv run python scripts/make_overview_figure.py --png      # SVG + Chrome 渲染 PNG
"""

from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- 设计令牌

PAPER = "#FBF6EA"        # 纸底
CARD = "#FFFDF6"        # 面板/卡片
INK = "#2B2926"         # 主文字
MUTED = "#7C7468"       # 次要文字
FAINT = "#A79C88"       # 极弱文字
LINE = "#C9BFA8"        # 描边
TEAL = "#4FB3A4"
BLUE = "#5B8FD6"
PURPLE = "#9B7FD4"
YELLOW = "#E5B54B"
GREEN = "#7CB661"
RED = "#C9564A"
GREY = "#A8A196"        # 对照栏（灰化）

SANS = "PingFang SC, Hiragino Sans GB, Microsoft YaHei, Source Han Sans SC, sans-serif"
MONO = "SF Mono, Menlo, Consolas, monospace"

W, H = 1600, 760

# 面板水平分栏
PANEL_X = [(52, 420), (440, 808), (828, 1196), (1216, 1548)]
TOP = 96
BOTTOM = 656

OUT_DIR = Path("docs/作品集/插图/知迹方法总览")
OUT_SVG = OUT_DIR / "知迹-方法总览.svg"
OUT_PNG = OUT_DIR / "知迹-方法总览.png"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def tx(x, y, s, size=12, fill=INK, weight=400, anchor="start", family=SANS, ls=0, opacity=None):
    op = f' opacity="{opacity}"' if opacity is not None else ""
    lsp = f' letter-spacing="{ls}"' if ls else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}"{lsp}{op}>{esc(s)}</text>'
    )


def box(x, y, w, h, fill=CARD, stroke=LINE, rx=8, sw=1.2, shadow=True, dash=None, opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    sh = "fldShadow" if shadow else "none"
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" filter="url(#{sh})"{d}{op}/>'
    )


def arrow(x1, y1, x2, y2, color=MUTED, sw=1.4, head=5.2, dash=None):
    """直线 + 箭头（用 polygon 画头，避免 marker 依赖）。"""
    import math

    ang = math.atan2(y2 - y1, x2 - x1)
    bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
    p1 = (bx + head * 0.55 * math.cos(ang + 2.5), by + head * 0.55 * math.sin(ang + 2.5))
    p2 = (bx + head * 0.55 * math.cos(ang - 2.5), by + head * 0.55 * math.sin(ang - 2.5))
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{bx}" y2="{by}" stroke="{color}" '
        f'stroke-width="{sw}" stroke-linecap="round"{d}/>'
        f'<polygon points="{x2},{y2} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/>'
    )


def sphere(cx, cy, r, color, sid):
    """渐变球 —— 论文图里用来表示「可点亮的实体/状态」。"""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{sid})" '
        f'stroke="{color}" stroke-width="1"/>'
    )


def block3d(x, y, w, h, top_ratio=0.72, fill="#FFFFFF", stroke=LINE, label=None,
            sub=None, label_size=13, sub_size=10.5, text_fill=INK, sw=1.3):
    """带 3D 倒角的块：正面 + 顶面窄梯形 + 底部阴影带。"""
    tw = w * top_ratio
    x0 = x + (w - tw) / 2
    parts = [
        f'<polygon points="{x0},{y} {x0+tw},{y} {x+w},{y+h} {x},{y+h}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>',
        f'<polygon points="{x},{y+h} {x+w},{y+h} {x+w-5},{y+h+5} {x+5},{y+h+5}" '
        f'fill="{stroke}" opacity="0.28"/>',
    ]
    if label:
        parts.append(tx(x + w / 2, y + h * 0.5 + (0 if not sub else -4), label,
                        size=label_size, fill=text_fill, weight=600, anchor="middle"))
    if sub:
        parts.append(tx(x + w / 2, y + h * 0.5 + 13, sub, size=sub_size,
                        fill=MUTED, anchor="middle"))
    return "".join(parts)


def zoom_cone(x1, y1a, y1b, x2, y2a, y2b, color=FAINT):
    """虚线「放大」连接锥：左端一小段 → 右端一大段，论文图里表示同一结构的不同尺度。"""
    return (
        f'<path d="M{x1},{y1a} L{x2},{y2a} M{x1},{y1b} L{x2},{y2b}" stroke="{color}" '
        f'stroke-width="1.2" stroke-dasharray="5 4" fill="none"/>'
        f'<circle cx="{x1}" cy="{y1a}" r="2.4" fill="{color}"/>'
        f'<circle cx="{x1}" cy="{y1b}" r="2.4" fill="{color}"/>'
    )


def panel_backdrop(x0, x1, y0=TOP - 12, y1=BOTTOM + 8):
    """栏底衬：极淡的圆角矩形，制造论文图里「子图各自成块」的分隔感。"""
    return (
        f'<rect x="{x0 - 8}" y="{y0}" width="{x1 - x0 + 16}" height="{y1 - y0}" rx="12" '
        f'fill="#FFFDF7" opacity="0.72" stroke="#E2D9C4" stroke-width="0.9"/>'
    )


def field_thumb(x, y, w, h, gid, label=None):
    """程序化「场」缩略图 —— 用渐变模拟数据分布的纹理，替代真实数据截图。"""
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="url(#{gid})" '
             f'stroke="{LINE}" stroke-width="0.8"/>']
    if label:
        parts.append(tx(x + w / 2, y + h + 11, label, size=9, fill=MUTED, anchor="middle"))
    return "".join(parts)


def chip(x, y, w, h, label, color, size=10.5, text_fill="#FFFFFF", rx=5, fill=None):
    f = fill or color
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f}" '
        f'stroke="{f}" stroke-width="0.8"/>'
        + tx(x + w / 2, y + h / 2 + 3.6, label, size=size, fill=text_fill,
             weight=600, anchor="middle")
    )


def hline(x1, x2, y, color=LINE, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="{sw}"{d}/>'


def vline(x, y1, y2, color=LINE, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d}/>'


# ---------------------------------------------------------------- 静态资源

def defs() -> str:
    """渐变、滤镜、纹理。"""
    defs = [
        '<filter id="fldShadow" x="-25%" y="-25%" width="150%" height="160%">'
        '<feDropShadow dx="0" dy="1.6" stdDeviation="2.2" flood-color="#8A7B58" '
        'flood-opacity="0.20"/></filter>',
        '<filter id="paperGrain" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" result="n"/>'
        '<feColorMatrix in="n" type="saturate" values="0"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="0.05"/></feComponentTransfer>'
        '</filter>',
        '<radialGradient id="ballTeal" cx="34%" cy="30%" r="72%">'
        f'<stop offset="0%" stop-color="#9FE3D8"/><stop offset="55%" stop-color="{TEAL}"/>'
        '<stop offset="100%" stop-color="#2C7E74"/></radialGradient>',
        '<radialGradient id="ballBlue" cx="34%" cy="30%" r="72%">'
        f'<stop offset="0%" stop-color="#A9C6EF"/><stop offset="55%" stop-color="{BLUE}"/>'
        '<stop offset="100%" stop-color="#33608F"/></radialGradient>',
        '<radialGradient id="ballPurple" cx="34%" cy="30%" r="72%">'
        f'<stop offset="0%" stop-color="#CDBEEB"/><stop offset="55%" stop-color="{PURPLE}"/>'
        '<stop offset="100%" stop-color="#6B4E9E"/></radialGradient>',
        '<radialGradient id="ballYellow" cx="34%" cy="30%" r="72%">'
        f'<stop offset="0%" stop-color="#F6DFA4"/><stop offset="55%" stop-color="{YELLOW}"/>'
        '<stop offset="100%" stop-color="#A87F22"/></radialGradient>',
    ]
    # 程序化场缩略图（3 种不同色相）
    for gid, stops in [
        ("fldTeal", ["#0E3B3A", "#1E7F72", "#7FD3C0", "#EAF7F2"]),
        ("fldBlue", ["#122A4A", "#2C5E9E", "#7FAEE2", "#E9F1FA"]),
        ("fldPlum", ["#2A1E4A", "#5B3E8E", "#A98FD8", "#F0EAF9"]),
    ]:
        defs.append(
            f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
            + "".join(
                f'<stop offset="{i*33.3:.1f}%" stop-color="{c}"/>' for i, c in enumerate(stops)
            )
            + '</linearGradient>'
        )
    return "<defs>" + "".join(defs) + "</defs>"


# ---------------------------------------------------------------- 各面板

def panel_a(x0, x1) -> str:
    """① 回合：一次提问怎么走。"""
    cx = (x0 + x1) / 2
    p = []
    p.append(tx(x0 + 16, TOP + 22, "① 回合", size=11, fill=TEAL, weight=700, ls=1.2))
    p.append(tx(x0 + 16, TOP + 46, "一次提问，走的是一张画出来的图", size=15.5,
                fill=INK, weight=700))
    p.append(tx(x0 + 16, TOP + 64, "每一步都有名字、有位置、有留痕", size=10.5, fill=MUTED))

    # 提问
    p.append(box(cx - 62, TOP + 84, 124, 32, fill="#EAF7F4", stroke=TEAL, rx=16, sw=1.4))
    p.append(tx(cx, TOP + 105, "学生提问", size=12.5, fill="#1F6C63", weight=600, anchor="middle"))
    p.append(arrow(cx, TOP + 116, cx, TOP + 136, color=FAINT))

    # 路由 / 规划
    p.append(box(x0 + 26, TOP + 138, 152, 36, fill=CARD, stroke=LINE))
    p.append(tx(x0 + 102, TOP + 155, "意图路由", size=12.5, fill=INK, weight=600, anchor="middle"))
    p.append(tx(x0 + 102, TOP + 168, "六类意图 → 四个子智能体", size=9, fill=MUTED, anchor="middle"))
    p.append(arrow(x0 + 180, TOP + 156, x0 + 214, TOP + 156, color=FAINT))
    p.append(box(x0 + 216, TOP + 138, 152, 36, fill=CARD, stroke=LINE))
    p.append(tx(x0 + 292, TOP + 155, "规划", size=12.5, fill=INK, weight=600, anchor="middle"))
    p.append(tx(x0 + 292, TOP + 168, "复杂请求先拆步骤", size=9, fill=MUTED, anchor="middle"))
    p.append(arrow(x0 + 102, TOP + 174, x0 + 102, TOP + 196, color=FAINT))
    p.append(arrow(x0 + 292, TOP + 174, x0 + 292, TOP + 196, color=FAINT))

    # 模型 ⟷ 工具
    p.append(box(x0 + 26, TOP + 198, 152, 44, fill="#EAF0F9", stroke=BLUE))
    p.append(tx(x0 + 102, TOP + 217, "模型回合", size=12.5, fill="#24507F", weight=600, anchor="middle"))
    p.append(tx(x0 + 102, TOP + 232, "决定调哪个工具", size=9, fill=MUTED, anchor="middle"))
    p.append(box(x0 + 216, TOP + 198, 152, 44, fill="#F4EEFA", stroke=PURPLE))
    p.append(tx(x0 + 292, TOP + 217, "工具执行", size=12.5, fill="#5F4494", weight=600, anchor="middle"))
    p.append(tx(x0 + 292, TOP + 232, "九件工具，权限先过一道", size=9, fill=MUTED, anchor="middle"))
    p.append(arrow(x0 + 180, TOP + 212, x0 + 214, TOP + 212, color=BLUE, sw=1.6, head=5.6))
    p.append(arrow(x0 + 214, TOP + 230, x0 + 180, TOP + 230, color=PURPLE, sw=1.6, head=5.6))
    p.append(tx(x0 + 197, TOP + 203, "调", size=9.5, fill=BLUE, anchor="middle", weight=700))
    p.append(tx(x0 + 197, TOP + 248, "回填", size=9.5, fill=PURPLE, anchor="middle", weight=700))

    # 结果
    p.append(arrow(cx, TOP + 242, cx, TOP + 264, color=FAINT))
    p.append(box(x0 + 26, TOP + 266, 342, 40, fill="#FCF6E4", stroke=YELLOW))
    p.append(tx(x0 + 197, TOP + 285, "回答 + 引用到第几页", size=12.5, fill="#7A5A16",
                weight=600, anchor="middle"))
    p.append(tx(x0 + 197, TOP + 299, "检索片段、错因、掌握度一起进上下文", size=9,
                fill=MUTED, anchor="middle"))

    # 三条工程承诺
    p.append(tx(x0 + 16, TOP + 332, "回合之外的三条硬承诺", size=10.5, fill=INK, weight=700))
    tags = [("中断可续", "检查点恢复", TEAL), ("写操作先问", "人工确认后落库", PURPLE),
            ("过程可查", "回合 trace 归因", BLUE)]
    for i, (t1, t2, c) in enumerate(tags):
        ty = TOP + 344 + i * 30
        p.append(f'<circle cx="{x0+24}" cy="{ty+9}" r="4" fill="{c}"/>')
        p.append(tx(x0 + 36, ty + 13, t1, size=11, fill=INK, weight=600))
        p.append(tx(x0 + 112, ty + 13, t2, size=10, fill=MUTED))

    # trace 缩略树
    p.append(tx(x0 + 16, TOP + 442, "一次回合读成一棵树", size=10.5, fill=INK, weight=700))
    tree = [("第 1 步 · route", 0), ("第 2 步 · knowledge_search", 1),
            ("命中 3 段 · top1 相似 0.82", 2), ("第 3 步 · 生成回答", 1)]
    for i, (label, depth) in enumerate(tree):
        ty = TOP + 454 + i * 22
        ind = x0 + 22 + depth * 16
        if depth:
            p.append(f'<path d="M{ind-9},{ty-6} L{ind-9},{ty+2} L{ind-3},{ty+2}" '
                     f'stroke="{FAINT}" stroke-width="1" fill="none"/>')
        p.append(f'<rect x="{ind}" y="{ty-7}" width="{6}" height="{6}" rx="1.5" fill="{TEAL}"/>')
        p.append(tx(ind + 12, ty, label, size=9.5, fill=MUTED))
    return "".join(p)


def panel_b(x0, x1) -> str:
    """② 检索：资料怎么变成能召回的片段。"""
    p = []
    p.append(tx(x0 + 16, TOP + 22, "② 检索", size=11, fill=BLUE, weight=700, ls=1.2))
    p.append(tx(x0 + 16, TOP + 46, "四路找法，加权融合后再精排", size=15.5, fill=INK, weight=700))
    p.append(tx(x0 + 16, TOP + 64, "中文资料难找，所以不只找一路", size=10.5, fill=MUTED))

    # 入库缩略
    p.append(tx(x0 + 16, TOP + 92, "入库：原样秒传 → 逐页切块", size=10.5, fill=INK, weight=700))
    p.append(field_thumb(x0 + 18, TOP + 104, 62, 46, "fldTeal"))
    p.append(field_thumb(x0 + 88, TOP + 104, 62, 46, "fldBlue"))
    p.append(field_thumb(x0 + 158, TOP + 104, 62, 46, "fldPlum"))
    p.append(tx(x0 + 49, TOP + 172, "PDF", size=9, fill=MUTED, anchor="middle"))
    p.append(tx(x0 + 119, TOP + 172, "PPT", size=9, fill=MUTED, anchor="middle"))
    p.append(tx(x0 + 189, TOP + 172, "图片", size=9, fill=MUTED, anchor="middle"))
    p.append(arrow(x0 + 228, TOP + 127, x0 + 250, TOP + 127, color=FAINT))
    for i in range(4):
        p.append(f'<rect x="{x0+256}" y="{TOP+106+i*11}" width="{96-i*4}" height="8" rx="3" '
                 f'fill="{TEAL}" opacity="{0.85-i*0.16}"/>')
    p.append(tx(x0 + 304, TOP + 172, "带页码的片段", size=9, fill=MUTED, anchor="middle"))
    p.append(tx(x0 + 358, TOP + 172, "×2048", size=8.5, fill=FAINT, anchor="middle", family=MONO))

    # 四路召回
    p.append(tx(x0 + 16, TOP + 196, "召回：四条通道并行", size=10.5, fill=INK, weight=700))
    channels = [("原查询 FTS", "字面 trigram", TEAL, 1.0),
                ("同义 / 中英扩写", "换个说法也能找到", BLUE, 0.5),
                ("两字词 LIKE", "短词专门兜底", YELLOW, 0.8),
                ("向量语义", "零字面重叠", PURPLE, 1.0)]
    for i, (name, note, c, wgt) in enumerate(channels):
        ry = TOP + 208 + i * 30
        p.append(f'<rect x="{x0+16}" y="{ry}" width="4" height="18" rx="2" fill="{c}"/>')
        p.append(tx(x0 + 28, ry + 13, name, size=11, fill=INK, weight=600))
        p.append(tx(x0 + 140, ry + 13, note, size=9, fill=MUTED))
        bw = 96 * wgt
        p.append(f'<rect x="{x0+216}" y="{ry+4}" width="{bw:.1f}" height="10" rx="5" '
                 f'fill="{c}" opacity="0.75"/>')
        p.append(tx(x0 + 322, ry + 13, f"{wgt:.1f}", size=9.5, fill=MUTED, family=MONO))

    # 融合漏斗
    p.append(tx(x0 + 16, TOP + 342, "融合与排序", size=10.5, fill=INK, weight=700))
    p.append(block3d(x0 + 60, TOP + 354, 200, 40, fill="#EEF3FA", stroke=BLUE,
                      label="加权 RRF", sub="k=60，扩写路降权", label_size=12.5))
    p.append(arrow(x0 + 160, TOP + 394, x0 + 160, TOP + 412, color=FAINT))
    p.append(box(x0 + 60, TOP + 414, 200, 34, fill="#FBF3DF", stroke=YELLOW))
    p.append(tx(x0 + 160, TOP + 431, "词面精排", size=12, fill="#7A5A16", weight=600, anchor="middle"))
    p.append(tx(x0 + 160, TOP + 443, "只调顺序，不增删候选", size=8.5, fill=MUTED, anchor="middle"))

    # 命中片段
    p.append(arrow(x0 + 160, TOP + 448, x0 + 160, TOP + 466, color=FAINT))
    hits = [("P12 · 傅里叶变换", 0.91), ("P07 · 拉普拉斯", 0.84), ("P31 · 卷积定理", 0.78)]
    for i, (t, sc) in enumerate(hits):
        hy = TOP + 468 + i * 24
        p.append(box(x0 + 40, hy, 240, 20, fill=CARD, stroke=LINE, rx=4, shadow=False, sw=0.9))
        p.append(tx(x0 + 48, hy + 14, t, size=9.5, fill=INK))
        p.append(f'<rect x="{x0+208}" y="{hy+6}" width="{34*sc:.0f}" height="8" rx="4" fill="{TEAL}"/>')
        p.append(tx(x0 + 322, hy + 14, f"{sc:.2f}", size=9, fill=MUTED, family=MONO, anchor="end"))
    return "".join(p)


def panel_c(x0, x1) -> str:
    """③ 治理：模型能说什么 ≠ 能做什么。"""
    p = []
    p.append(tx(x0 + 16, TOP + 22, "③ 治理", size=11, fill=PURPLE, weight=700, ls=1.2))
    p.append(tx(x0 + 16, TOP + 46, "模型能说出工具名，不等于跑得动", size=15.5, fill=INK, weight=700))
    p.append(tx(x0 + 16, TOP + 64, "两道权限 + 一次确认 + 三道兜底", size=10.5, fill=MUTED))

    # 图例条
    legend = [("看得见的工具", TEAL), ("拦得住的执行", PURPLE),
              ("要人点头的写入", YELLOW), ("失败可降级", RED)]
    lx = x0 + 16
    for name, c in legend:
        wdt = 16 + len(name) * 9.4
        p.append(chip(lx, TOP + 78, wdt, 17, name, c, size=9.5, rx=4))
        lx += wdt + 6

    # schema 层
    p.append(block3d(x0 + 30, TOP + 110, 308, 44, fill="#EAF7F4", stroke=TEAL,
                      label="第一层 · schema", sub="工具表按角色裁剪，禁用工具根本不出现在提示词里",
                      label_size=12.5, text_fill="#1F6C63"))
    p.append(arrow(x0 + 184, TOP + 154, x0 + 184, TOP + 176, color=FAINT))
    p.append(tx(x0 + 192, TOP + 170, "模型点名 save_note", size=9, fill=MUTED))

    # 执行层
    p.append(block3d(x0 + 30, TOP + 178, 308, 52, fill="#F4EEFA", stroke=PURPLE,
                      label="第二层 · 执行", sub="is_tool_allowed 逐次判定，越权当场拦下",
                      label_size=12.5, text_fill="#5F4494"))

    # HITL 分支：写操作先问一句
    p.append(arrow(x0 + 184, TOP + 230, x0 + 184, TOP + 250, color=PURPLE))
    p.append(box(x0 + 46, TOP + 252, 276, 40, fill="#FCF6E4", stroke=YELLOW))
    p.append(tx(x0 + 184, TOP + 271, "写操作 → 先问一句", size=12, fill="#7A5A16",
                weight=600, anchor="middle"))
    p.append(tx(x0 + 184, TOP + 285, "interrupt 暂停，用户确认后才落库", size=9,
                fill=MUTED, anchor="middle"))

    # 三道兜底
    p.append(tx(x0 + 16, TOP + 316, "就算模型想乱来，还有三道", size=10.5, fill=INK, weight=700))
    guards = [("护栏", "拦提示词注入与空回答", TEAL, "Teal"),
              ("预算", "当日超限直接阻止调用", YELLOW, "Yellow"),
              ("trace", "每步调了什么、错在哪", BLUE, "Blue")]
    for i, (t1, t2, _c, gid) in enumerate(guards):
        gy = TOP + 328 + i * 30
        p.append(f'<circle cx="{x0+26}" cy="{gy+8}" r="5" fill="url(#ball{gid})"/>')
        p.append(tx(x0 + 40, gy + 12, t1, size=11, fill=INK, weight=600))
        p.append(tx(x0 + 84, gy + 12, t2, size=9.5, fill=MUTED))

    # 工具九宫格
    p.append(tx(x0 + 16, TOP + 434, "九个工具：查、存、问外面", size=10.5, fill=INK, weight=700))
    tools = [("查", "knowledge_search"), ("查", "mistake_search"), ("查", "read_file"),
             ("存", "save_note"), ("存", "write_file"), ("查", "list_files"),
             ("外面", "web_search"), ("外面", "fetch_url"), ("外面", "calculator")]
    tw, th, gap = 100, 34, 8
    for i, (kind, name) in enumerate(tools):
        r, c = divmod(i, 3)
        tx0 = x0 + 16 + c * (tw + gap)
        ty0 = TOP + 448 + r * (th + gap)
        color = {"查": TEAL, "存": PURPLE, "外面": BLUE}[kind]
        p.append(box(tx0, ty0, tw, th, fill=CARD, stroke=LINE, rx=5, shadow=False, sw=0.9))
        p.append(f'<rect x="{tx0}" y="{ty0}" width="3" height="{th}" rx="1.5" fill="{color}"/>')
        p.append(tx(tx0 + 10, ty0 + 14, kind, size=8.5, fill=color, weight=700))
        p.append(tx(tx0 + 10, ty0 + 26, name, size=9, fill=INK, family=MONO))
    return "".join(p)


def panel_d(x0, x1) -> str:
    """④ 对照：去掉治理层会怎样（整栏灰化）。"""
    p = []
    p.append(tx(x0 + 16, TOP + 22, "④ 对照", size=11, fill=GREY, weight=700, ls=1.2))
    p.append(tx(x0 + 16, TOP + 46, "没有这层治理，代价是什么", size=15.5, fill="#6E675C", weight=700))
    p.append(tx(x0 + 16, TOP + 64, "同一套模型，只撤掉工程约束", size=10.5, fill="#938B7D"))

    p.append(block3d(x0 + 24, TOP + 92, 284, 40, fill="#F1EEE7", stroke=GREY,
                      label="工具表：九个全给", sub="包括本轮不该用的写工具", label_size=12,
                      text_fill="#6E675C"))
    p.append(arrow(x0 + 166, TOP + 132, x0 + 166, TOP + 152, color=GREY, dash="4 3"))
    p.append(block3d(x0 + 24, TOP + 154, 284, 46, fill="#F1EEE7", stroke=GREY,
                      label="执行：无判定", sub="模型说要写就写", label_size=12, text_fill="#6E675C"))

    fails = [("越权写入", "提示词劝告不是承诺"),
             ("误操作不可撤", "没有确认这一步"),
             ("出问题查不到", "过程没有留痕")]
    p.append(tx(x0 + 16, TOP + 232, "三个具体后果", size=10.5, fill="#6E675C", weight=700))
    for i, (t1, t2) in enumerate(fails):
        fy = TOP + 246 + i * 40
        p.append(f'<circle cx="{x0+30}" cy="{fy+10}" r="7" fill="none" stroke="{RED}" '
                 f'stroke-width="1.4"/>')
        p.append(f'<path d="M{x0+26},{fy+6} L{x0+34},{fy+14} M{x0+34},{fy+6} L{x0+26},{fy+14}" '
                 f'stroke="{RED}" stroke-width="1.4"/>')
        p.append(tx(x0 + 46, fy + 8, t1, size=11.5, fill="#5A5348", weight=600))
        p.append(tx(x0 + 46, fy + 22, t2, size=9.5, fill="#938B7D"))

    p.append(box(x0 + 24, TOP + 372, 284, 74, fill="#F6F3EC", stroke=GREY, dash="5 4", sw=1.1))
    p.append(tx(x0 + 40, TOP + 394, "知迹的选择", size=10.5, fill="#6E675C", weight=700))
    for i, line in enumerate([
        "权限是执行层的硬判定，不是提示词里的请求",
        "写入类操作一律先问一句",
        "每一步都留痕，能读成一棵诊断树",
    ]):
        p.append(f'<circle cx="{x0+46}" cy="{TOP+412+i*16}" r="2.4" fill="{TEAL}"/>')
        p.append(tx(x0 + 56, TOP + 415 + i * 16, line, size=9.5, fill="#6E675C"))
    return "".join(p)


# ---------------------------------------------------------------- 组装

def build_svg() -> str:
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{SANS}">']
    s.append(defs())

    # 纸底
    s.append(f'<rect x="14" y="12" width="{W-28}" height="{H-24}" rx="20" fill="{PAPER}" '
             f'stroke="#DED3BC" stroke-width="1.2" filter="url(#fldShadow)"/>')
    s.append(f'<rect x="14" y="12" width="{W-28}" height="{H-24}" rx="20" filter="url(#paperGrain)" '
             f'opacity="0.5"/>')

    # 标题条
    s.append(tx(52, 50, "知迹 · 方法总览", size=19, fill=INK, weight=700))
    s.append(tx(52, 68, "ZHIJI — how one study turn actually runs", size=10.5,
                fill=MUTED, family=MONO, ls=0.4))
    s.append(tx(1548, 46, "全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育",
                size=10.5, fill=MUTED, anchor="end"))
    s.append(tx(1548, 64, "LangGraph 状态图 · 四路混合检索 · 工具执行治理",
                size=10, fill=FAINT, anchor="end", family=MONO))
    s.append(hline(52, 1548, 82, color="#DCD2BB", sw=1.2))

    # 分栏与放大连接锥
    s.append(vline(430, TOP, BOTTOM, color="#DED3BC", sw=1, dash="4 5"))
    s.append(vline(818, TOP, BOTTOM, color="#DED3BB", sw=1, dash="4 5"))
    s.append(vline(1206, TOP, BOTTOM, color="#DED3BB", sw=1, dash="4 5"))
    for x0, x1 in PANEL_X:
        s.append(panel_backdrop(x0, x1))
    # 锥：从 A 的「工具执行」放大到 B 的检索内部
    s.append(zoom_cone(392, TOP + 200, TOP + 240, 440, TOP + 96, TOP + 168))
    # 锥：从 B 的「融合」放大到 C 的执行层
    s.append(zoom_cone(790, TOP + 356, TOP + 396, 828, TOP + 178, TOP + 230))

    s.append(panel_a(*PANEL_X[0]))
    s.append(panel_b(*PANEL_X[1]))
    s.append(panel_c(*PANEL_X[2]))
    s.append(panel_d(*PANEL_X[3]))

    # 每栏底部小标题（论文图的栏标）
    labels = ["① 一次回合", "② 四路检索", "③ 执行治理", "④ 撤掉治理会怎样"]
    for (x0, x1), lab in zip(PANEL_X, labels, strict=True):
        s.append(tx((x0 + x1) / 2, BOTTOM + 34, lab, size=12, fill=INK, weight=700,
                     anchor="middle"))
        s.append(hline(x0 + 40, x1 - 40, BOTTOM + 46, color="#DCD2BB", sw=1))

    # 图注
    s.append(tx(52, H - 26, "图 1 · 知迹把「整理资料 → 自动出题 → 结合知识库复习」落到一条"
                            "可恢复、可拦截、可度量的状态图上",
                size=10.5, fill=MUTED))
    s.append(tx(1548, H - 26, "每条机制都可在 evals/ 与 tests/ 里复现", size=10,
                fill=FAINT, anchor="end", family=MONO))
    s.append("</svg>")
    return "".join(s)


def render_png(svg_path: Path, png_path: Path, scale: int = 2) -> bool:
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).exists():
        print("! 未找到 Chrome，跳过 PNG 渲染", file=sys.stderr)
        return False
    tmp_html = png_path.with_suffix(".render.html")
    tmp_html.write_text(
        f'<!doctype html><meta charset="utf-8">'
        f'<style>html,body{{margin:0;padding:0;background:{PAPER};}}'
        f'img{{display:block;width:{W}px;height:{H}px;}}</style>'
        f'<img src="{svg_path.resolve().as_uri()}">',
        encoding="utf-8",
    )
    out = png_path.with_suffix(".chrome.png")
    cmd = [
        chrome, "--headless=new",
        "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
        "--virtual-time-budget=4000",
        f"--force-device-scale-factor={scale}",
        f"--window-size={W},{H}", f"--screenshot={out.resolve()}",
        tmp_html.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=False, capture_output=True)
    produced = out.with_suffix(".chrome.png")
    if not produced.exists():
        produced = out
    if produced.exists() and produced.stat().st_size > 0:
        shutil.move(str(produced), str(png_path))
        tmp_html.unlink(missing_ok=True)
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true", help="同时用 Chrome 渲染 PNG")
    ap.add_argument("--scale", type=int, default=2, help="PNG 倍率（默认 2）")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg = build_svg()
    OUT_SVG.write_text(svg, encoding="utf-8")
    print(f"✓ SVG  → {OUT_SVG}  ({len(svg) / 1024:.1f} KB)")

    if args.png:
        if render_png(OUT_SVG, OUT_PNG, args.scale):
            kb = OUT_PNG.stat().st_size / 1024
            print(f"✓ PNG  → {OUT_PNG}  ({kb:.0f} KB, {W*args.scale}×{H*args.scale})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
