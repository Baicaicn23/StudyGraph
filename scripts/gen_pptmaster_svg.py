# ruff: noqa: E501
"""知迹答辩 · ppt-master 版（Generate / Quick 路线，自由设计）

产物：projects/zhiji_pm/svg_output/slide_NN.svg
风格：P1 蓝白朱红 · solid 厚实实底（深色标题带 + 白底正文 + 朱红只做关键差异）
"""

from __future__ import annotations

import html
from pathlib import Path

W, H = 1280, 720
MG = 64                      # 左右边距 64px
BAND = 92                    # 标题带高度
INK = "#151B29"
GRAY = "#5B6675"
MUT = "#8A94A1"
PRI = "#173D67"
ACC = "#B82D32"
TINT = "#EEF3F8"
LINE = "#DCE2E9"
WHITE = "#FFFFFF"
FONT = "Noto Sans CJK SC"

OUT = Path(__file__).resolve().parent.parent / "svg_output"


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def txt(x, y, s, size=22, color=INK, weight=400, anchor="start", spacing=0):
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def rect(x, y, w, h, fill, r=0, stroke=None, sw=1, opacity=1):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity != 1 else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{st}{op}/>'


def line(x1, y1, x2, y2, color=LINE, sw=1):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"/>'


def page(kicker, title, body, n):
    """统一页：深色标题带（kicker + 标题），正文自 150px 起，底部页脚。"""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'version="1.1" width="{W}" height="{H}" viewBox="0 0 {W} {H}" lang="zh-CN">',
        rect(0, 0, W, H, WHITE),
        rect(0, 0, W, BAND, PRI),
        txt(MG, 36, kicker, 16, "#A8C0DA", 700, spacing=1),
        txt(MG, 72, title, 34, WHITE, 700),
        txt(W - MG, 40, f"{n:02d} / 18", 14, "#7E96B2", 400, anchor="end"),
        *body,
        line(MG, 676, W - MG, 676, LINE, 1),
        txt(MG, 700, "知迹 · 赛道十三 · 智慧教育", 14, MUT),
        "</svg>",
    ]
    return "\n".join(parts)


def render(name, svg):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------- 01 封面
cover = [
    rect(0, 0, W, H, WHITE),
    rect(0, 0, 760, H, PRI),
    txt(MG, 96, "全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育", 15, "#A8C0DA", 700),
    txt(MG, 250, "知迹", 96, WHITE, 700),
    rect(MG, 288, 160, 6, ACC),
    txt(MG, 360, "一个会整理、会出题的学习 Agent", 34, WHITE, 700),
    txt(MG, 420, "喂入资料，自动出题，闭环复习。", 22, "#C8D6E6"),
    txt(MG, 458, "它记得你错在哪，也知道明天让你练什么。", 22, "#C8D6E6"),
    txt(MG, 600, "LangGraph 状态机　·　四路混合检索　·　284 项自动化测试", 16, "#8FB0CE"),
    rect(760, 0, 520, H, TINT),
    txt(824, 300, "把「资料 → 错题 → 复习」", 28, PRI, 700),
    txt(824, 344, "接成一条线", 28, ACC, 700),
    txt(824, 400, "本页为封面示意，正式版可放实机截图", 15, MUT),
]
render("slide_01.svg", "\n".join([
    f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W}" height="{H}" viewBox="0 0 {W} {H}" lang="zh-CN">',
    *cover, "</svg>"]))

# ---------------------------------------------------------------- 02 痛点
b = [
    txt(MG, 172, "一天下来，全是力气活。", 28, INK, 700),
    txt(MG, 212, "不是 AI 不聪明，是这些活它不干。", 20, GRAY),
]
rows = [
    ("周一", "网盘囤了 100 多页独家复习提纲，没索引，等于没存。"),
    ("周三", "问通用 AI 考点，答得顺畅，可用的不是我们教材的定义。"),
    ("周五", "做错核心题，下周同类型再考，没有复习机制，照错不误。"),
]
y = 270
for d, t in rows:
    b += [txt(MG, y, d, 18, ACC, 700), txt(MG + 96, y, t, 24, INK), line(MG, y + 34, W - MG, y + 34)]
    y += 104
