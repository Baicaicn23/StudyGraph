# ruff: noqa: E501
"""知迹答辩 · v3（按 editable-research-ppt 规范重做）

规范要点（来自 skills/editable-research-ppt v1.4.0）：
- 1280×720 画布；标题 42px(31.5pt) / 正文 21–25px(15.75–18.75pt) / 辅助 ≥17px(12.75pt) / 页脚 14px(10.5pt)
- 左右边距 32px(0.333in)，内容对齐同一纵线
- 朱红只用于关键差异，不整页撒色
- 不逐页挂 takeaway 横幅；不连续三页同构卡片；章节页只用一份章节数据
- 表格：表头 21px 加粗，数据统一 20px
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".workbuddy/skills/slide-maker/scripts"))

import deckkit as dk
import presets
from pptx.enum.shapes import PP_PLACEHOLDER as _PH
from pptx.enum.text import PP_ALIGN

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/作品集/参赛/知迹答辩-v3"
ASSETS = ROOT / "docs/作品集/参赛/知迹答辩/assets"
PPTX = OUT / "知迹答辩-v3.pptx"

W, H = 13.333, 7.5
M = 32 / 96                      # 32px 边距
CW = W - 2 * M

INK = (15, 23, 42)
GRAY = (91, 102, 117)
MUTED = (138, 148, 161)
BLUE = (29, 78, 216)
RED = (200, 30, 20)
LINE = (220, 226, 233)
FILL = (246, 248, 250)
WHITE = (255, 255, 255)


def C(rgb):
    from pptx.dml.color import RGBColor
    return RGBColor(*rgb)


# 字号（px → pt，画布 96dpi）
T_TITLE = 31.5      # 42px
T_SECTION = 42      # 56px
T_SUB = 19.5        # 26px
T_BODY = 18         # 24px
T_SMALL = 13.5      # 18px
T_FOOT = 10.5       # 14px
T_NUM = 54          # 72px

# ---------------------------------------------------------------- 画布
prs = dk.Presentation()
prs.slide_width = dk.Inches(W)
prs.slide_height = dk.Inches(H)
dk.set_ground(C(WHITE))
presets.apply("consulting")
dk.FONT = "Hiragino Sans GB"
dk.DISPLAY = "Hiragino Sans GB"
dk.MONO = "Menlo"
dk.EAFONT = "Hiragino Sans GB"
dk.EADISPLAY = "Hiragino Sans GB"


def slide():
    return dk.add_slide(prs)


def para(txt, size=T_BODY, color=INK, bold=False, ls=1.0):
    return [(txt, size, C(color), bold, False, dk.FONT, ls)]


def text(s, x, y, w, h, runs, size=T_BODY, color=INK, bold=False, ls=1.35,
         align=None, anchor=None):
    if isinstance(runs, str):
        runs = [(runs, size, C(color), bold, False, dk.FONT)]
    kw = {"line_spacing": ls}
    if align is not None:
        kw["align"] = align
    if anchor is not None:
        kw["anchor"] = anchor
    return dk.text(s, x, y, w, h, [runs], **kw)


def rule(s, x, y, w, color=LINE, weight=0.008):
    dk.box(s, x, y, w, weight, fill=C(color))


def page(kicker, title, n, total=18):
    s = slide()
    text(s, M, 0.40, CW, 0.24, [(kicker, T_SMALL, C(BLUE), True, False, dk.FONT)])
    text(s, M, 0.70, CW, 1.20, [(title, T_TITLE, C(INK), True, False, dk.FONT)],
         ls=1.16)
    # 页脚
    rule(s, M, H - 0.44, CW, LINE, 0.006)
    text(s, M, H - 0.36, 8.0, 0.22,
         [("知迹 · 赛道十三 · 智慧教育", T_FOOT, C(MUTED), False, False, dk.FONT)])
    text(s, W - M - 1.2, H - 0.36, 1.2, 0.22,
         [(f"{n:02d} / {total}", T_FOOT, C(MUTED), False, False, dk.FONT)],
         align=PP_ALIGN.RIGHT)
    return s


def section(s, num, name, headline, lead, n, total=18):
    """章节页：一份章节数据（编号/名称/主问题），不放大导航图。"""
    text(s, M, 1.55, 3.0, 1.5, [(num, 96, C(BLUE), True, False, dk.FONT)], ls=0.9)
    text(s, M, 3.30, 6.0, 0.32, [(name, T_SUB, C(BLUE), True, False, dk.FONT)])
    text(s, M, 3.66, 10.6, 1.55, [(headline, T_SECTION, C(INK), True, False, dk.FONT)], ls=1.10)
    text(s, M, 5.44, 9.2, 0.80, [(lead, T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.45)
    # 三段进度：同一份章节数据
    labels = ["它做什么", "凭什么做到", "凭什么是它"]
    x = M
    for i, lb in enumerate(labels):
        active = int(num) - 1 == i
        text(s, x, 6.42, 2.4, 0.24,
             [(f"0{i + 1}", T_FOOT, C(BLUE if active else MUTED), active, False, dk.FONT)])
        text(s, x + 0.42, 6.42, 2.4, 0.24,
             [(lb, T_FOOT, C(INK if active else MUTED), active, False, dk.FONT)])
        if i < 2:
            rule(s, x + 2.10, 6.52, 0.50, C(LINE), 0.006)
        x += 2.95
    rule(s, M, H - 0.44, CW, LINE, 0.006)
    text(s, M, H - 0.36, 8.0, 0.22,
         [("知迹 · 赛道十三 · 智慧教育", T_FOOT, C(MUTED), False, False, dk.FONT)])
    text(s, W - M - 1.2, H - 0.36, 1.2, 0.22,
         [(f"{n:02d} / {total}", T_FOOT, C(MUTED), False, False, dk.FONT)],
         align=PP_ALIGN.RIGHT)


# ============================================================ 01 封面
s = slide()
PIC_W = 5.60
dk.picture(s, str(ASSETS / "p01-cover-desk.png"), W - PIC_W, 0, PIC_W, H, fit="cover", alt="")
# 图片左缘用一条实线收边，不做渐隐（规范里没有渐隐，简化）
text(s, M, 1.30, 6.6, 0.26,
     [("全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育",
       T_FOOT, C(BLUE), True, False, dk.FONT)])
text(s, M, 1.72, 6.0, 1.45, [("知迹", 90, C(INK), True, False, dk.FONT)], ls=0.95)
rule(s, M, 3.46, 2.30, C(BLUE), 0.028)
text(s, M, 3.76, 6.4, 0.44,
     [("一个", T_SUB, C(INK), True, False, dk.FONT),
      ("会整理、会出题", T_SUB, C(BLUE), True, False, dk.FONT),
      ("的学习 Agent", T_SUB, C(INK), True, False, dk.FONT)])
text(s, M, 4.52, 6.2, 1.10,
     [("喂入资料，自动出题，闭环复习。\n它记得你错在哪，也知道明天让你练什么。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.55)
for i, tag in enumerate(["LangGraph 状态机", "四路混合检索", "284 项自动化测试"]):
    text(s, M + i * 2.05, 6.30, 2.0, 0.26,
         [("— " + tag, T_SMALL, C(MUTED), False, False, dk.FONT)])

# ============================================================ 02 痛点
s = page("痛点", "最聪明的 AI，也做不了你的「专属私教」", 2)
rows = [
    ("周一", "网盘囤了 100 多页独家复习提纲，没索引，等于没存。"),
    ("周三", "问通用 AI 考点，答得顺畅，可用的不是我们教材的定义。"),
    ("周五", "做错核心题，下周同类型再考，没有复习机制，照错不误。"),
]
y = 2.20
for day, txt in rows:
    text(s, M, y, 1.30, 0.30, [(day, T_SMALL, C(RED), True, False, dk.FONT)])
    text(s, M + 1.55, y - 0.06, CW - 1.55, 0.44, [(txt, T_BODY, C(INK), False, False, dk.FONT)])
    rule(s, M, y + 0.78, CW, LINE, 0.006)
    y += 1.18
text(s, M, 5.98, CW, 0.32,
     [("一天下来，全是力气活：资料用不上、题要自己找、错了没人盯。",
       T_BODY, C(GRAY), False, False, dk.FONT)])

# ============================================================ 03 章节 01
s = slide()
section(s, "01", "这一章：它做什么",
        "它能在学习里，替你做多少事？",
        "不是多一个聊天窗口。是把整理资料、出题、盯复习这三件事，从你手里接过去。", 3)

# ============================================================ 04 定位
s = page("定位", "不只是聊天框：它自己整理、自己出题、自己盯", 4)
items = [
    ("私人定制的知识库问答", "讲义传进去，按学科归好；问它，只答你这一份。"),
    ("基于私有库的自动出题机", "不从网上找题，从你的讲义里出，按难度分三档。"),
    ("死咬不放的错题追踪器", "记错因、降掌握度，下次出题按薄弱点加重。"),
]
y = 2.10
for i, (t, d) in enumerate(items):
    text(s, M, y + 0.02, 0.60, 0.32, [(f"0{i + 1}", T_SMALL, C(BLUE), True, False, dk.FONT)])
    text(s, M + 0.66, y - 0.04, 4.6, 0.36, [(t, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, M + 5.40, y + 0.02, CW - 5.40, 0.36, [(d, T_BODY, C(GRAY), False, False, dk.FONT)])
    rule(s, M, y + 0.64, CW, LINE, 0.006)
    y += 0.98
text(s, M, 5.42, CW, 0.90,
     [("为什么不做大而全？因为多一个功能，就多一条出错的路径。\n"
       "所以鉴权、多租户这类外围功能主动不做，把精力压在工具权限、写前确认、自动化评测上。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.55)

# ============================================================ 05 场景①
s = page("应用场景 ①", "100 份散资料，拖进去就是一座能查的库", 5)
steps = [
    ("传", "PDF、Word、PPT、拍照的板书直接拖进去。"),
    ("解析", "按页切块、抽出文字，损坏的文件挡在门外。"),
    ("归档", "按学科归到库里，解析到哪一步都看得见。"),
]
x = M
for i, (t, d) in enumerate(steps):
    text(s, x, 2.10, 3.4, 0.40, [(t, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, x, 2.62, 3.4, 1.10, [(d, T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.45)
    if i < 2:
        text(s, x + 3.55, 2.52, 0.40, 0.40, [("→", T_SUB, C(MUTED), False, False, dk.FONT)])
    x += 4.02
rule(s, M, 4.10, CW, LINE, 0.006)
text(s, M, 4.34, 5.4, 0.30, [("以前", T_SMALL, C(MUTED), True, False, dk.FONT)])
text(s, M + 1.30, 4.32, CW - 1.30, 0.36,
     [("100 份讲义躺在网盘，改名、分文件夹，找一份翻七层。", T_BODY, C(MUTED), False, False, dk.FONT)])
text(s, M, 5.06, 5.4, 0.30, [("现在", T_SMALL, C(BLUE), True, False, dk.FONT)])
text(s, M + 1.30, 5.04, CW - 1.30, 0.36,
     [("拖进去按学科归好，找资料变成搜一句话；片段带着页码，点一下回原页。",
       T_BODY, C(INK), False, False, dk.FONT)])

# ============================================================ 06 场景②
s = page("应用场景 ②", "题不用自己找：按你的讲义出，按你的错因加重", 6)
steps = [
    ("出题", "从你的库里检索片段，分基础、进阶、迁移三档。"),
    ("记错因", "答错就选：概念混淆、步骤遗漏、条件误读。"),
    ("出变式", "同一个考点换个条件再出一遍，做对为止。"),
    ("排复习", "掌握度 0–100，间隔 0 / 1 / 3 / 7 天。"),
]
x = M
for i, (t, d) in enumerate(steps):
    text(s, x, 2.10, 3.0, 0.36, [(t, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, x, 2.60, 2.85, 1.30, [(d, T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.45)
    if i < 3:
        text(s, x + 2.92, 2.50, 0.36, 0.36, [("→", T_SUB, C(MUTED), False, False, dk.FONT)])
    x += 3.05
rule(s, M, 4.20, CW, LINE, 0.006)
text(s, M, 4.46, CW, 1.30,
     [("以前：网上的题库跟你手上这本讲义对不上，错题抄在本子上，什么时候看全凭记性。\n"
       "现在：题从你的讲义里出，答案就在那一页；掌握度降一档，明天它就找上门。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.55)

# ============================================================ 07 章节 02
s = slide()
section(s, "02", "这一章：凭什么做到",
        "这些能力不是提示词堆出来的",
        "检索、工具、记忆、权限、测试五条线，让「它会自动做」变成「你敢让它做」。", 7)

# ============================================================ 08 界面
s = page("界面", "所见即所得：这不是设计稿，是跑起来的界面", 8)
PW, PH = 5.95, 3.60
x1 = M
x2 = M + PW + 0.55
dk.picture(s, str(ASSETS / "ui-crop-knowledge.png"), x1, 2.02, PW, PH, fit="cover", alt="")
dk.picture(s, str(ASSETS / "ui-crop-practice.png"), x2, 2.02, PW, PH, fit="cover", alt="")
dk.box(s, x1, 2.02, PW, PH, fill=None, line=C(LINE), line_w=0.75)
dk.box(s, x2, 2.02, PW, PH, fill=None, line=C(LINE), line_w=0.75)
text(s, x1, 5.76, PW, 0.30, [("知识库页：按学科归好，每份文档解析到哪一步都看得见。",
                              T_SMALL, C(GRAY), False, False, dk.FONT)])
text(s, x2, 5.76, PW, 0.30, [("练习页：今日该复习哪几道排好了，自评一次掌握度就变。",
                              T_SMALL, C(GRAY), False, False, dk.FONT)])

# ============================================================ 09 检索
s = page("工程 ①", "不迷信黑盒：四路混合检索，答案只从你的库里来", 9)
routes = [
    ("原查询 FTS", "字面 trigram 匹配，术语一个字都不能差", 1.00),
    ("同义 / 中英扩写", "换个说法也能找到，但它是推断出来的", 0.50),
    ("两字词 LIKE", "短词、缩写专门兜底", 0.80),
    ("向量语义", "零字面重叠也能召回", 1.00),
]
y = 2.10
for name, note, wgt in routes:
    text(s, M, y, 3.0, 0.32, [(name, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, M + 3.10, y + 0.03, 4.6, 0.30, [(note, T_SMALL, C(GRAY), False, False, dk.FONT)])
    dk.box(s, M + 7.05, y + 0.11, 1.30, 0.10, fill=C(FILL))
    dk.box(s, M + 7.05, y + 0.11, 1.30 * wgt, 0.10, fill=C(BLUE))
    text(s, M + 8.45, y + 0.02, 0.6, 0.30, [(f"{wgt:.1f}", T_SMALL, C(GRAY), False, False, dk.FONT)])
    rule(s, M, y + 0.62, 8.95, LINE, 0.006)
    y += 0.86
text(s, M, 5.70, 8.9, 0.90,
     [("四路加权 RRF 融合（k=60）→ 词面精排 → top-k 片段。\n"
       "纯向量检索对中文专业术语容易「懂个大概」，四路互补才够准。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.50)
text(s, W - M - 3.4, 2.34, 3.4, 0.32, [("检索考卷 35 题", T_SMALL, C(GRAY), True, False, dk.FONT)])
text(s, W - M - 3.4, 2.72, 3.4, 1.10, [("0.9714", T_NUM, C(BLUE), True, False, dk.FONT)], ls=0.95)
text(s, W - M - 3.4, 3.86, 3.4, 0.60,
     [("Hit@3 = MRR，真实向量 35/35", T_SMALL, C(GRAY), False, False, dk.FONT)], ls=1.35)

# ============================================================ 10 一回合
s = page("工程 ②", "一回合四个节点：判意图、拆步骤、调工具、回填", 10)
nodes = ["START", "route", "plan", "agent", "tools", "END"]
nw, gap = 1.66, 0.40
x = M
for i, nd in enumerate(nodes):
    dk.box(s, x, 2.14, nw, 0.62, fill=C(FILL), line=C(LINE), line_w=0.75)
    text(s, x, 2.31, nw, 0.30, [(nd, T_SMALL, C(INK), True, False, dk.FONT)],
         align=PP_ALIGN.CENTER)
    if i < len(nodes) - 1:
        text(s, x + nw + 0.06, 2.28, 0.30, 0.30, [("→", T_SMALL, C(MUTED), False, False, dk.FONT)])
    x += nw + gap
text(s, M, 2.92, 8.4, 0.28,
     [("tools → agent 结果回填，最多 6 轮；节点名就是 application/graph.py 里的函数名。",
       T_SMALL, C(MUTED), False, False, dk.FONT)])
rows = [
    ("route 判意图", "六类：讲解 / 查资料 / 出题 / 计算 / 看进度 / 闲聊，15 句标注样本准确率 1.0。"),
    ("plan 拆步骤", "先拆成可执行的步骤，再决定每步调哪个工具，不靠模型临场发挥。"),
    ("上下文有预算", "上限 24 条；超了摘要成 240 字，最近 14 条永远原样保留。"),
]
y = 3.60
for t, d in rows:
    text(s, M, y, 3.1, 0.32, [(t, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, M + 3.20, y + 0.02, CW - 3.20, 0.60, [(d, T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.40)
    y += 1.02

# ============================================================ 11 工具
s = page("工程 ③", "它能动的手一共九件，还能从 MCP 接进来", 11)
tools = [
    ("knowledge_search", "查你的资料"), ("mistake_search", "翻你的错题"), ("calculator", "算式子"),
    ("save_note", "把结论存成笔记"), ("web_search", "联网查公开网页"), ("fetch_url", "读网页正文"),
    ("write_file", "写工作区文件"), ("read_file", "读工作区文件"), ("list_files", "列工作区文件"),
]
x0 = M
for i, (name, note) in enumerate(tools):
    col, row = i % 3, i // 3
    x = x0 + col * 3.05
    y = 2.10 + row * 1.12
    text(s, x, y, 3.0, 0.30, [(name, 15, C(INK), True, False, dk.MONO)])
    text(s, x, y + 0.34, 3.0, 0.30, [(note, T_SMALL, C(GRAY), False, False, dk.FONT)])
    rule(s, x, y + 0.76, 2.80, LINE, 0.006)
text(s, M, 5.70, 9.2, 0.34,
     [("工具表是可枚举的：模型只能从这九个里挑，加工具要改代码，不能自己发明。",
       T_SMALL, C(MUTED), False, False, dk.FONT)])
rule(s, M, 6.06, 9.2, LINE, 0.006)
text(s, M, 6.18, 9.2, 0.62,
     [("MCP：外部 server 的工具从 inputSchema 自动生成本地工具，名字加 mcp_<server>_<tool> 前缀；"
       "起不来不阻塞启动。", T_SMALL, C(GRAY), False, False, dk.FONT)], ls=1.35)

# ============================================================ 12 记忆
s = page("工程 ④", "记住你错在哪，也记住下次该练什么", 12)
layers = [
    ("资料层", "知识库", "每份资料切到页，检索时把页码一起带回来。"),
    ("学习状态层", "错题 / 错因 / 掌握度 / 排期", "答错一次就落库，下次出题直接拿它算权重。"),
    ("对话层", "上下文摘要 + 长期记忆", "超预算先摘要；长期记忆挂在课程下，换课不串味。"),
]
y = 2.10
for tag, name, desc in layers:
    text(s, M, y, 1.9, 0.30, [(tag, T_SMALL, C(BLUE), True, False, dk.FONT)])
    text(s, M + 2.05, y - 0.04, 4.3, 0.34, [(name, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, M + 6.50, y, CW - 6.50, 0.60, [(desc, T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.40)
    rule(s, M, y + 0.78, CW, LINE, 0.006)
    y += 1.14
text(s, M, 5.62, CW, 0.90,
     [("写操作一律 interrupt() 等确认——记忆不是只进不出的池子，改它之前先问你一句。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.45)

# ============================================================ 13 权限
s = page("工程 ⑤", "会动手，不等于乱动手：权限和写库都由系统说了算", 13)
gates = [("模型提议", "agent 想调某个工具"),
         ("schema 白名单", "禁用的工具不出现在提示词里"),
         ("执行层判定", "is_tool_allowed 逐次查"),
         ("人在环", "写操作等确认，取消就结束")]
x = M
for i, (t, d) in enumerate(gates):
    text(s, x, 2.16, 0.50, 0.26, [(f"0{i + 1}", T_FOOT, C(BLUE), True, False, dk.FONT)])
    text(s, x, 2.44, 2.55, 0.32, [(t, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, x, 2.84, 2.55, 0.70, [(d, T_SMALL, C(GRAY), False, False, dk.FONT)], ls=1.40)
    if i < 3:
        text(s, x + 2.62, 2.72, 0.32, 0.30, [("→", T_SMALL, C(MUTED), False, False, dk.FONT)])
    x += 3.05
rule(s, M, 3.86, CW, LINE, 0.006)
text(s, M, 4.10, CW, 1.60,
     [("举个真会发生的例子：它想覆盖你的一份笔记 —— write_file 在工具表里，执行前 interrupt() 弹给你确认；\n"
       "你点取消，文件一个字节都不动。写在提示词里模型可以忘，写在 interrupt() 里它跑不掉。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.55)

# ============================================================ 14 数据
s = page("工程 ⑥", "284 项测试全绿，是因为每一层都能单独测", 14)
kpis = [("284", "项", "自动化测试", "全 Mock，零 API 消耗"),
        ("0.9714", "", "检索 Hit@3 = MRR", "35 题考卷，真实向量 35/35"),
        ("1.0", "", "意图识别准确率", "15 句标注样本，六类意图"),
        ("0", "处", "占位实现", "全仓无占位实现")]
x = M
for num, unit, label, sub in kpis:
    text(s, x, 2.14, 3.0, 0.96, [(num, T_NUM, C(INK), True, False, dk.FONT)], ls=0.95)
    if unit:
        text(s, x + 1.55, 2.78, 0.5, 0.26, [(unit, T_SMALL, C(GRAY), False, False, dk.FONT)])
    text(s, x, 3.18, 3.0, 0.28, [(label, T_SMALL, C(INK), True, False, dk.FONT)])
    text(s, x, 3.50, 2.90, 0.56, [(sub, T_SMALL, C(GRAY), False, False, dk.FONT)], ls=1.35)
    x += 3.05
rule(s, M, 4.30, CW, LINE, 0.006)
text(s, M, 4.54, 5.6, 0.30, [("消融对照", T_SMALL, C(RED), True, False, dk.FONT)])
text(s, M, 4.88, CW, 1.10,
     [("关掉词面精排，同一张考卷立刻从 0.9714 掉到 0.9571 —— 精排到底有没有用，不用信我，看数。\n"
       "domain 层全是纯函数：排期、四档自评、检索融合、护栏，测它们不用起数据库、不联网、不花额度。",
       T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.55)

# ============================================================ 15 章节 03
s = slide()
section(s, "03", "这一章：凭什么是它",
        "同样的活儿，为什么非它不可",
        "不是比谁功能多，而是谁能把「资料、错题、进度」串成一条线。", 15)

# ============================================================ 16 对比（真表格）
s = page("对比", "三条路摆在一起：只有第三条把整条线串起来了", 16)
rows = [
    ["", "通用 AI", "在线题库 App", "知迹"],
    ["懂不懂你的资料", "只懂通用知识", "只懂它自己的题库", "只从你的库里找，切到页"],
    ["会不会替你出题", "你问一句它答一句", "固定题库，对不上讲义", "按讲义出，分三档难度"],
    ["记不记得错因", "聊完就散", "只记对错", "记错因，下次按它加重"],
    ["会不会排复习", "不管", "何时看全凭你", "掌握度 + 间隔 0/1/3/7 天"],
    ["改数据谁说了算", "没有这个概念", "不碰你的文件", "四道闸门 + 写前确认"],
    ["结论能不能复现", "换个时间答案就变", "过程不可见", "284 项测试 + 35 题考卷"],
]
dk.table(s, M, 2.02, CW, rows, col_w=[3.35, 2.85, 3.05, 3.40], header=True,
         size=15, row_h=0.62, head_c=C(INK), body_c=C((40, 50, 66)),
         rule_c=C((210, 218, 226)), hi_c=C(RED))
text(s, M, 6.36, CW, 0.32,
     [("前两条路各自都成立，但它们手里没有「你的那一份」。", T_BODY, C(GRAY), False, False, dk.FONT)])

# ============================================================ 17 壁垒
s = page("壁垒", "单看每一项都不稀奇，稀奇的是它们共用同一份底账", 17)
wins = [
    ("同一份资料", "题从库里出", "出题时检索的是你上传的那几页，不是互联网。"),
    ("同一份错题", "复习按错题排", "答错就记错因、降掌握度，下一次出题立刻按它加重。"),
    ("同一份进度", "越用越像你的私教", "资料越全、错题越多，掌握度曲线越准，排期越贴合你。"),
]
y = 2.10
for i, (tag, t, d) in enumerate(wins):
    text(s, M, y + 0.04, 0.60, 0.40, [(f"0{i + 1}", T_SMALL, C(BLUE), True, False, dk.FONT)])
    text(s, M + 0.66, y, 2.6, 0.32, [(tag, T_SMALL, C(MUTED), True, False, dk.FONT)])
    text(s, M + 0.66, y + 0.34, 4.4, 0.36, [(t, T_SUB, C(INK), True, False, dk.FONT)])
    text(s, M + 5.60, y + 0.18, CW - 5.60, 0.60, [(d, T_BODY, C(GRAY), False, False, dk.FONT)], ls=1.40)
    rule(s, M, y + 1.02, CW, LINE, 0.006)
    y += 1.24
text(s, M, 5.94, CW, 0.40,
     [("别人给你的是「一次回答」，它给的是「一条会自己变准的线」。",
       T_SUB, C(INK), True, False, dk.FONT)])

# ============================================================ 18 结尾
s = slide()
text(s, M, 1.90, 6.0, 0.28, [("谢谢聆听 · 欢迎追问", T_SMALL, C(BLUE), True, False, dk.FONT)])
text(s, M, 2.28, 6.0, 1.35, [("知迹", 84, C(INK), True, False, dk.FONT)], ls=0.95)
rule(s, M, 3.86, 2.10, C(BLUE), 0.028)
text(s, M, 4.14, 7.0, 0.40,
     [("会整理、会出题", T_SUB, C(BLUE), True, False, dk.FONT),
      ("的学习 Agent", T_SUB, C(INK), True, False, dk.FONT)])
text(s, M, 4.86, 9.4, 0.30,
     [("284 项测试全绿　·　35 题检索 MRR 0.9714　·　源码与评测集都在这台机器上，欢迎当场抽查。",
       T_SMALL, C(GRAY), False, False, dk.FONT)])
rule(s, M, H - 0.44, CW, LINE, 0.006)
text(s, M, H - 0.36, 8.0, 0.22,
     [("知迹 · 赛道十三 · 智慧教育", T_FOOT, C(MUTED), False, False, dk.FONT)])
text(s, W - M - 1.2, H - 0.36, 1.2, 0.22,
     [("18 / 18", T_FOOT, C(MUTED), False, False, dk.FONT)], align=PP_ALIGN.RIGHT)

# 清掉母版/版式的日期·页脚·页码占位符，避免渲染器把它们画出来压住页脚
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
print(f"✓ {PPTX}  ({PPTX.stat().st_size / 1024:.0f} KB)")
print(f"  页面 {len(prs.slides.__iter__.__self__._sldIdLst)}")
