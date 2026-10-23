#!/usr/bin/env python3
"""知迹答辩 PPT · slides_maker 构建脚本

风格：`consulting` 预设（白底 · 行动结论式标题 · 藏蓝→翠绿渐变顶线 · 5 色语义契约）
叙事：痛点 → 定位 → 两个应用场景 → 真实界面 → 工程三条线 → 边界 → Roadmap

用法：
    python3 build_deck.py                # 生成 pptx
    python3 build_deck.py --render       # 生成并渲染预览
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path.home() / ".workbuddy/skills/slide-maker"
sys.path.insert(0, str(SKILL / "scripts"))

import deckkit as dk  # noqa: E402
import presets  # noqa: E402
from pptx.enum.shapes import PP_PLACEHOLDER as _PH  # noqa: E402

OUT = Path("docs/作品集/参赛/知迹答辩")
ASSETS = OUT / "assets"
PPTX = OUT / "知迹答辩.pptx"

# ---------------------------------------------------------------- 风格

presets.apply("consulting")
# 中文字体：macOS 自带 苹方/冬青黑体，避免 tofu
dk.FONT = "Hiragino Sans GB"
dk.DISPLAY = "Hiragino Sans GB"
dk.MONO = "Menlo"
dk.EAFONT = "Hiragino Sans GB"
dk.EADISPLAY = "Hiragino Sans GB"

def C(t):
    """元组 → RGBColor（deckkit 的颜色参数必须是 RGBColor 实例）。"""
    return dk.RGBColor(*t) if isinstance(t, tuple) else t


INK = dk.DEEP
NAVY = C(dk.BLUE)
EMERALD = C((30, 133, 108))
GOLD = C((166, 124, 12))
CORAL = C((192, 73, 46))
SLATE = C((88, 102, 124))
BG = C((255, 255, 255))
MUTE = C((89, 98, 112))          # 4.5:1 on light
LIGHT = C((242, 246, 250))
LINE = C((214, 222, 232))
TINT = C((238, 244, 249))      # 中性浅底（断链图节点）
PRI = NAVY                    # 断链图节点左条/文字

W, H = 13.333, 7.5          # 英寸（16:9）
M = 0.62                    # 左右安全边距
CW = W - 2 * M               # 内容宽

prs = dk.Presentation()
prs.slide_width = dk.Inches(W)
prs.slide_height = dk.Inches(H)
dk.set_ground(BG)


def slide():
    return dk.add_slide(prs)


# ---- 字号温和提升（1.10×）：对齐 editable-research-ppt 的可读性标准 ----
SCALE = 1.10
_orig_text = dk.text


def _scaled_text(slide, x, y, w, h, paras, **kw):
    scaled = []
    for p_ in paras:
        scaled.append([(t, round(sz * SCALE, 1), *rest) for (t, sz, *rest) in p_])
    return _orig_text(slide, x, y, w, h, scaled, **kw)


dk.text = _scaled_text


def para(runs, size=14, color=INK, bold=False, ls=None):
    """单段落 run 构造器。"""
    if isinstance(runs, str):
        runs = [runs]
    return [(r, size, color, bold, False, dk.FONT) for r in runs]


def body(s, x, y, w, txt, size=14, color=SLATE, bold=False, ls=1.42, gap=0.10):
    """放一段文字，高度自动测量（measure 与 place 用同一个字号/行距/字体）。"""
    runs = [(txt, size, color, bold, False, dk.FONT)]
    h = dk.measure_text([(txt, bold)], w, size, font=dk.FONT, line_spacing=ls)
    dk.text(s, x, y, w, h, [runs], line_spacing=ls)
    return y + h + gap


def head(s, title, kicker="", accent=NAVY):
    """页眉：章节标签 + 行动结论式标题 + 渐变顶线。返回内容起始 y。"""
    # 顶部条：藏蓝 → 翠绿。渲染器对渐变支持不稳，用「左深右浅」两段拼接等效实现
    dk.box(s, 0, 0, W * 0.62, 0.13, fill=NAVY)
    dk.box(s, W * 0.62, 0, W * 0.24, 0.13, fill=C((30, 110, 100)))
    dk.box(s, W * 0.86, 0, W * 0.14, 0.13, fill=EMERALD)
    y = 0.46
    if kicker:
        dk.text(s, M, y, CW, 0.26, [para(kicker, 11.5, EMERALD, True)])
        y += 0.32
    # 标题按测量高度自适应，最多两行
    th = dk.measure_text([(title, True)], CW, 23, font=dk.FONT, line_spacing=1.18)
    th = min(th, 0.92)          # 标题最多两行，超出即压
    dk.text(s, M, y, CW, th, [para(title, 23, INK, True)], line_spacing=1.18)
    y += th + 0.16
    dk.box(s, M, y, 1.70, 0.032, fill=NAVY)
    dk.box(s, M + 1.70, y, 0.90, 0.032, fill=EMERALD)
    return y + 0.30


FLOOR = 6.80          # 内容区底边（页脚安全线之上）


def foot(s, n, total=18, note=""):
    """页脚：细分隔线 + 左侧标签 + 右侧页码。"""
    dk.hrule(s, M, H - 0.46, CW, color=LINE, weight=0.012)
    dk.text(s, M, H - 0.38, CW * 0.6, 0.22,
            [para(note or "知迹 · 赛道十三 · 智慧教育", 9, MUTE)])
    dk.text(s, W - M - 1.2, H - 0.38, 1.2, 0.22,
            [[(f"{n:02d}", 10, NAVY, True, False, dk.FONT),
              (f" / {total}", 9, MUTE, False, False, dk.FONT)]],
            align=dk.PP_ALIGN.RIGHT)


def dfoot(s, n, total=18):
    """深色页的页脚：字色反过来，否则在深蓝上几乎看不见。"""
    dk.hrule(s, M, H - 0.46, CW, color=C((38, 62, 90)), weight=0.012)
    dk.text(s, M, H - 0.38, CW * 0.6, 0.22,
            [para("知迹 · 赛道十三 · 智慧教育", 9, C((128, 154, 184)))])
    dk.text(s, W - M - 1.2, H - 0.38, 1.2, 0.22,
            [[(f"{n:02d}", 10, C((122, 226, 198)), True, False, dk.FONT),
              (f" / {total}", 9, C((128, 154, 184)), False, False, dk.FONT)]],
            align=dk.PP_ALIGN.RIGHT)


def divider(s, num, section, headline, lead, chips, n, pages=""):
    """章节页：深蓝底 + 大号章节序号 + 一句导语 + 本章小标题 + 本节页码区间。"""
    dk.box(s, 0, 0, W, H, fill=C((14, 32, 61)))
    dk.box(s, 0, 0, W, 0.06, fill=C((30, 120, 104)))
    dk.text(s, M + 0.10, 1.16, 3.2, 1.40, [para(num, 88, C((48, 112, 152)), True)])
    dk.text(s, M + 0.14, 2.78, 6.4, 0.34, [para(section, 19, C((122, 226, 198)), True)])
    dk.text(s, M + 0.14, 3.26, 8.55, 1.20,
            [para(headline, 32, C((255, 255, 255)), True)], line_spacing=1.20)
    dk.text(s, M + 0.14, 4.56, 8.55, 0.90,
            [para(lead, 14.5, C((170, 192, 218)))], line_spacing=1.50)
    tx = M + 0.14
    for c in chips:
        cwid = pill_width(c, 10.5, 0.46)
        dk.box(s, tx, 5.86, cwid, 0.38, fill=None, line=C((58, 100, 128)),
               line_w=0.9, round=True, r=0.19)
        dk.text(s, tx, 5.91, cwid, 0.28, [para(c, 10.5, C((186, 216, 232)), True)],
                align=dk.PP_ALIGN.CENTER, anchor=dk.MSO_ANCHOR.MIDDLE)
        tx += cwid + 0.16
    if pages:
        dk.box(s, 9.52, 2.62, 0.014, 3.30, fill=C((40, 66, 96)))
        dk.text(s, 9.82, 2.74, 2.6, 0.24, [para("本 节", 10, C((128, 154, 184)), True)])
        dk.text(s, 9.82, 3.02, 2.9, 0.62, [para(pages, 34, C((255, 255, 255)), True)])
        dk.text(s, 9.82, 3.74, 2.6, 0.24,
                [para(f"{len(chips)} 个小节", 10, C((128, 154, 184)))])
    dfoot(s, n)


def insight(s, x, y, w, label, hero, txt, accent=NAVY):
    """结论条：左侧竖条 + 一句 so-what。"""
    h = 0.72
    dk.box(s, x, y, w, h, fill=LIGHT, round=True, r=0.07)
    dk.box(s, x, y, 0.055, h, fill=accent)
    dk.text(s, x + 0.24, y + 0.10, w - 0.45, 0.22, [para(label, 10, accent, True)])
    dk.text(s, x + 0.24, y + 0.33, w - 0.45, 0.32, [para(hero, 14, INK, True)])
    return y + h


def card(s, x, y, w, h, title, lines, accent=NAVY, num=""):
    """卡片：细描边 + 顶部色条 + 标题 + 要点。"""
    dk.box(s, x, y, w, h, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, x + 0.02, y + 0.02, w - 0.04, 0.05, fill=accent)
    ty = y + 0.22
    if num:
        dk.box(s, x + 0.22, ty, 0.34, 0.34, fill=accent, round=True, r=0.05)
        dk.text(s, x + 0.22, ty + 0.055, 0.34, 0.24,
                [para(num, 12, C((255, 255, 255)), True)], align=dk.PP_ALIGN.CENTER)
        dk.text(s, x + 0.66, ty + 0.045, w - 0.9, 0.28, [para(title, 15, INK, True)])
        ty += 0.46
    else:
        dk.text(s, x + 0.22, ty, w - 0.44, 0.28, [para(title, 15, INK, True)])
        ty += 0.36
    for ln in lines:
        ty = body(s, x + 0.22, ty, w - 0.44, ln, 12, SLATE, ls=1.30) + 0.09
    return ty


def figure_slot(s, x, y, w, h, caption, tag):
    """图位：留白 + 虚线框 + 说明（图片生成后替换此框）。"""
    dk.box(s, x, y, w, h, fill=C((250, 251, 252)), line=C((140, 152, 168)), line_w=1.0,
           round=True, r=0.07)
    dk.text(s, x, y + h / 2 - 0.30, w, 0.30, [para(tag, 13, C((120, 132, 148)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.text(s, x + 0.3, y + h / 2 + 0.02, w - 0.6, 0.46,
            [[(caption, 11, C((120, 132, 148)), False, False, dk.FONT)]],
            align=dk.PP_ALIGN.CENTER)


FONT_FILE = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def pill_width(txt, size=9.5, pad=0.42):
    """胶囊标签宽度 = 文字实宽 + 左右内边距（PIL 量真宽，避免长标签被截）。"""
    from PIL import ImageFont
    try:
        f = ImageFont.truetype(FONT_FILE, int(size * 6))
        return f.getlength(txt) / 6 / 72 + pad
    except OSError:
        return len(txt) * size / 72 + pad


# ================================================================ 01 封面

s = slide()
dk.box(s, 0, 0, W, H, fill=C((14, 32, 61)))
dk.box(s, 0, 0, W, 0.16, fill=NAVY)

# 右半幅：真实桌面场景。图片左缘已由 scripts/prep_cover_image.py 烘焙成深蓝渐变，
# 与本页背景同色，接缝处是渐变而不是一刀切。
PIC_X = 7.55
dk.picture(s, str(ASSETS / "p01-cover-desk.png"), PIC_X, 0.16, W - PIC_X, H - 0.16,
           fit="cover", alt="")

dk.text(s, M + 0.12, 1.54, 6.0, 0.26,
        [para("全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育", 12, C((160, 195, 230)), True)])
dk.text(s, M + 0.12, 1.96, 6.2, 1.24, [para("知迹", 62, C((255, 255, 255)), True)])
dk.box(s, M + 0.12, 3.18, 1.50, 0.036, fill=C((30, 110, 100)))
dk.box(s, M + 1.62, 3.18, 0.90, 0.036, fill=EMERALD)
SUBT = C((122, 226, 198))          # 「言必有据」的亮青绿
dk.text(s, M + 0.12, 3.46, 6.75, 0.66,
        [[("一个", 26, C((255, 255, 255)), True, False, dk.FONT),
          ("会整理、会出题", 26, SUBT, True, False, dk.FONT),
          ("的学习 Agent", 26, C((255, 255, 255)), True, False, dk.FONT)]],
        line_spacing=1.20)
dk.text(s, M + 0.12, 4.32, 5.62, 0.95,
        [[("喂入资料，自动出题，闭环复习。", 15.5, C((205, 220, 240)), False, False, dk.FONT)],
         [("它记得你错在哪，也知道明天让你练什么。", 15.5, C((150, 205, 182)), True, False, dk.FONT)]],
        line_spacing=1.42)

# 技术底座：三个胶囊标签（替代原来两行长文本，避免左栏挤成一坨）
tx = M + 0.12
for tag in ("LangGraph 状态机", "四路混合检索", "284 项自动化测试"):
    tw = pill_width(tag)
    dk.box(s, tx, 5.66, tw, 0.34, fill=C((24, 47, 82)), line=C((58, 106, 126)),
           line_w=0.75, round=True, r=0.17)
    dk.text(s, tx, 5.66 + 0.075, tw, 0.19,
            [para(tag, 9.5, C((178, 210, 228)), True)], align=dk.PP_ALIGN.CENTER)
    tx += tw + 0.14

# ================================================================ 02 痛点与破局

s = slide()
y = head(s, "最聪明的 AI，也做不了你的「专属私教」",
         "痛点 · 不是 AI 不聪明，是这些活它不干")

# 左侧：纯痛点场景（不出现知迹的任何功能，否则和「翻车」的标题自相矛盾）
WARN = C((197, 106, 82))
story = [
    ("周一", "网盘囤了 100 多页独家复习提纲，没索引，等于没存。"),
    ("周三", "问通用 AI 考点，答得顺畅，可用的不是我们教材的定义，还得自己翻书核一遍。"),
    ("周五", "做错核心题，下周同类型再考，没有复习机制，照错不误。"),
]
ty = y + 0.06
for i, (t, d) in enumerate(story):
    # 竖线把三段串成一条时间轴（最后一段不画）
    if i < len(story) - 1:
        dk.box(s, M + 0.153, ty + 0.25, 0.014, 1.38 - 0.30, fill=C((228, 222, 216)))
    # 时间轴节点：一个小圆点就够了，比红感叹号克制（渲染器的圆角半径有上限，大圆会变圆角方块）
    dk.box(s, M + 0.093, ty + 0.115, 0.135, 0.135, fill=WARN, round=True, r=0.068)
    dk.text(s, M + 0.48, ty, 6.1, 0.32, [para(t, 17, INK, True)])
    body(s, M + 0.48, ty + 0.40, 6.1, d, 15, SLATE, ls=1.50)
    ty += 1.38

# 右侧：一条断掉的链（资料 → 题 → 复习），断口就是上面三段经历
rx = M + 7.10
rw = CW - 7.10
dk.text(s, rx, y + 0.06, rw, 0.28, [para("断在哪，一看就明白", 16, INK, True)])
chain = [
    ("资料", "囤了 100 页，没索引", TINT, PRI),
    ("变不成题", None, None, None),
    ("题目", "网上找，对不上讲义", TINT, PRI),
    ("进不了复习", None, None, None),
    ("复习", "做完就忘，没人排", TINT, PRI),
]
cy = y + 0.44
for label, sub, tint, ink in chain:
    if sub is None:                      # 断口：细线 + 红圈 ✕ + 短句
        dk.box(s, rx + 0.44, cy + 0.02, 0.03, 0.50, fill=C((228, 222, 216)))
        dk.box(s, rx + 0.30, cy + 0.08, 0.32, 0.32, fill=C((255, 255, 255)), line=WARN,
               line_w=1.1, round=True, r=0.16)
        dk.text(s, rx + 0.30, cy + 0.13, 0.32, 0.22, [para("✕", 11, WARN, True)],
                align=dk.PP_ALIGN.CENTER)
        dk.text(s, rx + 0.80, cy + 0.14, rw - 0.9, 0.26, [para(label, 13.5, WARN, True)])
        cy += 0.56
    else:
        dk.box(s, rx, cy, rw, 0.72, fill=tint, line=LINE, line_w=0.9, round=True, r=0.07)
        dk.box(s, rx, cy, 0.08, 0.72, fill=PRI)
        dk.text(s, rx + 0.28, cy + 0.10, rw - 0.5, 0.28, [para(label, 17, ink, True)])
        dk.text(s, rx + 0.28, cy + 0.40, rw - 0.5, 0.26, [para(sub, 13, SLATE)])
        cy += 0.86

# 底部：整页唯一的重色横带。链条全篇统一为「资料 → 错题 → 复习」
by = 6.26
BH = 0.74
dk.box(s, M, by, CW, BH, fill=C((21, 118, 99)), round=True, r=0.07)
dk.box(s, M, by, 0.055, BH, fill=C((146, 214, 194)))
MINT = C((206, 240, 228))
WHITE = C((255, 255, 255))

dk.text(s, M + 0.26, by + 0.13, 1.1, 0.20, [para("破局点", 9.5, MINT, True)])
dk.text(s, M + 1.26, by + 0.20, CW - 3.35, 0.36,
        [[("把「资料 → 错题 → 复习」", 16.5, WHITE, True, False, dk.FONT),
          ("这条断掉的线，接起来。", 16.5, MINT, True, False, dk.FONT)]])
foot(s, 2)

# ================================================================ 章节 01：它做什么

s = slide()
divider(s, "01", "这一章：它做什么",
        "一个 Agent 能在学习里，替你做多少事？",
        "不是多一个聊天窗口。是把整理资料、出题、盯复习这三件事，从你手里接过去。",
        ["定位：会动手的 Agent", "场景 ① 知识库整理", "场景 ② 出题与复习"], 3, "04 — 06")

# ================================================================ 04 产品定位

s = slide()
y = head(s, "不只是聊天框：它自己整理、自己出题、自己盯",
         "定位 · 会动手的 Agent，不是会聊天的对话框")


def glyph(s, kind, x, y, d, color):
    """三个卡片图标：文件夹 / 靶心 / 日历。全部用几何形状画，不用 emoji（跨端渲染不可控）。"""
    if kind == "folder":
        dk.box(s, x, y + 0.01, 0.10, 0.045, fill=color, round=True, r=0.015)
        dk.box(s, x, y + 0.045, d, 0.155, fill=None, line=color, line_w=1.1,
               round=True, r=0.02)
        for i in range(2):
            dk.box(s, x + 0.045, y + 0.085 + i * 0.045, d - 0.09, 0.018,
                   fill=color, round=True, r=0.009)
    elif kind == "target":
        dk.box(s, x, y, d, d, fill=None, line=color, line_w=1.2, round=True, r=d / 2)
        dk.box(s, x + 0.06, y + 0.06, d - 0.12, d - 0.12, fill=None, line=color,
               line_w=0.9, round=True, r=(d - 0.12) / 2)
        dk.box(s, x + d / 2 - 0.03, y + d / 2 - 0.03, 0.06, 0.06, fill=color,
               round=True, r=0.03)
    else:  # calendar
        for tx in (0.05, 0.155):
            dk.box(s, x + tx, y - 0.005, 0.025, 0.05, fill=color, round=True, r=0.012)
        dk.box(s, x, y + 0.03, d, 0.185, fill=None, line=color, line_w=1.1,
               round=True, r=0.03)
        dk.box(s, x + 0.005, y + 0.075, d - 0.01, 0.02, fill=color)
        for tx in (0.045, 0.105, 0.165):
            dk.box(s, x + tx, y + 0.13, 0.026, 0.026, fill=color, round=True, r=0.006)


EMER_TXT = C((22, 112, 92))
three = [
    ("私人定制的知识库问答", "folder", NAVY, C((238, 244, 249)), [
        [("讲义/笔记传进去，按学科归好。它既懂通用知识，更懂你这一门课；"
          "想核对原话，点 ", 12.5, SLATE, False, False, dk.FONT),
         ("[P12]", 11.5, NAVY, True, False, dk.MONO),
         (" 就跳到第 12 页。", 12.5, SLATE, False, False, dk.FONT)],
    ]),
    ("基于私有库的自动出题机", "target", EMERALD, C((238, 247, 243)), [
        [("不要网上烂大街的题库。只从你的讲义出题，"
          "几百页死资料变成一场模拟考。", 12.5, SLATE, False, False, dk.FONT)],
    ]),
    ("死咬不放的错题追踪器", "calendar", GOLD, C((252, 249, 239)), [
        [("不只记错题，更记错因。根据薄弱点自动生成", 12.5, SLATE, False, False, dk.FONT),
         ("变式题", 12.5, INK, True, False, dk.FONT),
         ("，配合间隔重复，直到真正掌握。", 12.5, SLATE, False, False, dk.FONT)],
    ]),
]
cw3 = (CW - 0.44) / 3
cx = M
for title, kind, c, tint, paras_ in three:
    dk.box(s, cx, y + 0.04, cw3, 2.44, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, cx + 0.02, y + 0.06, cw3 - 0.04, 0.05, fill=c)
    dk.box(s, cx + 0.24, y + 0.28, 0.50, 0.50, fill=tint, line=c, line_w=0.75,
           round=True, r=0.11)
    glyph(s, kind, cx + 0.24 + 0.10, y + 0.28 + 0.10, 0.30, c)
    dk.text(s, cx + 0.24, y + 0.94, cw3 - 0.44, 0.34, [para(title, 15.5, INK, True)])
    th = dk.measure_text([(title, True)], cw3 - 0.44, 15.5, font=dk.FONT, line_spacing=1.15)
    by_ = y + 0.94 + max(th, 0.30) + 0.14
    dk.text(s, cx + 0.24, by_, cw3 - 0.44, 2.44 - (by_ - y - 0.04) - 0.12,
            paras_, line_spacing=1.46)
    cx += cw3 + 0.22

# 为什么不做大而全：金句 + 支撑点（关键词标绿，评委扫一眼就能看到工程深度）
by = y + 2.66
dk.box(s, M, by, CW, 1.86, fill=C((248, 250, 252)), line=LINE, line_w=0.9, round=True, r=0.07)
dk.text(s, M + 0.30, by + 0.20, CW - 0.6, 0.28,
        [para("为什么不做「大而全」的平台", 15, INK, True)])
dk.text(s, M + 0.30, by + 0.56, CW - 0.6, 0.30,
        [para("因为多一个功能，就多一条出错的路径。", 16, INK, True)])
dk.text(s, M + 0.30, by + 0.98, CW - 0.6, 0.34,
        [[("所以鉴权、多租户这类外围功能主动不做，把工程精力全压在 ", 12.5, SLATE, False, False, dk.FONT),
          ("工具双层权限", 12.5, EMER_TXT, True, False, dk.FONT),
          ("、", 12.5, SLATE, False, False, dk.FONT),
          ("HITL 写入确认", 12.5, EMER_TXT, True, False, dk.FONT),
          ("、", 12.5, SLATE, False, False, dk.FONT),
          ("284 项自动化评测", 12.5, EMER_TXT, True, False, dk.FONT),
          (" 上。", 12.5, SLATE, False, False, dk.FONT)]],
        line_spacing=1.40)
dk.text(s, M + 0.30, by + 1.42, CW - 0.6, 0.30,
        [para("所有技术设计只为一件事：让答案可核验。", 13.5, C((30, 110, 92)), True)])
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("定位", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("克制不是少做，是把「资料 → 错题 → 复习」每一环都做到能核验。",
              11, C((38, 52, 46)), True)])
foot(s, 4)

# ================================================================ 05 场景一：知识库整理


def step_row(s, x, y0, w, num, title, desc, accent=NAVY, tint=None):
    tint = tint or C((241, 246, 250))
    """带序号的一步：圆角序号片 + 标题 + 说明。"""
    dk.box(s, x, y0, 0.42, 0.42, fill=tint, line=accent, line_w=0.9, round=True, r=0.09)
    dk.text(s, x, y0 + 0.095, 0.42, 0.24, [para(num, 12.5, accent, True)],
            align=dk.PP_ALIGN.CENTER)
    dk.text(s, x + 0.60, y0 - 0.02, w - 0.60, 0.30, [para(title, 15.5, INK, True)])
    body(s, x + 0.60, y0 + 0.36, w - 0.60, desc, 12.5, SLATE, ls=1.42)


def before_after(s, x, y0, w, pairs, step=1.40, ch=0.82):
    """以前 / 现在 对照：左灰右绿。y0 = 第一行顶部（和左侧步骤行同一基线）。"""
    cw2 = (w - 0.18) / 2
    dk.text(s, x, y0 - 0.36, cw2, 0.26, [para("以前", 11, MUTE, True)])
    dk.text(s, x + cw2 + 0.18, y0 - 0.36, cw2, 0.26, [para("现在", 11, EMERALD, True)])
    ry = y0
    for before, after in pairs:
        dk.text(s, x, ry, cw2, ch, [para(before, 11.5, MUTE)], line_spacing=1.36,
                anchor=dk.MSO_ANCHOR.MIDDLE)
        dk.box(s, x + cw2 + 0.18, ry, cw2, ch, fill=C((240, 247, 243)),
               line=C((206, 226, 216)), line_w=0.9, round=True, r=0.07)
        dk.text(s, x + cw2 + 0.34, ry, cw2 - 0.32, ch,
                [para(after, 11.5, C((24, 46, 38)), True)], line_spacing=1.36,
                anchor=dk.MSO_ANCHOR.MIDDLE)
        ry += step


s = slide()
y = head(s, "100 份散资料，拖进去就是一座能查的库",
         "应用场景 ① · 知识库的整理与构建")

LW = 5.60
for i, (num, t, d) in enumerate([
    ("1", "传资料", "PDF、Word、PPT、拍照的板书都能直接拖进去。先落盘，不急着读。"),
    ("2", "解析入库", "点一下才开始切：PDF 按页切块、抽出文字，损坏的文件挡在门外。"),
    ("3", "自动归档", "按学科归到库里，每份资料多少字、解析到哪一步，都看得见。"),
]):
    step_row(s, M, y + 0.10 + i * 1.58, LW, num, t, d)

RX = M + LW + 0.63
rx = M + LW + 0.63
rw = CW - LW - 0.63
dk.picture(s, str(ASSETS / "ui-fig-1.png"), rx, y + 0.06, rw, rw / 1.48,
           fit="cover", alt="")
dk.box(s, rx, y + 0.06, rw, rw / 1.48, fill=None, line=C(LINE), line_w=0.9)
dk.text(s, rx, y + 0.06 + rw / 1.48 + 0.14, rw, 0.28,
        [para("库里长这样：每份资料带字数与解析状态。", 12.5, SLATE)])
dk.text(s, rx, y + 0.06 + rw / 1.48 + 0.48, rw, 0.30,
        [[("以前：翻七层找一份。", 12.5, MUTE, False, False, dk.FONT),
          ("现在：搜一句话。", 12.5, EMERALD, True, False, dk.FONT)]], line_spacing=1.30)

# 底部结论条
ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("场景 ①", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("整理一次，往后每次出题、每次复习，都在这座库上跑。", 11, C((38, 52, 46)), True)])
foot(s, 5)

# ================================================================ 06 场景二：自动出题与复习

s = slide()
y = head(s, "题不用自己找：按你的讲义出，按你的错因加重",
         "应用场景 ② · 自动出题与复习安排")

LW = 5.60
for i, (num, t, d) in enumerate([
    ("1", "出题", "从你的库里检索片段，按难度分基础、进阶、迁移三档。"),
    ("2", "记错因", "答错就选一个错因：概念混淆、步骤遗漏、条件误读。"),
    ("3", "出变式", "同一个考点换个条件再出一遍，做对为止。"),
    ("4", "排复习", "掌握度 0–100，间隔 0 / 1 / 3 / 7 天，今天练哪几道系统定。"),
]):
    step_row(s, M, y + 0.10 + i * 1.10, LW, num, t, d)

RX = M + LW + 0.63
rx = M + LW + 0.63
rw = CW - LW - 0.63
dk.picture(s, str(ASSETS / "ui-fig-3.png"), rx, y + 0.06, rw, rw / 1.48,
           fit="cover", alt="")
dk.box(s, rx, y + 0.06, rw, rw / 1.48, fill=None, line=C(LINE), line_w=0.9)
dk.text(s, rx, y + 0.06 + rw / 1.48 + 0.14, rw, 0.28,
        [para("练习页长这样：错因、自评、掌握度都在一页。", 12.5, SLATE)])
dk.text(s, rx, y + 0.06 + rw / 1.48 + 0.48, rw, 0.30,
        [[("以前：错题抄本子上。", 12.5, MUTE, False, False, dk.FONT),
          ("现在：掌握度降一档，明天找上门。", 12.5, EMERALD, True, False, dk.FONT)]], line_spacing=1.30)

# 底部结论条
ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("场景 ②", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("出题不看运气：你错在哪，下次就多练哪。", 11, C((38, 52, 46)), True)])
foot(s, 6)

# ================================================================ 章节 02：凭什么做到

s = slide()
divider(s, "02", "这一章：凭什么做到",
        "这些能力不是提示词堆出来的，是系统工程",
        "检索、权限、测试三条线，让「它会自动做」变成「你敢让它做」。",
        ["真实界面", "四路检索", "一回合", "工具与 MCP", "记忆", "动手管控", "284 项测试"], 7, "08 — 14")

# ================================================================ 08 真实界面

s = slide()
y = head(s, "所见即所得：这不是设计稿，是跑起来的界面",
         "界面 · 三张实机截图")

figs = [
    ("①", "assets/ui-fig-1.png", "资料按学科归好，每份文档带字数与解析状态；\n点开就能读原文。"),
    ("②", "assets/ui-fig-2.png", "今日该复习哪几道已经排好，\n答完直接进下一题。"),
    ("③", "assets/ui-fig-3.png", "答完自评一次，掌握度当场变化；\n下次出题按它加重。"),
]
PW, PH, GAP = 3.70, 2.50, 0.33
px = M
for num, img, cap in figs:
    dk.box(s, px, y + 0.16, 0.34, 0.30, fill=NAVY, round=True, r=0.05)
    dk.text(s, px, y + 0.205, 0.34, 0.22, [para(num, 10.5, C((255, 255, 255)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.picture(s, str(ASSETS / img.split("/")[-1]), px, y + 0.56, PW, PH,
               fit="cover", alt="")
    dk.box(s, px, y + 0.56, PW, PH, fill=None, line=C((196, 206, 218)), line_w=0.9)
    dk.text(s, px, y + 3.16, PW, 0.62, [para(cap, 12, SLATE)], line_spacing=1.40)
    px += PW + GAP

dk.text(s, M, y + 3.94, CW, 0.24,
        [para("来源：知迹 v0.9 实机截图（2026-10-22），未用任何设计稿替换。", 10.5, MUTE)])

ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("界面", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("界面上的每一个按钮，背后都有真实的后端 API 和状态机在支撑。", 11, C((38, 52, 46)), True)])
foot(s, 8)

# ================================================================ 05 亮点一：治幻觉

s = slide()
y = head(s, "不迷信黑盒：四路混合检索，答案只从你的库里来",
         "工程 ① · 它凭什么「懂你的课」")

# 左：四路
dk.text(s, M, y + 0.04, 5.4, 0.28, [para("四路并行召回：中文资料没有单一找法", 15, INK, True)])
routes = [
    ("原查询 FTS", "字面 trigram 匹配", "1.0", NAVY),
    ("同义 / 中英扩写", "换个说法也能找到", "0.5", EMERALD),
    ("两字词 LIKE", "短词专门兜底", "0.8", GOLD),
    ("向量语义", "零字面重叠也能召回", "1.0", SLATE),
]
ry = y + 0.42
for name, note, w, c in routes:
    dk.box(s, M, ry, 5.30, 0.62, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, M, ry, 0.05, 0.62, fill=c)
    dk.text(s, M + 0.24, ry + 0.10, 2.5, 0.24, [para(name, 13.5, INK, True)])
    dk.text(s, M + 0.24, ry + 0.34, 2.7, 0.22, [para(note, 11, MUTE)])
    # 权重条
    bw = 1.30 * float(w)
    dk.box(s, M + 3.15, ry + 0.26, 1.30, 0.11, fill=C((238, 242, 246)), round=True, r=0.03)
    dk.box(s, M + 3.15, ry + 0.26, bw, 0.11, fill=c, round=True, r=0.03)
    dk.text(s, M + 4.52, ry + 0.20, 0.7, 0.24, [para(w, 12, c, True)])
    ry += 0.72

dk.box(s, M, ry + 0.04, 5.30, 0.72, fill=C((238, 245, 242)), round=True, r=0.07)
dk.text(s, M + 0.22, ry + 0.16, 4.9, 0.26,
        [para("加权 RRF 融合（k=60）→ 词面精排 → top-k 片段", 13, EMERALD, True)])
dk.text(s, M + 0.22, ry + 0.44, 4.9, 0.24,
        [para("扩写路是推断出来的，权重就该低于字面命中", 11, SLATE)])
dk.text(s, M, ry + 0.92, 5.30, 0.44,
        [para("纯向量检索对专业术语容易「懂个大概」，四路互补才够准。",
              11, MUTE)], line_spacing=1.40)

# 右：出处 + 数据
rx = M + 5.72
rw = CW - 5.72
dk.text(s, rx, y + 0.04, rw, 0.28, [para("切到页：每道题都说得清从哪一段来", 15, INK, True)])
dk.box(s, rx, y + 0.42, rw, 1.72, fill=C((250, 251, 252)), line=LINE, line_w=0.9, round=True, r=0.07)
for i, (pg, seg) in enumerate([("P12", "片段 1"), ("P12", "片段 2"), ("P07", "片段 3")]):
    bx = rx + 0.24 + i * 1.44
    dk.box(s, bx, y + 0.62, 0.62, 0.30, fill=NAVY, round=True, r=0.04)
    dk.text(s, bx, y + 0.665, 0.62, 0.22, [para(pg, 10, C((255, 255, 255)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.box(s, bx, y + 0.98, 1.30, 0.94, fill=BG, line=LINE, line_w=0.9, round=True, r=0.05)
    dk.text(s, bx, y + 1.12, 1.30, 0.24, [para(seg, 11, INK, True)], align=dk.PP_ALIGN.CENTER)
    dk.text(s, bx, y + 1.38, 1.30, 0.24, [para("可跳回原页", 9.5, MUTE)], align=dk.PP_ALIGN.CENTER)
dk.text(s, rx + 0.24, y + 2.26, rw - 0.48, 0.24,
        [para("整篇不切，题就只能笼统地「来自这份资料」；切到页，才知道考的是哪一段", 10.5, MUTE)])

dk.kpi_card(s, rx, y + 2.52, rw, 1.52, "检索考卷（35 题 / 21 篇语料）", "0.9714",
            sub="Hit@3 = MRR　·　接真实向量 35 题全中",
            accent=EMERALD, ink=C((10, 148, 117)), mute=SLATE, value_size=48, label_size=11)
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("工程 ① · 检索", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("答案先在你的资料里找；资料里没有的，才联网并标明来源。", 11, C((38, 52, 46)), True)])
foot(s, 9)

# ================================================================ 10 工程②：一回合怎么跑

s = slide()
y = head(s, "一回合四个节点：判意图、拆步骤、调工具、回填",
         "工程 ② · 一回合怎么跑")

# 状态图
nodes = [("START", C((246, 248, 250)), INK), ("route", NAVY, C((255, 255, 255))),
         ("plan", NAVY, C((255, 255, 255))), ("agent", C((14, 32, 61)), C((255, 255, 255))),
         ("tools", C((14, 32, 61)), C((255, 255, 255))), ("END", C((246, 248, 250)), INK)]
nw, nh, gap = 1.42, 0.72, 0.42
nx = M
for i, (label, fill, tc) in enumerate(nodes):
    dk.box(s, nx, y + 0.24, nw, nh, fill=fill, line=NAVY, line_w=1.0, round=True, r=0.07)
    dk.text(s, nx, y + 0.44, nw, 0.30, [para(label, 14, tc, True)], align=dk.PP_ALIGN.CENTER)
    if i < len(nodes) - 1:
        dk.arrow(s, nx + nw + 0.05, y + 0.54, gap - 0.10, 0.14,
                 color=C((130, 145, 165)), direction="right")
    nx += nw + gap
dk.text(s, M, y + 1.08, 5.6, 0.24,
        [para("application/graph.py · build_graph　·　上面这一行就是真的代码", 10.5, MUTE)])

# 回环标注
dk.box(s, M + 0.30, y + 1.38, 3.5, 0.34, fill=C((240, 246, 252)), round=True, r=0.05)
dk.text(s, M + 0.30, y + 1.45, 3.5, 0.24,
        [para("tools → agent　结果回填（最多 6 轮）", 10.5, NAVY, True)], align=dk.PP_ALIGN.CENTER)

# 三个节点各自的职责
phases = [
    ("route · 先判意图", "六类：讲解 / 查资料 / 出题 / 计算 / 看进度 / 闲聊。"
     "15 句标注样本，准确率 1.0。", NAVY),
    ("plan · 再拆步骤", "先拆成可执行的步骤，再决定每步调哪个工具，"
     "不靠临场发挥。", EMERALD),
    ("上下文 · 有预算", "上限 24 条；超了先摘要成 240 字，但最近 14 条永远原样保留。", GOLD),
]
pw = (CW - 0.36) / 3
px = M
for name, desc, c in phases:
    dk.box(s, px, y + 1.94, pw, 1.76, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, px, y + 1.94, pw, 0.05, fill=c)
    dk.text(s, px + 0.24, y + 2.16, pw - 0.48, 0.28, [para(name, 15, c, True)])
    dk.text(s, px + 0.24, y + 2.52, pw - 0.48, 1.00, [para(desc, 12.5, SLATE)],
            line_spacing=1.42)
    px += pw + 0.18

dk.text(s, M, y + 3.86, 8.4, 0.24,
        [para("application/context.py · compact_messages　·　摘要与保留策略就这几行", 10.5, MUTE)])
ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("工程 ② · 框架", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("框架不是黑盒：每个节点都有名字、有位置，也能被单独测。", 11, C((38, 52, 46)), True)])
foot(s, 10)

# ================================================================ 11 工程③：工具与 MCP

s = slide()
y = head(s, "它能动的手一共九件，还能从 MCP 接进来",
         "工程 ③ · 它能动的手")

tools = [
    ("knowledge_search", "查你的资料", NAVY),
    ("mistake_search", "翻你的错题", NAVY),
    ("calculator", "算式子", NAVY),
    ("save_note", "把结论存成笔记", EMERALD),
    ("web_search", "联网查公开网页", GOLD),
    ("fetch_url", "读一个网页正文", GOLD),
    ("write_file", "写工作区文件", CORAL),
    ("read_file", "读工作区文件", CORAL),
    ("list_files", "列工作区文件", CORAL),
]
tw, th = 2.28, 1.02
gx, gy = M, y + 0.30
for i, (name, note, c) in enumerate(tools):
    col, row = i % 3, i // 3
    bx = gx + col * (tw + 0.18)
    by_ = gy + row * (th + 0.18)
    dk.box(s, bx, by_, tw, th, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, bx, by_, 0.05, th, fill=c)
    dk.text(s, bx + 0.20, by_ + 0.16, tw - 0.34, 0.26,
            [[(name, 11, INK, True, False, dk.MONO)]])
    dk.text(s, bx + 0.20, by_ + 0.50, tw - 0.34, 0.26, [para(note, 11, SLATE)])

# 右侧：MCP 桥
mx = M + 3 * (tw + 0.18) + 0.14
mw = CW - (mx - M)
dk.box(s, mx, y + 0.30, mw, 3.10, fill=C((248, 250, 252)), line=LINE, line_w=0.9,
       round=True, r=0.07)
dk.text(s, mx + 0.26, y + 0.50, mw - 0.52, 0.30, [para("MCP 桥：外部工具接进来", 15, INK, True)])
dk.text(s, mx + 0.26, y + 0.86, mw - 0.52, 0.28,
        [para("community server 也能变成它的手", 11, MUTE)])
for i, ln in enumerate([
        "从 inputSchema 自动生成参数模型，不用手写包装",
        "工具名加 mcp_<server>_<tool> 前缀，不跟内置撞",
        "server 起不来不阻塞启动，MCP 是可选增强"]):
    dk.box(s, mx + 0.26, y + 1.28 + i * 0.72, 0.06, 0.06, fill=EMERALD, round=True, r=0.03)
    dk.text(s, mx + 0.44, y + 1.16 + i * 0.72, mw - 0.72, 0.58,
            [para(ln, 11.5, SLATE)], line_spacing=1.36)

dk.text(s, M, y + 4.02, 7.2, 0.24,
        [para("工具表是可枚举的：模型只能从这九个里挑，加工具要改代码，不能自己发明。",
              11, MUTE)])

ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("工程 ③ · 工具", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("资料里没有的才联网，回来标明来源 URL；只放行公网地址。", 11, C((38, 52, 46)), True)])
foot(s, 11)

# ================================================================ 12 工程④：记忆

s = slide()
y = head(s, "记住你错在哪，也记住下次该练什么",
         "工程 ④ · 它记得什么")

layers = [
    ("资料层", "知识库", "每份资料切到页，检索时带着页码一起返回。", NAVY),
    ("学习状态层", "错题 / 错因 / 掌握度 / 排期", "答错一次就落库，下一次出题直接拿它算权重。", EMERALD),
    ("对话层", "上下文摘要 + 长期记忆", "超预算先摘要，最近 14 条原样保留；长期记忆按课程隔离。", GOLD),
]
ly = y + 0.30
for name, sub, desc, c in layers:
    dk.box(s, M, ly, 7.30, 1.24, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, M, ly, 0.06, 1.24, fill=c)
    dk.text(s, M + 0.26, ly + 0.18, 1.5, 0.26, [para(name, 10.5, c, True)])
    dk.text(s, M + 1.70, ly + 0.14, 5.30, 0.30, [para(sub, 15, INK, True)])
    dk.text(s, M + 1.70, ly + 0.56, 5.30, 0.52, [para(desc, 12, SLATE)], line_spacing=1.36)
    ly += 1.38

# 右侧：隔离与确认
mx = M + 7.52
mw = CW - 7.52
dk.box(s, mx, y + 0.30, mw, 3.60, fill=C((248, 250, 252)), line=LINE, line_w=0.9, round=True, r=0.07)
dk.text(s, mx + 0.26, y + 0.50, mw - 0.52, 0.30, [para("两层护栏", 15, INK, True)])
for i, (t, d) in enumerate([
        ("按课程隔离", "记忆挂在 project_id 下，换一门课不会串味"),
        ("写入前确认", "任何写操作都 interrupt() 等你点头，不悄悄改")]):
    dk.text(s, mx + 0.26, y + 0.96 + i * 1.34, mw - 0.52, 0.28, [para(t, 13, EMERALD, True)])
    dk.text(s, mx + 0.26, y + 1.28 + i * 1.34, mw - 0.52, 0.86,
            [para(d, 11.5, SLATE)], line_spacing=1.36)

ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("工程 ④ · 记忆", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("短板也在这：过期、替换、删除三种状态还没做，写在体检报告里。", 11, C((38, 52, 46)), True)])
foot(s, 12)

# ================================================================ 13 工程⑤：动手之前

s = slide()
y = head(s, "会动手，不等于乱动手：权限和写库都由系统说了算",
         "工程 ⑤ · 动手之前，谁说了算")

gates = [
    ("模型提议", "agent 想调某个工具", C((246, 248, 250))),
    ("schema 白名单", "禁用的工具不进提示词", C((238, 245, 242))),
    ("执行层判定", "is_tool_allowed 逐次查，硬发也拦得住", C((240, 246, 252))),
    ("人在环", "写操作 interrupt() 等确认，取消就结束", C((252, 243, 239))),
]
gw = 2.62
gx = M
for i, (name, desc, fill) in enumerate(gates):
    dk.box(s, gx, y + 0.34, gw, 1.80, fill=fill, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.text(s, gx + 0.22, y + 0.52, gw - 0.44, 0.28, [para(f"0{i + 1}", 10.5, MUTE, True)])
    dk.text(s, gx + 0.22, y + 0.82, gw - 0.44, 0.28, [para(name, 14, INK, True)])
    dk.text(s, gx + 0.22, y + 1.18, gw - 0.44, 0.80, [para(desc, 11, SLATE)], line_spacing=1.34)
    if i < len(gates) - 1:
        dk.arrow(s, gx + gw + 0.02, y + 1.16, 0.22, 0.14, color=C((132, 146, 166)), direction="right")
    gx += gw + 0.26
dk.text(s, M, y + 2.26, CW, 0.26,
        [para("→ 只有这四道都过了，工具才真的执行；任何一道拦下，这一回合就地停住。", 11.5, MUTE)])

# 一个真会发生的例子
ey = y + 2.58
dk.box(s, M, ey, CW, 1.06, fill=C((250, 251, 252)), line=LINE, line_w=0.9, round=True, r=0.07)
dk.box(s, M, ey, 0.05, 1.06, fill=CORAL)
dk.text(s, M + 0.28, ey + 0.18, 3.0, 0.26, [para("举个真会发生的例子", 12.5, INK, True)])
dk.text(s, M + 0.28, ey + 0.50, CW - 0.56, 0.46,
        [para("它想覆盖你的一份笔记：write_file 在工具表里，但执行前会 interrupt() 弹给你确认；"
              "你点取消，文件一个字节都不动。", 12, SLATE)], line_spacing=1.36)

insight(s, M, y + 3.80, CW, "所以",
        "「AI 不改你的数据」是承诺，不是请求",
        "写在提示词里模型可以忘，写在 interrupt() 里它跑不掉。这就是可拦截。", EMERALD)

ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("工程 ⑤ · 权限", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("四道闸门全部在代码里，不是提示词里的请求。", 11, C((38, 52, 46)), True)])
foot(s, 13)

# ================================================================ 07 工程稳健性

s = slide()
y = head(s, "284 项测试全绿，是因为每一层都能单独测",
         "工程 ⑥ · 这些结论可复现")

kpis = [
    ("284", "项", "自动测试", "全 Mock，零 API 消耗", NAVY),
    ("0.9714", "", "检索 Hit@3 = MRR", "35 题考卷 · 真实向量 35/35", EMERALD),
    ("1.0", "", "意图识别准确率", "15 句标注样本 · 六类意图", EMERALD),
    ("0", "处", "占位实现", "全仓无占位实现", GOLD),
]
kw = (CW - 0.54) / 4
kx = M
for num, unit, label, sub, c in kpis:
    dk.kpi_card(s, kx, y + 0.06, kw, 1.66, label, num, unit=unit, sub=sub,
                accent=c, ink=INK, mute=SLATE, value_size=38, label_size=11)
    kx += kw + 0.18

# 四层架构
dk.text(s, M, y + 1.94, 5.0, 0.28, [para("四层洋葱：依赖只朝内", 15, INK, True)])
layers = [
    ("interfaces", "FastAPI + SSE · CLI（组合根）", NAVY),
    ("application", "用例编排 · 端口 Protocol · LangGraph 图", EMERALD),
    ("infrastructure", "SQLite · Embedding · LLM · MCP · 文件解析", GOLD),
    ("domain", "纯函数：排期 / 出题 / 检索融合 / 护栏", SLATE),
]
ly = y + 2.16
for name, desc, c in layers:
    dk.box(s, M, ly, 5.5, 0.46, fill=BG, line=LINE, line_w=0.9, round=True, r=0.05)
    dk.box(s, M, ly, 0.05, 0.46, fill=c)
    dk.text(s, M + 0.24, ly + 0.05, 1.9, 0.20, [para(name, 11.5, c, True)])
    dk.text(s, M + 0.24, ly + 0.24, 5.0, 0.18, [para(desc, 10, SLATE)])
    ly += 0.50

# 右边
rx = M + 5.86
rw = CW - 5.86
dk.text(s, rx, y + 1.94, rw, 0.28, [para("为什么这能测", 15, INK, True)])
dk.box(s, rx, y + 2.16, rw, 1.10, fill=C((248, 250, 252)), line=LINE, line_w=0.9, round=True, r=0.07)
dk.text(s, rx + 0.26, y + 2.30, rw - 0.52, 0.26,
        [para("domain 层全是纯函数", 13.5, EMERALD, True)])
dk.text(s, rx + 0.26, y + 2.58, rw - 0.52, 0.62,
        [para("复习排期、四档自评、检索融合、护栏，测它们不用起数据库、"
              "不联网、不花一分钱额度。回归测试跑一次只要十几秒。",
              12, SLATE)], line_spacing=1.34)

# 自绘消融卡（kpi_card 的 sub 文字在组件内后画，会被后来的形状盖住）
dk.box(s, rx, y + 3.34, rw, 0.72, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
dk.box(s, rx, y + 3.34, 0.05, 0.72, fill=GOLD)
dk.text(s, rx + 0.24, y + 3.42, rw - 0.5, 0.22, [para("消融对照：关掉词面精排", 10.5, INK, True)])
dk.text(s, rx + 0.24, y + 3.66, 1.6, 0.30, [para("0.9571", 20, GOLD, True)])
dk.text(s, rx + 1.90, y + 3.72, rw - 2.1, 0.24,
        [para("0.9714 → 0.9571　当场可见", 10, SLATE)])
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("工程 ⑥ · 证据", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("domain 层不碰 I/O，回归测试跑一次十几秒，零 API 消耗。", 11, C((38, 52, 46)), True)])
foot(s, 14)

# ================================================================ 章节 03：凭什么是它

s = slide()
divider(s, "03", "这一章：凭什么是它",
        "同样的活儿，为什么非它不可",
        "不是比谁功能多，是比谁能把「你的资料、你的错题、你的进度」串在同一条线上。",
        ["三条路摆在一起", "它凭什么赢"], 15, "16 — 17")

# ================================================================ 16 三条路对比

s = slide()
y = head(s, "三条路摆在一起：只有第三条把整条线串起来了",
         "对比 · 通用 AI / 在线题库 / 知迹")

CW3 = [2.52, 2.58, 2.88]
LABELW = 3.26
cx0 = M + LABELW + 0.12
heads = [("通用 AI", SLATE, C((255, 255, 255))),
         ("在线题库 App", SLATE, C((255, 255, 255))),
         ("知迹", C((238, 245, 242)), C((22, 112, 92)))]
for i, (name, fill, ink) in enumerate(heads):
    x = cx0 + sum(CW3[:i]) + i * 0.10
    dk.box(s, x, y + 0.10, CW3[i], 0.44, fill=fill, round=True, r=0.05)
    dk.text(s, x, y + 0.17, CW3[i], 0.28, [para(name, 12.5, ink, True)],
            align=dk.PP_ALIGN.CENTER)

rows = [
    ("懂不懂你的资料", "只懂通用知识，不知道你老师划的重点", "只懂它自己的题库", "只从你的库里找，切到页"),
    ("会不会替你出题", "你问一句它答一句", "固定题库，跟你的讲义对不上", "按你的讲义出，分三档难度"),
    ("记不记得错因", "聊完就散", "只记对错，不记为什么错", "记错因，下次按它加重"),
    ("会不会排复习", "不管", "有错题本，何时看全凭你", "掌握度 + 间隔 0/1/3/7 天"),
    ("改数据谁说了算", "没有这个概念", "不碰你的文件", "四道闸门 + 写前确认"),
    ("结论能不能复现", "换个时间问，答案就变了", "题库固定，过程不可见", "284 项测试 + 35 题考卷"),
]
ry = y + 0.66
for label, a, b, c in rows:
    dk.box(s, M, ry, CW, 0.60, fill=BG, line=LINE, line_w=0.9, round=True, r=0.05)
    dk.box(s, M, ry, 0.05, 0.60, fill=C((224, 231, 240)))
    dk.text(s, M + 0.24, ry + 0.16, LABELW - 0.30, 0.28, [para(label, 12, INK, True)])
    for i, txt in enumerate((a, b)):
        x = cx0 + sum(CW3[:i]) + i * 0.10
        dk.text(s, x + 0.12, ry + 0.10, CW3[i] - 0.24, 0.42, [para(txt, 10.5, MUTE)],
                line_spacing=1.22)
    x = cx0 + sum(CW3[:2]) + 0.20
    dk.text(s, x + 0.12, ry + 0.10, CW3[2] - 0.24, 0.42, [para(c, 10.5, C((22, 112, 92)), True)],
            line_spacing=1.22)
    ry += 0.66

ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("对比", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("前两条路各自都成立，但它们的手里没有「你的那一份」。", 11, C((38, 52, 46)), True)])
foot(s, 16)

# ================================================================ 17 凭什么赢

s = slide()
y = head(s, "单看每一项都不稀奇，稀奇的是它们共用同一份底账",
         "壁垒 · 三件事串在一条线上")

wins = [
    ("同一份资料", "题从库里出", "出题时检索的是你上传的那几页，不是互联网。", NAVY),
    ("同一份错题", "复习按错题排", "答错就记错因、降掌握度，下一次出题立刻按它加重。", EMERALD),
    ("同一份进度", "越用越像你的私教", "资料越全、错题越多，掌握度曲线越准，排期越贴合你。", GOLD),
]
wy = y + 0.14
for name, sub, desc, c in wins:
    dk.box(s, M, wy, CW, 1.08, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, M, wy, 0.06, 1.08, fill=c)
    dk.text(s, M + 0.28, wy + 0.14, 2.6, 0.26, [para(name, 10.5, c, True)])
    dk.text(s, M + 0.28, wy + 0.44, 3.4, 0.30, [para(sub, 15, INK, True)])
    dk.text(s, M + 4.10, wy + 0.28, CW - 4.40, 0.52, [para(desc, 12, SLATE)], line_spacing=1.36)
    wy += 1.22

dk.box(s, M, wy + 0.02, CW, 0.84, fill=C((238, 245, 242)), line=C((206, 226, 216)),
       line_w=0.9, round=True, r=0.07)
dk.text(s, M + 0.30, wy + 0.16, 3.0, 0.24, [para("所以", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 0.30, wy + 0.40, CW - 0.60, 0.34,
        [para("别人给你的是「一次回答」，它给的是「一条会自己变准的线」。", 15, INK, True)])

ib = 6.60
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.9, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.58, 0.20, [para("壁垒", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22,
        [para("这三件事单独做都不难，难的是它们读的是同一份数据。", 11, C((38, 52, 46)), True)])
foot(s, 17)

# ================================================================ 18 结尾

s = slide()
dk.box(s, 0, 0, W, H, fill=C((14, 32, 61)))
dk.box(s, 0, 0, W, 0.06, fill=C((30, 120, 104)))

WHITE = C((255, 255, 255))
MINT = C((122, 226, 198))
SOFT = C((176, 198, 224))

dk.text(s, M + 0.14, 1.62, 8.0, 0.28, [para("谢谢聆听", 12, MINT, True)])
dk.text(s, M + 0.14, 2.02, 6.4, 1.30, [para("知迹", 60, WHITE, True)])
dk.box(s, M + 0.14, 3.42, 1.50, 0.032, fill=C((30, 110, 100)))
dk.box(s, M + 1.64, 3.42, 0.90, 0.032, fill=MINT)
dk.text(s, M + 0.14, 3.66, 7.6, 0.46,
        [para("会整理、会出题的学习 Agent", 24, MINT, True)])
dk.text(s, M + 0.14, 4.36, 8.2, 0.30,
        [para("284 项测试全绿　·　35 题检索 MRR 0.9714　·　六项能力自评在上一页", 12, SOFT)])

dk.text(s, M + 0.14, 5.62, 8.6, 0.30,
        [para("源码、评测集、体检报告都在这台机器上，欢迎当场抽查。", 12, C((150, 176, 206)))])

# 与左侧那行同一基线，字号收小，不抢标题
dk.text(s, W - M - 3.2, 5.62, 3.2, 0.30,
        [para("欢迎追问", 14, WHITE, True)], align=dk.PP_ALIGN.RIGHT)
dfoot(s, 18)

# ================================================================ 保存

# 清掉母版与版式里的 dt / ftr / sldNum 占位符：
# 有些渲染器（含预览器）会把它们画出来，正好压在我们自己的页脚上。
_DROP = {_PH.DATE, _PH.FOOTER, _PH.SLIDE_NUMBER}
for _layout in prs.slide_layouts:
    for _sh in list(_layout.shapes):
        try:
            if _sh.is_placeholder and _sh.placeholder_format.type in _DROP:
                _sh._element.getparent().remove(_sh._element)
        except (AttributeError, ValueError):
            pass
for _sh in list(prs.slide_master.shapes):
    try:
        if _sh.is_placeholder and _sh.placeholder_format.type in _DROP:
            _sh._element.getparent().remove(_sh._element)
    except (AttributeError, ValueError):
        pass

OUT.mkdir(parents=True, exist_ok=True)
prs.save(str(PPTX))
print(f"✓ {PPTX}  ({PPTX.stat().st_size/1024:.0f} KB)")
print("  预设 consulting · 渐变顶线 · 行动结论式标题 · 语义五色")
print(f"  页面 {len(prs.slides.__iter__.__self__._sldIdLst)}")