b += [txt(MG, 636, "资料用不上、题要自己找、错了没人盯 —— 这三件事，今天都得你亲手做。", 20, GRAY)]
render("slide_02.svg", page("痛点", "最聪明的 AI，也做不了你的「专属私教」", b, 2))

# ---------------------------------------------------------------- 03 章节 01
s3 = [
    txt(MG, 210, "01", 120, TINT, 700),
    txt(MG, 268, "这一章：它做什么", 20, PRI, 700),
    txt(MG, 340, "它能在学习里，替你做多少事？", 42, INK, 700),
    txt(MG, 400, "不是多一个聊天窗口。是把整理资料、出题、盯复习这三件事，从你手里接过去。", 22, GRAY),
    line(MG, 500, W - MG, 500, LINE),
    txt(MG, 540, "01  它做什么", 18, PRI, 700),
    txt(MG + 200, 540, "02  凭什么做到", 18, MUT),
    txt(MG + 400, 540, "03  凭什么是它", 18, MUT),
]
render("slide_03.svg", "\n".join([
    f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W}" height="{H}" viewBox="0 0 {W} {H}" lang="zh-CN">',
    rect(0, 0, W, H, WHITE), rect(0, 0, 10, H, PRI), *s3,
    line(MG, 676, W - MG, 676, LINE), txt(MG, 700, "知迹 · 赛道十三 · 智慧教育", 14, MUT),
    txt(W - MG, 700, "03 / 18", 14, MUT, anchor="end"), "</svg>"]))

# ---------------------------------------------------------------- 04 定位
b = [txt(MG, 168, "三件事，别的都不做。", 26, INK, 700)]
items = [
    ("01", "私人定制的知识库问答", "讲义传进去，按学科归好；问它，只答你这一份。"),
    ("02", "基于私有库的自动出题机", "不从网上找题，从你的讲义里出，按难度分三档。"),
    ("03", "死咬不放的错题追踪器", "记错因、降掌握度，下次出题按薄弱点加重。"),
]
y = 226
for num, t, d in items:
    b += [txt(MG, y, num, 16, PRI, 700), txt(MG + 56, y, t, 24, INK, 700),
          txt(MG + 56, y + 34, d, 20, GRAY), line(MG, y + 52, W - MG, y + 52)]
    y += 112
b += [rect(MG, 596, W - 2 * MG, 60, TINT, 6),
      txt(MG + 24, 632, "为什么不做大而全？因为多一个功能，就多一条出错的路径。", 20, PRI, 700)]
render("slide_04.svg", page("定位", "不只是聊天框：它自己整理、自己出题、自己盯", b, 4))

# ---------------------------------------------------------------- 05 场景①
b = []
steps = [("传", "PDF、Word、PPT、拍照的板书直接拖进去。"),
         ("解析", "按页切块、抽出文字，损坏的文件挡在门外。"),
         ("归档", "按学科归到库里，解析到哪一步都看得见。")]
x = MG
for t, d in steps:
    b += [rect(x, 180, 8, 74, PRI), txt(x + 26, 210, t, 26, INK, 700),
          txt(x + 26, 244, d, 18, GRAY)]
    x += 400
b += [line(MG, 320, W - MG, 320),
      txt(MG, 372, "以前", 16, MUT, 700),
      txt(MG + 90, 372, "100 份讲义躺在网盘，改名、分文件夹，找一份翻七层。", 22, MUT),
      txt(MG, 442, "现在", 16, PRI, 700),
      txt(MG + 90, 442, "拖进去按学科归好，找资料变成搜一句话；片段带页码，点一下回原页。", 22, INK),
      line(MG, 490, W - MG, 490),
      txt(MG, 548, "整理一次，往后每次出题、每次复习，都在这座库上跑。", 20, GRAY)]
render("slide_05.svg", page("应用场景 ①", "100 份散资料，拖进去就是一座能查的库", b, 5))

# ---------------------------------------------------------------- 06 场景②
b = []
steps = [("出题", "从你的库里检索片段，分基础、进阶、迁移三档。"),
         ("记错因", "答错就选：概念混淆、步骤遗漏、条件误读。"),
         ("出变式", "同一个考点换个条件再出一遍，做对为止。"),
         ("排复习", "掌握度 0–100，间隔 0 / 1 / 3 / 7 天。")]
