#!/usr/bin/env python3
"""知迹答辩 PPT · slides_maker 构建脚本

风格：`consulting` 预设（白底 · 行动结论式标题 · 藏蓝→翠绿渐变顶线 · 5 色语义契约）
叙事：痛点故事 → 产品定位 → 流程 → 两个硬核亮点 → 工程数据 → 边界 → Roadmap

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

W, H = 13.333, 7.5          # 英寸（16:9）
M = 0.62                    # 左右安全边距
CW = W - 2 * M               # 内容宽

prs = dk.Presentation()
prs.slide_width = dk.Inches(W)
prs.slide_height = dk.Inches(H)
dk.set_ground(BG)


def slide():
    return dk.add_slide(prs)


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


def foot(s, n, total=10, note=""):
    """页脚：细分隔线 + 左侧标签 + 右侧页码。"""
    dk.hrule(s, M, H - 0.46, CW, color=LINE, weight=0.012)
    dk.text(s, M, H - 0.38, CW * 0.6, 0.22,
            [para(note or "知迹 · 赛道十三 · 智慧教育", 9, MUTE)])
    dk.text(s, W - M - 1.2, H - 0.38, 1.2, 0.22,
            [[(f"{n:02d}", 10, NAVY, True, False, dk.FONT),
              (f" / {total}", 9, MUTE, False, False, dk.FONT)]],
            align=dk.PP_ALIGN.RIGHT)


def insight(s, x, y, w, label, hero, txt, accent=NAVY):
    """结论条：左侧竖条 + 一句 so-what。"""
    h = 0.72
    dk.box(s, x, y, w, h, fill=LIGHT, round=True, r=0.06)
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
           round=True, r=0.08)
    dk.text(s, x, y + h / 2 - 0.30, w, 0.30, [para(tag, 13, C((120, 132, 148)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.text(s, x + 0.3, y + h / 2 + 0.02, w - 0.6, 0.46,
            [[(caption, 11, C((120, 132, 148)), False, False, dk.FONT)]],
            align=dk.PP_ALIGN.CENTER)


# ================================================================ 01 封面

s = slide()
dk.box(s, 0, 0, W, H, fill=C((14, 32, 61)))
dk.box(s, 0, 0, W, 0.16, fill=NAVY)
# 右侧氛围图位
figure_slot(s, 7.55, 0.16, W - 7.55, H - 0.16,
            "封面氛围图 · 浅色调书桌场景（待生成，见 assets/配图提示词.md）",
            "p01-cover-desk.png")

dk.text(s, M + 0.12, 1.30, 6.0, 0.26,
        [para("全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育", 12, C((160, 195, 230)), True)])
dk.text(s, M + 0.12, 1.80, 6.2, 1.10, [para("知迹", 62, C((255, 255, 255)), True)])
dk.box(s, M + 0.12, 3.00, 1.50, 0.036, fill=C((30, 110, 100)))
dk.box(s, M + 1.62, 3.00, 0.90, 0.036, fill=EMERALD)
dk.text(s, M + 0.12, 3.28, 6.0, 1.30,
        [para("一个不乱编的个人学习 Agent", 30, C((255, 255, 255)), True)], line_spacing=1.16)
dk.text(s, M + 0.12, 4.14, 6.0, 0.90,
        [[("资料进去，题出来，复习排好 —— ", 15, C((205, 220, 240)), False, False, dk.FONT),
          ("每句结论都能点回你上传的那一页。", 15, C((150, 205, 182)), True, False, dk.FONT)]],
        line_spacing=1.40)

dk.box(s, M + 0.12, 5.42, 0.045, 0.66, fill=EMERALD)
dk.text(s, M + 0.32, 5.44, 6.0, 0.28,
        [para("LangGraph 状态图 · 四路混合检索 · 人在环写入确认", 12, C((205, 220, 240)), True)])
dk.text(s, M + 0.32, 5.74, 6.0, 0.26,
        [para("284 项自动测试全绿 · 检索 35 题 Hit@3 = MRR = 0.9714", 11, C((165, 185, 212)))])

# ================================================================ 02 痛点与破局

s = slide()
y = head(s, "资料存了一百份，AI 答得行云流水，翻开书才发现它连定理条件都记错了",
         "痛点 · 期末周的一次翻车")

# 左侧：故事（占据上半，左 60%）
story = [
    ("期末周的真实困境",
     "网盘里上百份讲义和历年卷，不知道从哪看起；问 AI 一道高数题，"
     "它答得头头是道 —— 一翻书，它连定理的条件都记错了。"),
    ("更致命的是学习本身是断的",
     "学习该是「输入 → 练习 → 纠错 → 再复习」的连续闭环，"
     "但存资料的不管你错题，讲题的不管你下次还错不错。"),
    ("所以问题不是模型不够聪明",
     "是没有任何工具在管「这次复习到底有没有用」。"
     "答错的代价，要等到下次考试才暴露。"),
]
ty = y + 0.06
for t, d in story:
    dk.box(s, M, ty, 0.05, 1.06, fill=CORAL)
    dk.text(s, M + 0.28, ty, 6.6, 0.30, [para(t, 16, INK, True)])
    body(s, M + 0.28, ty + 0.36, 6.6, d, 13, SLATE, ls=1.48)
    ty += 1.28

# 右侧：三个断点（与左栏同高）
rx = M + 7.10
rw = CW - 7.10
dk.text(s, rx, y + 0.06, rw, 0.28, [para("三个断点，缺一不可", 16, INK, True)])
gaps = [
    ("信息过载", "上百份资料散在各处，没有索引、找不动", GOLD),
    ("AI 幻觉", "答得像真的，但错了你分辨不出", CORAL),
    ("学习断层", "错题记住了，下次照样再错", NAVY),
]
gy = y + 0.48
for name, desc, c in gaps:
    dk.box(s, rx, gy, rw, 0.94, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, rx, gy, 0.05, 0.94, fill=c)
    dk.text(s, rx + 0.26, gy + 0.18, rw - 0.5, 0.28, [para(name, 16, c, True)])
    dk.text(s, rx + 0.26, gy + 0.52, rw - 0.5, 0.32, [para(desc, 12, SLATE)])
    gy += 1.06

# 底部：横贯的破局结论（浅色系 + 缩窄，位置在内容之下，不遮挡上方任何元素）
by = 6.62
dk.box(s, M, by, CW, 0.46, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, by, 0.045, 0.46, fill=C((30, 133, 108)))
dk.text(s, M + 0.24, by + 0.13, 1.0, 0.22, [para("破局点", 10, C((30, 110, 92)), True)])
dk.text(s, M + 1.30, by + 0.10, 5.0, 0.26,
        [para("把三件事接成闭环", 13, C((24, 38, 33)), True)])
dk.text(s, M + 6.40, by + 0.13, CW - 6.6, 0.22,
        [para("不是造一个更大的工具，是让「资料 → 题 → 复习」这条线自己转起来。",
              10.5, C((58, 72, 66)))])
dk.text(s, W - M - 2.9, by + 0.13, 2.6, 0.22,
        [para("知迹只做三件事，做到能核验", 10.5, C((30, 110, 92)), True)])
foot(s, 2)

# ================================================================ 03 产品定位

s = slide()
y = head(s, "知迹只死磕三件事：因为只有把闭环做透，才谈得上「可靠」",
         "定位 · 一个克制的单品")

three = [
    ("整理你的资料", "讲义、课件、笔记、拍照的板书传进来，按学科分好；"
     "PDF 能翻到第几页，图片由多模态模型转成文字。", NAVY, "1"),
    ("盯着你的错题", "错题记上「概念混淆 / 步骤遗漏 / 条件误读」这样的错因，"
     "下次出题时它真的按错因加重。", EMERALD, "2"),
    ("结合你的库出题", "题只从你自己的资料里出，答完自评，"
     "掌握度变了，后面的复习安排跟着变。", GOLD, "3"),
]
cw3 = (CW - 0.44) / 3
cx = M
for title, desc, c, num in three:
    card(s, cx, y + 0.04, cw3, 2.55, title, [], accent=c, num=num)
    body(s, cx + 0.22, y + 0.86, cw3 - 0.44, desc, 12.5, SLATE, ls=1.38)
    cx += cw3 + 0.22

# 为什么不做大而全
by = y + 2.80
dk.box(s, M, by, CW, 1.28, fill=C((248, 250, 252)), line=LINE, line_w=0.9, round=True, r=0.08)
dk.text(s, M + 0.28, by + 0.18, 3.2, 0.28,
        [para("为什么不做成「什么都有」的平台", 15, INK, True)])
body(s, M + 0.28, by + 0.52, CW - 0.56,
     "每一多一个功能，就多一条可能出错的路径 —— 而这个项目要证明的恰恰是「输出可信」。"
     "所以它只做单机、单用户、三个动作，做到底。技术上也不是拼装："
     "权限、恢复、评测这三件事，都是围着「让答案可被核验」设计的。",
     12.5, SLATE, ls=1.38)
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("破局点", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("不是造一个更大的工具，是让「资料 → 题 → 复习」这条线自己转起来。", 11, C((38, 52, 46)), True)])
foot(s, 3)

# ================================================================ 04 核心流程

s = slide()
y = head(s, "一个学生的四周：从传资料到自动排复习，中间每一步都留得下痕迹",
         "流程 · 传资料 → 问问题 → 记错因 → 出变式题 → 排复习")

steps = [
    ("周一", "传讲义", "三份 PDF 和课件照片拖进知迹。\n系统不急着读 —— 先落盘，"
     "等你点「解析入库」，后台才按页切块建索引。", NAVY),
    ("周三", "提个问", "「拉格朗日中值定理的条件是什么？」\n"
     "回答句末贴一个 [P12]，点一下就跳回讲义第 12 页原图。", EMERALD),
    ("周五", "记错因", "答错一道。不只是看答案，\n顺手记下「概念混淆」这个错因。", GOLD),
    ("周日", "排复习", "今日复习自动推基于那道错题的变式题，\n并把明天的日程排好。", CORAL),
]
sw = (CW - 0.66) / 4
sx = M
for i, (d, t, desc, c) in enumerate(steps):
    if i:
        dk.arrow(s, sx - 0.20, y + 0.52, 0.14, 0.14, color=C((150, 162, 178)), direction="right")
    dk.box(s, sx, y + 0.10, sw, 2.36, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, sx, y + 0.10, sw, 0.05, fill=c)
    dk.text(s, sx + 0.20, y + 0.30, sw - 0.4, 0.24, [para(d, 11, c, True)])
    dk.text(s, sx + 0.20, y + 0.56, sw - 0.4, 0.30, [para(t, 16, INK, True)])
    dk.text(s, sx + 0.20, y + 0.96, sw - 0.4, 1.30,
            [[(ln, 12, SLATE, False, False, dk.FONT)] for ln in desc.split("\n")],
            line_spacing=1.36)
    sx += sw + 0.22

# 真实界面
iy = y + 2.52
dk.text(s, M, iy, 4.0, 0.26, [para("真实运行界面", 14, INK, True)])
dk.picture(s, str(ASSETS / "ui-knowledge.png"), M, iy + 0.30, 4.40, 1.86, fit="contain")
dk.picture(s, str(ASSETS / "ui-practice.png"), M + 4.56, iy + 0.30, 4.40, 1.86, fit="contain")
dk.text(s, M + 9.20, iy + 0.34, CW - 9.20, 1.76,
        [para("没有华丽的图表，只有极度确定的闭环："
              "每一步都知道自己依据什么、结果存在哪、下次还练不练。",
              13, INK, True)], line_spacing=1.40)
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("定位", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("每一个功能都要回答同一个问题：它让答案更可信了吗？", 11, C((38, 52, 46)), True)])
foot(s, 4)

# ================================================================ 05 亮点一：治幻觉

s = slide()
y = head(s, "它不乱编的底气：四路同时去找，答案里的每一句都能点回原页",
         "硬核亮点 ① · 治幻觉")

# 左：四路
dk.text(s, M, y + 0.04, 5.4, 0.28, [para("四路并行召回 —— 因为中文资料没有单一找法", 15, INK, True)])
routes = [
    ("原查询 FTS", "字面 trigram 匹配", "1.0", NAVY),
    ("同义 / 中英扩写", "换个说法也能找到", "0.5", EMERALD),
    ("两字词 LIKE", "短词专门兜底", "0.8", GOLD),
    ("向量语义", "零字面重叠也能召回", "1.0", SLATE),
]
ry = y + 0.42
for name, note, w, c in routes:
    dk.box(s, M, ry, 5.30, 0.62, fill=BG, line=LINE, line_w=0.9, round=True, r=0.06)
    dk.box(s, M, ry, 0.05, 0.62, fill=c)
    dk.text(s, M + 0.24, ry + 0.10, 2.5, 0.24, [para(name, 13.5, INK, True)])
    dk.text(s, M + 0.24, ry + 0.34, 2.7, 0.22, [para(note, 11, MUTE)])
    # 权重条
    bw = 1.30 * float(w)
    dk.box(s, M + 3.15, ry + 0.26, 1.30, 0.11, fill=C((238, 242, 246)), round=True, r=0.03)
    dk.box(s, M + 3.15, ry + 0.26, bw, 0.11, fill=c, round=True, r=0.03)
    dk.text(s, M + 4.52, ry + 0.20, 0.7, 0.24, [para(w, 12, c, True)])
    ry += 0.72

dk.box(s, M, ry + 0.04, 5.30, 0.72, fill=C((238, 245, 242)), round=True, r=0.06)
dk.text(s, M + 0.22, ry + 0.16, 4.9, 0.26,
        [para("加权 RRF 融合（k=60）→ 词面精排 → top-k 片段", 13, EMERALD, True)])
dk.text(s, M + 0.22, ry + 0.44, 4.9, 0.24,
        [para("扩写路是推断出来的，权重就该低于字面命中", 11, SLATE)])

# 右：出处 + 数据
rx = M + 5.72
rw = CW - 5.72
dk.text(s, rx, y + 0.04, rw, 0.28, [para("每条片段都带着自己的页码", 15, INK, True)])
dk.box(s, rx, y + 0.42, rw, 1.72, fill=C((250, 251, 252)), line=LINE, line_w=0.9, round=True, r=0.08)
for i, (pg, seg) in enumerate([("P12", "片段 1"), ("P12", "片段 2"), ("P07", "片段 3")]):
    bx = rx + 0.24 + i * 1.44
    dk.box(s, bx, y + 0.62, 0.62, 0.30, fill=NAVY, round=True, r=0.04)
    dk.text(s, bx, y + 0.665, 0.62, 0.22, [para(pg, 10, C((255, 255, 255)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.box(s, bx, y + 0.98, 1.30, 0.94, fill=BG, line=LINE, line_w=0.9, round=True, r=0.05)
    dk.text(s, bx, y + 1.12, 1.30, 0.24, [para(seg, 11, INK, True)], align=dk.PP_ALIGN.CENTER)
    dk.text(s, bx, y + 1.38, 1.30, 0.24, [para("可跳回原页", 9.5, MUTE)], align=dk.PP_ALIGN.CENTER)
dk.text(s, rx + 0.24, y + 2.26, rw - 0.48, 0.24,
        [para("整篇 PDF 切成一个片段，引用就只能指向「整篇」—— 答案对不对就无从核验", 10.5, MUTE)])

dk.kpi_card(s, rx, y + 2.52, rw, 1.30, "检索考卷（35 题 / 21 篇语料）", "0.9714",
            sub="Hit@3 = MRR　·　接真实向量 35 题全中",
            accent=EMERALD, ink=INK, mute=SLATE, value_size=32, label_size=11)
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("流程", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("用户只管传资料和做题，排期、难度、复习都自动接上。", 11, C((38, 52, 46)), True)])
foot(s, 5)

# ================================================================ 06 亮点二：Agent 架构

s = slide()
y = head(s, "它是个 Agent，不是套壳：一次提问要走完四节点，写库之前必须等你点头",
         "硬核亮点 ② · 真 Agent 架构")

# 状态图
nodes = [("START", C((246, 248, 250)), INK), ("route", NAVY, C((255, 255, 255))),
         ("plan", NAVY, C((255, 255, 255))), ("agent", C((14, 32, 61)), C((255, 255, 255))),
         ("tools", C((14, 32, 61)), C((255, 255, 255))), ("END", C((246, 248, 250)), INK)]
nw, nh, gap = 1.42, 0.72, 0.42
nx = M
for i, (label, fill, tc) in enumerate(nodes):
    dk.box(s, nx, y + 0.30, nw, nh, fill=fill, line=NAVY, line_w=1.0, round=True, r=0.07)
    dk.text(s, nx, y + 0.50, nw, 0.30, [para(label, 14, tc, True)], align=dk.PP_ALIGN.CENTER)
    if i < len(nodes) - 1:
        dk.arrow(s, nx + nw + 0.05, y + 0.60, gap - 0.10, 0.14,
                 color=C((130, 145, 165)), direction="right")
    nx += nw + gap
dk.text(s, M, y + 1.14, 5.0, 0.24,
        [para("application/graph.py · build_graph　——　上面这一行就是真的代码", 10.5, MUTE)])

# 回环标注
dk.box(s, M + 0.30, y + 1.44, 3.5, 0.34, fill=C((240, 246, 252)), round=True, r=0.05)
dk.text(s, M + 0.30, y + 1.51, 3.5, 0.24,
        [para("tools → agent　结果回填（最多 6 轮）", 10.5, NAVY, True)], align=dk.PP_ALIGN.CENTER)

# 三道管控
ty = y + 1.94
guards = [
    ("schema 层", "按角色裁剪工具表，禁用的工具不出现在提示词里", NAVY),
    ("执行层", "is_tool_allowed 逐次判定，模型硬发被禁工具也执行不了", EMERALD),
    ("人在环", "写操作 interrupt() 等确认，点取消就到此结束", CORAL),
]
gw = (CW - 0.36) / 3
gx = M
for name, desc, c in guards:
    dk.box(s, gx, ty, gw, 1.16, fill=BG, line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, gx, ty, gw, 0.05, fill=c)
    dk.text(s, gx + 0.22, ty + 0.20, gw - 0.44, 0.28, [para(name, 15, c, True)])
    dk.text(s, gx + 0.22, ty + 0.52, gw - 0.44, 0.52, [para(desc, 12, SLATE)], line_spacing=1.34)
    gx += gw + 0.18

insight(s, M, ty + 1.34, CW, "所以",
        "「AI 不改你的数据」是承诺，不是请求",
        "写在提示词里模型可以忘，写在 interrupt() 里它跑不掉 —— 这就是可拦截。", EMERALD)
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("亮点 ①", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("四路召回 + 逐页切块 + 引用跳转 —— 这是纯对话模型做不到的。", 11, C((38, 52, 46)), True)])
foot(s, 6)

# ================================================================ 07 工程稳健性

s = slide()
y = head(s, "284 项测试全绿不是因为功能简单，是因为架构让每一层都能单独测",
         "工程稳健性 · 数据说话")

kpis = [
    ("284", "项", "自动测试", "全 Mock，零 API 消耗", NAVY),
    ("0.9714", "", "检索 Hit@3 = MRR", "35 题考卷 · 真实向量 35/35", EMERALD),
    ("1.0", "", "意图识别准确率", "15 句标注样本 · 六类意图", EMERALD),
    ("0", "处", "占位实现", "全仓无 TODO / 空壳", GOLD),
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
dk.box(s, rx, y + 2.16, rw, 1.10, fill=C((248, 250, 252)), line=LINE, line_w=0.9, round=True, r=0.08)
dk.text(s, rx + 0.26, y + 2.30, rw - 0.52, 0.26,
        [para("domain 层全是纯函数", 13.5, EMERALD, True)])
dk.text(s, rx + 0.26, y + 2.58, rw - 0.52, 0.62,
        [para("复习排期、四档自评、检索融合、护栏 —— 测它们不用起数据库、"
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
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("亮点 ②", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("写在提示词里模型可以忘，写在 interrupt() 里它跑不掉。", 11, C((38, 52, 46)), True)])
foot(s, 7)

# ================================================================ 08 边界

s = slide()
y = head(s, "六项能力：两项达标，三项一半，一项没做 —— 说清楚比多做一点更有用",
         "客观认知 · 我的体检报告")

items = [
    ("中断可恢复", "达标", EMERALD, "状态图 + 检查点 + 中断恢复，孤儿线程级联清理"),
    ("检索准确可追溯", "达标", EMERALD, "35 题考卷，真实向量 35/35，引用精确到页"),
    ("工具执行治理", "一半", GOLD, "有双层权限、超时退避、并发与失败转消息；缺参数级约束"),
    ("长上下文管理", "一半", GOLD, "有抽取式摘要与预算控制；缺关键事实外置"),
    ("长期记忆", "一半", GOLD, "按课程隔离、写入前确认；缺过期、替换与删除机制"),
    ("任务级成功率评测", "没做", CORAL, "考卷只测「找到没」，不测「复习有没有用」"),
]
rh = 0.48
ry = y + 0.02
for name, status, c, desc in items:
    dk.box(s, M, ry, CW, rh, fill=BG, line=LINE, line_w=0.8, round=True, r=0.05)
    dk.box(s, M, ry, 0.05, rh, fill=c)
    dk.text(s, M + 0.26, ry + 0.11, 3.0, 0.26, [para(name, 13.5, INK, True)])
    dk.box(s, M + 3.30, ry + 0.09, 0.72, 0.28, fill=c, round=True, r=0.04)
    dk.text(s, M + 3.30, ry + 0.135, 0.72, 0.22, [para(status, 10.5, C((255, 255, 255)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.text(s, M + 4.22, ry + 0.12, CW - 4.44, 0.24, [para(desc, 11.5, SLATE)])
    ry += rh + 0.08

# 三个真缺陷
dk.text(s, M, ry + 0.02, 5.0, 0.24, [para("最该先补的三个", 13.5, CORAL, True)])
defects = [
    ("trace 是事后猜的", "从消息历史反推责任层，没有运行时耗时与 token 归因"),
    ("没有连续失败熔断", "工具持续报错时会烧满 6 轮真实 API 调用"),
    ("记忆没有生命周期", "「准备四级」和「准备考研」会同时注入，模型两件都当真"),
]
dx = M
dw = (CW - 0.36) / 3
for name, desc in defects:
    dk.box(s, dx, ry + 0.30, dw, 0.76, fill=C((253, 246, 245)), line=C((222, 196, 192)),
           line_w=0.9, round=True, r=0.06)
    dk.text(s, dx + 0.20, ry + 0.38, dw - 0.40, 0.22, [para(name, 11.5, CORAL, True)])
    dk.text(s, dx + 0.20, ry + 0.60, dw - 0.40, 0.40, [para(desc, 10, SLATE)], line_spacing=1.24)
    dx += dw + 0.18
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("工程", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("domain 层全是纯函数，回归测试跑一次十几秒，零 API 消耗。", 11, C((38, 52, 46)), True)])
foot(s, 8)

# ================================================================ 09 Roadmap

s = slide()
y = head(s, "接下来三件事：都在现有门禁里能验证，不需要换架构",
         "未来展望 · 有依据的排序")

road = [
    ("任务级成功率评测", "从「找到没」升到「这次复习到底有没有用」",
     "用确定性状态校验，不用 LLM 判分；引入 pass^k 看稳定性 —— "
     "只报 pass@1 会把「偶尔能成」包装成「稳定可用」。", EMERALD),
    ("记忆的过期与删除", "给记忆加状态：有效 / 被替代 / 失效",
     "写入前做冲突检测，注入时按需检索而非全量拼接 —— "
     "直接对上 LongMemEval 指出的「时间推理」短板。", GOLD),
    ("更难的检索考卷", "现在的 35 题已经饱和，测不出差别",
     "加长文档、强干扰项、跨库同名 —— "
     "有难例才谈得上「比昨天更准」。", NAVY),
]
rw2 = (CW - 0.44) / 3
rx2 = M
for i, (t, sub, desc, c) in enumerate(road):
    dk.box(s, rx2, y + 0.10, rw2, 2.90, fill=BG, line=LINE, line_w=0.9, round=True, r=0.08)
    dk.box(s, rx2 + 0.24, y + 0.34, 0.42, 0.42, fill=c, round=True, r=0.06)
    dk.text(s, rx2 + 0.24, y + 0.415, 0.42, 0.24, [para(f"0{i+1}", 13, C((255, 255, 255)), True)],
            align=dk.PP_ALIGN.CENTER)
    dk.text(s, rx2 + 0.24, y + 0.92, rw2 - 0.48, 0.30, [para(t, 15, INK, True)])
    dk.text(s, rx2 + 0.24, y + 1.26, rw2 - 0.48, 0.46, [para(sub, 12, c, True)], line_spacing=1.32)
    dk.text(s, rx2 + 0.24, y + 1.80, rw2 - 0.48, 1.0, [para(desc, 11.5, SLATE)], line_spacing=1.38)
    rx2 += rw2 + 0.22

# 更大的愿景
vy = y + 3.22
dk.box(s, M, vy, CW, 1.16, fill=C((248, 250, 252)), line=LINE, line_w=0.9, round=True, r=0.08)
dk.text(s, M + 0.28, vy + 0.18, 3.6, 0.28, [para("再往后：让它能交付给别人", 15, INK, True)])
body(s, M + 0.28, vy + 0.52, CW - 0.56,
     "多用户隔离（数据层已按 user_id 隔离，缺的是入口鉴权）、Reranker 重排、"
     "OpenTelemetry 全链路追踪。技术选型上，SQLite 是主动选型 —— 单机演示不需要服务端库的并发写优势，"
     "而换库会重创检索层（FTS5 trigram → ngram，四路召回与全部评测基线作废）。"
     "真要多机部署时，会先看 Postgres 的 pg_trgm + pg_vector。",
     12, SLATE, ls=1.36)
# 底部结论条（浅色系 + 缩窄；位置在内容最低点之下，不遮挡上方任何元素）
ib = 6.66
dk.box(s, M, ib, CW, 0.40, fill=C((243, 247, 245)), line=C((206, 222, 216)), line_w=0.8, round=True, r=0.05)
dk.box(s, M, ib, 0.045, 0.40, fill=C((30, 133, 108)))
dk.text(s, M + 0.22, ib + 0.105, 1.7, 0.20, [para("边界", 9.5, C((30, 110, 92)), True)])
dk.text(s, M + 1.86, ib + 0.10, CW - 2.1, 0.22, [para("六项能力每一项都有代码依据 —— 说清楚比多做一点更有用。", 11, C((38, 52, 46)), True)])
foot(s, 9)

# ================================================================ 10 团队与致谢

s = slide()
y = head(s, "感谢聆听 · 欢迎追问", "Q & A")

# 三个可能被问到的点 + 备答
qa = [
    ("「我直接用 ChatGPT 不行吗？」",
     "ChatGPT 是一问一答，它没有状态，也不会管你明天记不记得。"
     "知迹是有状态的 Agent 系统：把错题和知识库变成上下文，用 LangGraph 跑流程。"
     "更关键的是，ChatGPT 可能会编造页码，而知迹的每个出处都能精确跳回你上传的第 12 页。"),
    ("「你连登录都没有，是不是没做完？」",
     "您看得很准，这确实是我们当前最大的短板。我们把精力全放在了最难的"
     "「Agent 核心链路与防幻觉检索」上，目前它是单机自用的产品。"
     "体检报告里已把它列为 P0，数据库的 user_id 隔离也做好了，接入多租户是接口层的工作。"),
    ("「这个项目有什么了不起的？」",
     "它不比多数 Demo 功能多，但它的每一个结论都能被复现："
     "284 项测试全绿、检索 35 题考卷 0.9714、关掉精排立刻掉到 0.9571。"
     "我们敢把没做的部分也摆出来 —— 那份体检报告和这份 PPT 一样重要。"),
]
qy = y + 0.02
for q, a in qa:
    dk.box(s, M, qy, CW, 0.98, fill=C((250, 251, 252)), line=LINE, line_w=0.9, round=True, r=0.07)
    dk.box(s, M, qy, 0.05, 0.98, fill=NAVY)
    dk.text(s, M + 0.28, qy + 0.12, CW - 0.56, 0.24, [para(q, 13, INK, True)])
    dk.text(s, M + 0.28, qy + 0.40, CW - 0.56, 0.48, [para(a, 11.5, SLATE)], line_spacing=1.32)
    qy += 1.08

dk.box(s, M, qy + 0.06, CW, 1.12, fill=C((14, 32, 61)), round=True, r=0.08)
dk.text(s, M + 0.34, qy + 0.22, 5.0, 0.38, [para("知迹 ZhiJi", 22, C((255, 255, 255)), True)])
dk.text(s, M + 0.34, qy + 0.64, 6.0, 0.26,
        [para("一个不乱编的个人学习 Agent", 12.5, C((150, 205, 182)), True)])
dk.text(s, W - M - 4.6, qy + 0.26, 4.26, 0.76,
        [[("284 项测试全绿　·　检索 35 题 Hit@3 = MRR = 0.9714", 11.5,
           C((205, 220, 240)), False, False, dk.FONT)],
         [("知迹 · 赛道十三 · 智慧教育　·　欢迎指正", 10.5,
           C((165, 185, 212)), False, False, dk.FONT)]],
        align=dk.PP_ALIGN.RIGHT, line_spacing=1.46)

# ================================================================ 保存

OUT.mkdir(parents=True, exist_ok=True)
prs.save(str(PPTX))
print(f"✓ {PPTX}  ({PPTX.stat().st_size/1024:.0f} KB)")
print("  预设 consulting · 渐变顶线 · 行动结论式标题 · 语义五色")
print(f"  页面 {len(prs.slides.__iter__.__self__._sldIdLst)}")