x = MG
for t, d in steps:
    b += [txt(x, 206, t, 24, INK, 700), txt(x, 240, d, 17, GRAY)]
    x += 300
b += [line(MG, 330, W - MG, 330),
      txt(MG, 386, "以前：网上的题库跟你手上这本讲义对不上，错题抄在本子上，什么时候看全凭记性。", 21, MUT),
      txt(MG, 434, "现在：题从你的讲义里出，答案就在那一页；掌握度降一档，明天它就找上门。", 21, INK),
      line(MG, 486, W - MG, 486),
      txt(MG, 544, "出题不看运气：你错在哪，下次就多练哪。", 20, GRAY)]
render("slide_06.svg", page("应用场景 ②", "题不用自己找：按你的讲义出，按你的错因加重", b, 6))

# ---------------------------------------------------------------- 07 章节 02
s7 = [
    txt(MG, 210, "02", 120, TINT, 700),
    txt(MG, 268, "这一章：凭什么做到", 20, PRI, 700),
    txt(MG, 340, "这些能力不是提示词堆出来的", 42, INK, 700),
    txt(MG, 400, "检索、工具、记忆、权限、测试五条线，让「它会自动做」变成「你敢让它做」。", 22, GRAY),
    line(MG, 500, W - MG, 500),
    txt(MG, 540, "01  它做什么", 18, MUT),
    txt(MG + 200, 540, "02  凭什么做到", 18, PRI, 700),
    txt(MG + 400, 540, "03  凭什么是它", 18, MUT),
]
render("slide_07.svg", "\n".join([
    f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W}" height="{H}" viewBox="0 0 {W} {H}" lang="zh-CN">',
    rect(0, 0, W, H, WHITE), rect(0, 0, 10, H, PRI), *s7,
    line(MG, 676, W - MG, 676, LINE), txt(MG, 700, "知迹 · 赛道十三 · 智慧教育", 14, MUT),
    txt(W - MG, 700, "07 / 18", 14, MUT, anchor="end"), "</svg>"]))

# ---------------------------------------------------------------- 08 界面（三图组）
ASSET = str(Path(__file__).resolve().parent.parent / "docs" / "作品集" / "参赛" / "知迹答辩" / "assets")
b = []
figs = [("①", "ui-fig-1.png", "资料按学科归好，每份文档带字数与解析状态。"),
        ("②", "ui-fig-2.png", "今日该复习哪几道已经排好。"),
        ("③", "ui-fig-3.png", "自评一次，掌握度当场变化。")]
x = MG
for num, img, cap in figs:
    b += [rect(x, 150, 34, 30, PRI, 4), txt(x + 12, 171, num, 15, WHITE, 700),
          f'<image x="{x}" y="{200}" width="368" height="248" preserveAspectRatio="xMidYMid slice" xlink:href="file://{ASSET}/{img}"/>',
          rect(x, 200, 368, 248, "none", 0, LINE, 1),
          txt(x, 476, cap, 16, GRAY)]
    x += 388
b += [txt(MG, 536, "来源：知迹 v0.9 实机截图（2026-10-22），未用任何设计稿替换。", 15, MUT),
      rect(MG, 576, W - 2 * MG, 56, TINT, 6),
      txt(MG + 24, 612, "界面上的每一个按钮，背后都有真实的后端 API 和状态机在支撑。", 20, PRI, 700)]
render("slide_08.svg", page("界面", "所见即所得：这不是设计稿，是跑起来的界面", b, 8))

# ---------------------------------------------------------------- 09 检索
b = [txt(MG, 168, "四路并行召回：中文资料没有单一找法", 24, INK, 700)]
routes = [("原查询 FTS", "字面 trigram 匹配，术语一个字都不能差", 1.0),
          ("同义 / 中英扩写", "换个说法也能找到，但它是推断出来的", 0.5),
          ("两字词 LIKE", "短词、缩写专门兜底", 0.8),
          ("向量语义", "零字面重叠也能召回", 1.0)]
y = 222
for name, note, w in routes:
    b += [txt(MG, y, name, 21, INK, 700), txt(MG + 220, y, note, 17, GRAY),
          rect(MG + 640, y - 14, 200, 10, TINT), rect(MG + 640, y - 14, int(200 * w), 10, PRI),
          txt(MG + 860, y, f"{w:.1f}", 17, GRAY),
          line(MG, y + 26, MG + 900, y + 26)]
    y += 74
b += [txt(MG, 552, "加权 RRF 融合（k=60）→ 词面精排 → top-k 片段", 20, PRI, 700),
      txt(MG, 588, "纯向量检索对中文专业术语容易「懂个大概」，四路互补才够准。", 18, GRAY),
      txt(W - MG - 300, 250, "检索考卷 35 题", 16, GRAY, 700),
      txt(W - MG - 300, 330, "0.9714", 62, PRI, 700),
      txt(W - MG - 300, 368, "Hit@3 = MRR，真实向量 35/35", 15, GRAY)]
render("slide_09.svg", page("工程 ①", "不迷信黑盒：四路混合检索，答案只从你的库里来", b, 9))

# ---------------------------------------------------------------- 10 一回合
b = []
nodes = ["START", "route", "plan", "agent", "tools", "END"]
x = MG
for i, nd in enumerate(nodes):
    b += [rect(x, 180, 168, 62, TINT, 4, LINE, 1), txt(x + 84, 218, nd, 17, INK, 700, anchor="middle")]
    if i < len(nodes) - 1:
        b += [txt(x + 172, 216, "→", 18, MUT)]
    x += 196
b += [txt(MG, 276, "tools → agent 结果回填，最多 6 轮；节点名就是 application/graph.py 里的函数名。", 15, MUT)]
rows = [("route 判意图", "六类：讲解 / 查资料 / 出题 / 计算 / 看进度 / 闲聊，15 句标注样本准确率 1.0。"),
        ("plan 拆步骤", "先拆成可执行的步骤，再决定每步调哪个工具，不靠模型临场发挥。"),
        ("上下文有预算", "上限 24 条；超了摘要成 240 字，最近 14 条永远原样保留。")]
y = 340
for t, d in rows:
    b += [txt(MG, y, t, 21, INK, 700), txt(MG + 200, y, d, 19, GRAY), line(MG, y + 30, W - MG, y + 30)]
    y += 92
render("slide_10.svg", page("工程 ②", "一回合四个节点：判意图、拆步骤、调工具、回填", b, 10))

# ---------------------------------------------------------------- 11 工具
b = [txt(MG, 168, "九个内置工具，一个 MCP 桥", 24, INK, 700)]
tools = [("knowledge_search", "查你的资料"), ("mistake_search", "翻你的错题"), ("calculator", "算式子"),
         ("save_note", "存成笔记"), ("web_search", "联网查公开网页"), ("fetch_url", "读网页正文"),
         ("write_file", "写工作区文件"), ("read_file", "读工作区文件"), ("list_files", "列工作区文件")]
x0 = MG
for i, (name, note) in enumerate(tools):
    col, row = i % 3, i // 3
    x = x0 + col * 400
    y = 220 + row * 96
    b += [txt(x, y, name, 17, INK, 700), txt(x, y + 26, note, 16, GRAY), line(x, y + 44, x + 350, y + 44)]
b += [txt(MG, 540, "工具表是可枚举的：模型只能从这九个里挑，加工具要改代码，不能自己发明。", 16, MUT),
      line(MG, 570, W - MG, 570),
      txt(MG, 606, "MCP：外部 server 的工具从 inputSchema 自动生成本地工具，名字加 mcp_<server>_<tool> 前缀；起不来不阻塞启动。", 16, GRAY)]
render("slide_11.svg", page("工程 ③", "它能动的手一共九件，还能从 MCP 接进来", b, 11))

# ---------------------------------------------------------------- 12 记忆
b = []
layers = [("资料层", "知识库", "每份资料切到页，检索时把页码一起带回来。"),
          ("学习状态层", "错题 / 错因 / 掌握度 / 排期", "答错一次就落库，下次出题直接拿它算权重。"),
          ("对话层", "上下文摘要 + 长期记忆", "超预算先摘要；长期记忆挂在课程下，换课不串味。")]
y = 200
for tag, name, d in layers:
    b += [txt(MG, y, tag, 16, PRI, 700), txt(MG + 150, y, name, 22, INK, 700),
          txt(MG + 150, y + 32, d, 18, GRAY), line(MG, y + 56, W - MG, y + 56)]
    y += 108
b += [rect(MG, 546, W - 2 * MG, 64, TINT, 6),
      txt(MG + 24, 586, "写操作一律 interrupt() 等确认 —— 记忆不是只进不出的池子，改它之前先问你一句。", 19, PRI, 700)]
render("slide_12.svg", page("工程 ④", "记住你错在哪，也记住下次该练什么", b, 12))

# ---------------------------------------------------------------- 13 权限
b = []
gates = [("模型提议", "agent 想调某个工具"), ("schema 白名单", "禁用的工具不出现"),
         ("执行层判定", "is_tool_allowed 逐次查"), ("人在环", "写操作等确认")]
x = MG
for i, (t, d) in enumerate(gates):
    b += [txt(x, 186, f"0{i + 1}", 15, PRI, 700), txt(x, 222, t, 21, INK, 700), txt(x, 252, d, 16, GRAY)]
    if i < 3:
        b += [txt(x + 246, 222, "→", 18, MUT)]
    x += 290
b += [line(MG, 320, W - MG, 320),
      txt(MG, 380, "举个真会发生的例子：它想覆盖你的一份笔记 —— write_file 在工具表里，执行前 interrupt() 弹给你确认；", 21, GRAY),
      txt(MG, 418, "你点取消，文件一个字节都不动。写在提示词里模型可以忘，写在 interrupt() 里它跑不掉。", 21, INK),
      rect(MG, 490, W - 2 * MG, 70, TINT, 6),
      txt(MG + 24, 534, "「AI 不改你的数据」是承诺，不是请求。", 24, PRI, 700)]
render("slide_13.svg", page("工程 ⑤", "会动手，不等于乱动手：权限和写库都由系统说了算", b, 13))

# ---------------------------------------------------------------- 14 数据
b = []
kpis = [("284", "项", "自动化测试", "全 Mock，零 API 消耗"), ("0.9714", "", "检索 Hit@3 = MRR", "35 题，真实向量 35/35"),
        ("1.0", "", "意图识别", "15 句标注，六类意图"), ("0", "处", "占位实现", "全仓无占位实现")]
x = MG
for num, unit, label, sub in kpis:
    b += [txt(x, 268, num, 60, INK, 700), txt(x, 306, label, 17, INK, 700), txt(x, 334, sub, 15, GRAY)]
    if unit:
        b += [txt(x + 150, 268, unit, 16, GRAY)]
    x += 296
b += [line(MG, 380, W - MG, 380),
      txt(MG, 436, "关掉词面精排，同一张考卷立刻从 0.9714 掉到 0.9571 —— 精排到底有没有用，不用信我，看数。", 22, ACC, 700),
      txt(MG, 486, "domain 层全是纯函数：排期、四档自评、检索融合、护栏，测它们不用起数据库、不联网、不花额度。", 20, GRAY)]
render("slide_14.svg", page("工程 ⑥", "284 项测试全绿，是因为每一层都能单独测", b, 14))

# ---------------------------------------------------------------- 15 章节 03
s15 = [
    txt(MG, 210, "03", 120, TINT, 700),
    txt(MG, 268, "这一章：凭什么是它", 20, PRI, 700),
    txt(MG, 340, "同样的活儿，为什么非它不可", 42, INK, 700),
    txt(MG, 400, "不是比谁功能多，而是谁能把「资料、错题、进度」串成一条线。", 22, GRAY),
    line(MG, 500, W - MG, 500),
    txt(MG, 540, "01  它做什么", 18, MUT),
    txt(MG + 200, 540, "02  凭什么做到", 18, MUT),
    txt(MG + 400, 540, "03  凭什么是它", 18, PRI, 700),
]
render("slide_15.svg", "\n".join([
    f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W}" height="{H}" viewBox="0 0 {W} {H}" lang="zh-CN">',
    rect(0, 0, W, H, WHITE), rect(0, 0, 10, H, PRI), *s15,
    line(MG, 676, W - MG, 676, LINE), txt(MG, 700, "知迹 · 赛道十三 · 智慧教育", 14, MUT),
    txt(W - MG, 700, "15 / 18", 14, MUT, anchor="end"), "</svg>"]))

# ---------------------------------------------------------------- 16 对比表
b = []
cols = [(MG, 300, ""), (MG + 300, 260, "通用 AI"), (MG + 560, 280, "在线题库 App"), (MG + 840, 312, "知迹")]
for x, w, name in cols:
    if name:
        b += [rect(x, 160, w, 44, PRI if name == "知迹" else "#7C8FA6", 4),
              txt(x + w / 2, 189, name, 17, WHITE, 700, anchor="middle")]
rows = [("懂不懂你的资料", "只懂通用知识", "只懂它自己的题库", "只从你的库里找，切到页"),
        ("会不会替你出题", "你问一句它答一句", "固定题库，对不上讲义", "按讲义出，分三档难度"),
        ("记不记得错因", "聊完就散", "只记对错", "记错因，下次按它加重"),
        ("会不会排复习", "不管", "何时看全凭你", "掌握度 + 间隔 0/1/3/7"),
        ("改数据谁说了算", "没有这个概念", "不碰你的文件", "四道闸门 + 写前确认"),
        ("结论能不能复现", "换个时间答案就变", "过程不可见", "284 项测试 + 35 题考卷")]
y = 236
for label, a, bb, c in rows:
    b += [txt(MG, y, label, 18, INK, 700),
          txt(MG + 300, y, a, 16, GRAY), txt(MG + 560, y, bb, 16, GRAY),
          txt(MG + 840, y, c, 16, ACC, 700), line(MG, y + 22, W - MG, y + 22)]
    y += 62
b += [txt(MG, 646, "前两条路各自都成立，但它们手里没有「你的那一份」。", 19, GRAY)]
render("slide_16.svg", page("对比", "三条路摆在一起：只有第三条把整条线串起来了", b, 16))

# ---------------------------------------------------------------- 17 壁垒
b = []
wins = [("01", "同一份资料", "题从库里出", "出题时检索的是你上传的那几页，不是互联网。"),
        ("02", "同一份错题", "复习按错题排", "答错就记错因、降掌握度，下一次出题立刻按它加重。"),
        ("03", "同一份进度", "越用越像你的私教", "资料越全、错题越多，掌握度曲线越准，排期越贴合你。")]
y = 200
for num, tag, t, d in wins:
    b += [txt(MG, y, num, 15, PRI, 700), txt(MG + 56, y, tag, 16, MUT, 700),
          txt(MG + 56, y + 34, t, 24, INK, 700), txt(MG + 420, y + 20, d, 20, GRAY),
          line(MG, y + 70, W - MG, y + 70)]
    y += 116
b += [txt(MG, 590, "别人给你的是「一次回答」，它给的是「一条会自己变准的线」。", 24, INK, 700)]
render("slide_17.svg", page("壁垒", "单看每一项都不稀奇，稀奇的是它们共用同一份底账", b, 17))

# ---------------------------------------------------------------- 18 结尾
s18 = [
    rect(0, 0, W, H, PRI),
    txt(MG, 250, "谢谢聆听 · 欢迎追问", 20, "#A8C0DA", 700),
    txt(MG, 400, "知迹", 96, WHITE, 700),
    rect(MG, 438, 160, 6, ACC),
    txt(MG, 510, "会整理、会出题的学习 Agent", 32, WHITE, 700),
    txt(MG, 570, "284 项测试全绿　·　35 题检索 MRR 0.9714", 20, "#C8D6E6"),
    txt(MG, 610, "源码、评测集与体检报告都在这台机器上，欢迎当场抽查。", 18, "#8FB0CE"),
]
render("slide_18.svg", "\n".join([
    f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{W}" height="{H}" viewBox="0 0 {W} {H}" lang="zh-CN">',
    *s18, "</svg>"]))

print("wrote", len(list(OUT.glob("slide_*.svg"))), "pages to", OUT)
