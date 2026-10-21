#!/usr/bin/env python3
"""
kami_slides.py — 基于 tw93/kami (MIT) 的 slides.py 模板，填入「知迹」答辩内容。

上游：https://github.com/tw93/kami  (MIT License, (c) 2026 Tw93)
本文件为衍生作品，保留上游版权声明；内容与页序为本项目所有。

原模板说明：
slides.py - parchment design system slide deck generator

用法：
  pip install python-pptx --break-system-packages
  python3 slides.py --out output.pptx

输出：
  output.pptx (16:9 宽屏, parchment 风格)

这是一个模板脚本 - 填充自己的内容后直接运行。
"""

from pptx import Presentation
from pptx.util import Emu, Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree

# ═══════════════════════════════════════════════════════════
# Design System Constants
# ═══════════════════════════════════════════════════════════

# 色板
PARCHMENT   = RGBColor(0xf5, 0xf4, 0xed)
IVORY       = RGBColor(0xfa, 0xf9, 0xf5)
BRAND       = RGBColor(0x1B, 0x36, 0x5D)
NEAR_BLACK  = RGBColor(0x14, 0x14, 0x13)
DARK_WARM   = RGBColor(0x3d, 0x3d, 0x3a)
OLIVE       = RGBColor(0x50, 0x4e, 0x49)
STONE       = RGBColor(0x6b, 0x6a, 0x64)
BORDER      = RGBColor(0xe8, 0xe6, 0xdc)
WHITE       = RGBColor(0xff, 0xff, 0xff)

# Fonts. Single serif per page. PPT falls back on the viewer's system.
# For Japanese best-effort output, set LANG = "ja" before generating.
LANG = "zh"
CN_SERIF = "Songti SC"   # 本机无思源宋体；Windows/WPS 会替换为宋体（同为衬线）
JA_SERIF = "YuMincho"  # Windows: Yu Mincho; Linux: Noto Serif CJK JP

SERIF = JA_SERIF if LANG == "ja" else CN_SERIF
SANS  = SERIF

# 16:9 宽屏
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def blank_slide(prs, bg_color=PARCHMENT):
    """创建空白幻灯片，指定背景色"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])   # 6 = Blank
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = bg_color
    bg.line.fill.background()
    bg.shadow.inherit = False
    return slide


def add_text(slide, text, left, top, width, height,
             font=SANS, size=18, bold=False, italic=False,
             color=NEAR_BLACK, align=PP_ALIGN.LEFT,
             vanchor=MSO_ANCHOR.TOP):
    """加一段文字"""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = vanchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    # python-pptx 的 font.name 只写 a:latin（西文），中文要看 a:ea / a:cs，
    # 不显式写的话中文会落到查看器默认字体——换机器就变样。
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", font)
    return tb


def add_card(slide, left, top, width, height,
             fill=IVORY, border=BORDER, border_weight=0.5):
    """加卡片背景"""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = fill
    card.line.color.rgb = border
    card.line.width = Pt(border_weight)
    card.shadow.inherit = False
    return card


# ═══════════════════════════════════════════════════════════
# Slide Templates
# ═══════════════════════════════════════════════════════════

def cover_slide(prs, title, subtitle, author, date):
    """封面：大标题 + 副标题 + 作者/日期"""
    s = blank_slide(prs)
    # 大标题（serif 44pt 居中）
    add_text(s, title,
             Inches(1), Inches(2.5), Inches(11.33), Inches(1.5),
             font=SERIF, size=44, color=NEAR_BLACK,
             align=PP_ALIGN.CENTER)
    # 副标题
    add_text(s, subtitle,
             Inches(1), Inches(4.5), Inches(11.33), Inches(0.8),
             font=SANS, size=18, color=OLIVE,
             align=PP_ALIGN.CENTER)
    # 作者 + 日期
    add_text(s, f"{author}　·　{date}",
             Inches(1), Inches(6.5), Inches(11.33), Inches(0.4),
             font=SANS, size=13, color=STONE,
             align=PP_ALIGN.CENTER)
    return s


def toc_slide(prs, items):
    """目录页：01 章节名 列表"""
    s = blank_slide(prs)
    add_text(s, "目录",
             Inches(1.2), Inches(0.8), Inches(10), Inches(0.8),
             font=SERIF, size=32, color=NEAR_BLACK)

    for i, item in enumerate(items):
        y = Inches(2.4 + i * 0.9)
        add_text(s, f"0{i+1}",
                 Inches(1.2), y, Inches(1), Inches(0.6),
                 font=SERIF, size=28, color=BRAND)
        add_text(s, item,
                 Inches(2.4), y, Inches(9), Inches(0.6),
                 font=SERIF, size=22, color=NEAR_BLACK,
                 vanchor=MSO_ANCHOR.MIDDLE)
    return s


def chapter_slide(prs, number, title):
    """章节首页：油墨蓝色背景 + 居中大标题"""
    s = blank_slide(prs, bg_color=BRAND)
    add_text(s, f"0{number}",
             Inches(0.8), Inches(0.5), Inches(2), Inches(0.8),
             font=SERIF, size=26, color=WHITE)
    add_text(s, title,
             Inches(1), Inches(3), Inches(11.33), Inches(1.5),
             font=SERIF, size=56, color=WHITE,
             align=PP_ALIGN.CENTER)
    return s


def content_slide(prs, eyebrow, title, body, page_num=None):
    """内容页：小标题 + 大标题 + 正文"""
    s = blank_slide(prs)
    # eyebrow
    add_text(s, eyebrow,
             Inches(1.2), Inches(0.6), Inches(10), Inches(0.4),
             font=SANS, size=12, color=STONE)
    # title
    add_text(s, title,
             Inches(1.2), Inches(1.2), Inches(11.33), Inches(1.2),
             font=SERIF, size=32, color=NEAR_BLACK)
    # body
    add_text(s, body,
             Inches(1.2), Inches(3), Inches(11), Inches(3.5),
             font=SANS, size=18, color=DARK_WARM)
    # page number
    if page_num is not None:
        add_text(s, f" - {page_num:02d}",
                 Inches(11.5), Inches(6.9), Inches(1.5), Inches(0.3),
                 font=SANS, size=11, color=STONE,
                 align=PP_ALIGN.RIGHT)
    return s


def metrics_slide(prs, title, metrics):
    """数据页：标题 + N 张数据卡并排
    metrics: [(value, label), ...]
    """
    s = blank_slide(prs)
    # 标题
    add_text(s, title,
             Inches(1.2), Inches(0.8), Inches(11), Inches(1),
             font=SERIF, size=28, color=NEAR_BLACK,
             align=PP_ALIGN.CENTER)

    # 数据卡
    n = len(metrics)
    card_w = Inches(2.8)
    gap = Inches(0.3)
    total_w = card_w * n + gap * (n - 1)
    start = (SLIDE_W - total_w) / 2

    for i, (value, label) in enumerate(metrics):
        x = start + (card_w + gap) * i
        # 大数字
        add_text(s, value,
                 x, Inches(3), card_w, Inches(1.5),
                 font=SERIF, size=52, color=BRAND,
                 align=PP_ALIGN.CENTER)
        # 标签
        add_text(s, label,
                 x, Inches(4.8), card_w, Inches(0.6),
                 font=SANS, size=14, color=OLIVE,
                 align=PP_ALIGN.CENTER)
    return s


def quote_slide(prs, quote, source):
    """引用页：极简，居中引文"""
    s = blank_slide(prs)
    add_text(s, f"\u201c{quote}\u201d",
             Inches(1.5), Inches(2.8), Inches(10.33), Inches(2.5),
             font=SERIF, size=28, color=NEAR_BLACK,
             align=PP_ALIGN.CENTER,
             vanchor=MSO_ANCHOR.MIDDLE)
    add_text(s, f" - {source}",
             Inches(1.5), Inches(5.2), Inches(10.33), Inches(0.4),
             font=SANS, size=14, color=OLIVE,
             align=PP_ALIGN.CENTER)
    return s


def comparison_slide(prs, eyebrow, left_title, left_items, right_title, right_items, page_num=None):
    """对比页：左右两栏，留白分隔，左侧降调，右侧全色
    left_items / right_items: list of str (最多 4 条)
    """
    s = blank_slide(prs)
    add_text(s, eyebrow,
             Inches(1.2), Inches(0.6), Inches(10), Inches(0.4),
             font=SANS, size=12, color=STONE)
    # 左栏标题（降调）
    add_text(s, left_title,
             Inches(1.2), Inches(1.2), Inches(5), Inches(0.8),
             font=SERIF, size=22, color=OLIVE)
    # 右栏标题（全色）
    add_text(s, right_title,
             Inches(7.0), Inches(1.2), Inches(5), Inches(0.8),
             font=SERIF, size=22, color=NEAR_BLACK)
    # 左栏条目（降调）
    for i, item in enumerate(left_items[:4]):
        add_text(s, item,
                 Inches(1.2), Inches(2.6 + i * 0.9), Inches(4.9), Inches(0.7),
                 font=SANS, size=17, color=STONE)
    # 右栏条目（全色）
    for i, item in enumerate(right_items[:4]):
        add_text(s, item,
                 Inches(7.0), Inches(2.6 + i * 0.9), Inches(5.2), Inches(0.7),
                 font=SANS, size=17, color=DARK_WARM)
    if page_num is not None:
        add_text(s, f" - {page_num:02d}",
                 Inches(11.5), Inches(6.9), Inches(1.5), Inches(0.3),
                 font=SANS, size=11, color=STONE,
                 align=PP_ALIGN.RIGHT)
    return s


def pipeline_slide(prs, eyebrow, title, steps, page_num=None):
    """流程步骤页：01/02/03 序号 + 步骤标题 + 步骤描述
    steps: list of (step_title, step_desc)，最多 4 步
    """
    s = blank_slide(prs)
    add_text(s, eyebrow,
             Inches(1.2), Inches(0.6), Inches(10), Inches(0.4),
             font=SANS, size=12, color=STONE)
    add_text(s, title,
             Inches(1.2), Inches(1.1), Inches(11), Inches(0.9),
             font=SERIF, size=30, color=NEAR_BLACK)

    n = len(steps[:4])
    step_w = Inches(11.5 / n)
    for i, (step_title, step_desc) in enumerate(steps[:4]):
        x = Inches(1.0) + step_w * i
        # 序号
        add_text(s, f"0{i+1}",
                 x, Inches(2.5), step_w, Inches(0.8),
                 font=SERIF, size=40, color=BRAND)
        # 步骤标题
        add_text(s, step_title,
                 x, Inches(3.45), step_w - Inches(0.2), Inches(0.6),
                 font=SERIF, size=19, color=NEAR_BLACK)
        # 步骤描述
        add_text(s, step_desc,
                 x, Inches(4.15), step_w - Inches(0.2), Inches(2.2),
                 font=SANS, size=15, color=OLIVE)
    if page_num is not None:
        add_text(s, f" - {page_num:02d}",
                 Inches(11.5), Inches(6.9), Inches(1.5), Inches(0.3),
                 font=SANS, size=11, color=STONE,
                 align=PP_ALIGN.RIGHT)
    return s


def ending_slide(prs, message, contact):
    """结束页"""
    s = blank_slide(prs)
    add_text(s, message,
             Inches(1), Inches(3), Inches(11.33), Inches(1.2),
             font=SERIF, size=40, color=NEAR_BLACK,
             align=PP_ALIGN.CENTER)
    add_text(s, contact,
             Inches(1), Inches(4.8), Inches(11.33), Inches(0.6),
             font=SANS, size=16, color=OLIVE,
             align=PP_ALIGN.CENTER)
    return s


# ═══════════════════════════════════════════════════════════
# Main: 示例 deck，按实际需求改
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 本项目补充的三个版式（Kami 模板只有封面/目录/内容/数据/对比/流程/引用/结束，
# 没有「细线表格」「左右分栏」「截图页」，而答辩这三样都要用）
# ═══════════════════════════════════════════════════════════

MARGIN_L = Inches(1.1)
CONTENT_W = Inches(11.13)


def rule(slide, left, top, width, color=BORDER, weight=0.6):
    """细线：表格行线、强调下划线。"""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Pt(weight))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def vrule(slide, left, top, height, color=BORDER):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, Pt(0.6), height)
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def head(slide, eyebrow, title, title_size=27):
    """页眉：eyebrow + 结论式标题。"""
    add_text(slide, eyebrow, MARGIN_L, Inches(0.6), Inches(9), Inches(0.35),
             font=SANS, size=12, color=STONE)
    add_text(slide, title, MARGIN_L, Inches(1.1), CONTENT_W, Inches(1.3),
             font=SERIF, size=title_size, color=NEAR_BLACK)


def pagenum(slide, n):
    add_text(slide, f"· {n:02d}", Inches(11.4), Inches(6.95), Inches(1.2), Inches(0.3),
             font=SANS, size=11, color=STONE, align=PP_ALIGN.RIGHT)


def foot(slide, text):
    add_text(slide, text, MARGIN_L, Inches(6.45), CONTENT_W, Inches(0.45),
             font=SANS, size=12, color=STONE)


def table_slide(prs, eyebrow, title, headers, rows, widths, page_num, note=None):
    """细线表格页：不���色表头、不加竖线，行分隔靠留白与极细线（Kami 规范）。"""
    s = blank_slide(prs)
    head(s, eyebrow, title)
    x = MARGIN_L
    for label, w in zip(headers, widths):
        add_text(s, label, x, Inches(2.25), Inches(w), Inches(0.3),
                 font=SANS, size=12, color=STONE)
        x += Inches(w)
    rule(s, MARGIN_L, Inches(2.62), CONTENT_W, weight=0.6)
    y = 2.78
    row_h = (6.2 - y) / max(len(rows), 1)
    for row in rows:
        x = MARGIN_L
        for cell, w in zip(row, widths):
            add_text(s, cell, x, Inches(y), Inches(w - 0.12), Inches(row_h - 0.08),
                     font=SANS, size=12.5, color=DARK_WARM)
            x += Inches(w)
        y += row_h
        if rows.index(row) < len(rows) - 1:
            rule(s, MARGIN_L, Inches(y - 0.08), CONTENT_W, weight=0.25)
    if note:
        foot(s, note)
    pagenum(s, page_num)
    return s


def split_slide(prs, eyebrow, title, left_title, left_items, right_title, right_items,
                page_num, note=None):
    """左右分栏：每栏 = 小标题 + 条目(label, 说明)。"""
    s = blank_slide(prs)
    head(s, eyebrow, title)
    lx, rx = MARGIN_L, Inches(7.0)
    vrule(s, Inches(6.62), Inches(2.3), Inches(4.0))
    for col_x, col_title, items in ((lx, left_title, left_items), (rx, right_title, right_items)):
        add_text(s, col_title, col_x, Inches(2.28), Inches(5.3), Inches(0.35),
                 font=SANS, size=14, bold=True, color=BRAND)
        y = 2.78
        for label, desc in items:
            add_text(s, label, col_x, Inches(y), Inches(5.3), Inches(0.3),
                     font=SANS, size=13.5, bold=True, color=NEAR_BLACK)
            add_text(s, desc, col_x, Inches(y + 0.3), Inches(5.2), Inches(0.62),
                     font=SANS, size=12, color=DARK_WARM)
            y += 1.02
    if note:
        foot(s, note)
    pagenum(s, page_num)
    return s


def card_grid_slide(prs, eyebrow, title, cards, page_num, note=None):
    """2×2 证据卡：每张卡 = 名称 + 作用 + 局限。"""
    s = blank_slide(prs)
    head(s, eyebrow, title)
    cw, ch, gap = Inches(5.45), Inches(1.72), Inches(0.26)
    for i, (name, role, limit) in enumerate(cards):
        col, row = i % 2, i // 2
        x = MARGIN_L + col * (cw + gap)
        y = Inches(2.3) + row * (ch + gap)
        add_card(s, x, y, cw, ch)
        add_text(s, name, x + Inches(0.22), y + Inches(0.16), Inches(5.0), Inches(0.3),
                 font=SANS, size=14, bold=True, color=BRAND)
        add_text(s, role, x + Inches(0.22), y + Inches(0.54), Inches(5.0), Inches(0.6),
                 font=SANS, size=12, color=DARK_WARM)
        add_text(s, limit, x + Inches(0.22), y + Inches(1.22), Inches(5.0), Inches(0.3),
                 font=SANS, size=11, color=STONE)
    if note:
        foot(s, note)
    pagenum(s, page_num)
    return s


def image_slide(prs, eyebrow, title, image_path, caption, steps, page_num, note=None):
    """截图页：实拍做视觉锚点 + 一列要点。"""
    s = blank_slide(prs)
    head(s, eyebrow, title)
    from PIL import Image as PILImage
    with PILImage.open(image_path) as im:
        iw, ih = im.size
    img_w = Inches(8.2)
    img_h = Inches(8.2 * ih / iw)
    s.shapes.add_picture(str(image_path), MARGIN_L, Inches(2.3), width=img_w, height=img_h)
    add_text(s, caption, MARGIN_L, Inches(2.3) + img_h + Inches(0.1), Inches(8.1), Inches(0.4),
             font=SANS, size=11.5, color=STONE)
    x = Inches(9.55)
    y = 2.3
    for i, (label, desc) in enumerate(steps, 1):
        add_text(s, f"{i}", x, Inches(y), Inches(0.3), Inches(0.3),
                 font=SERIF, size=15, bold=True, color=BRAND)
        add_text(s, label, x + Inches(0.32), Inches(y), Inches(2.6), Inches(0.3),
                 font=SANS, size=13.5, bold=True, color=NEAR_BLACK)
        add_text(s, desc, x + Inches(0.32), Inches(y + 0.28), Inches(2.6), Inches(0.62),
                 font=SANS, size=11.5, color=DARK_WARM)
        y += 1.0
    if note:
        foot(s, note)
    pagenum(s, page_num)
    return s


def cover_kami(prs, eyebrow, title, subtitle, proposition, stack, stats):
    """封面：赛事行 + 大标题 + 副标 + 核心命题 + 技术栈 + 四个数据。"""
    s = blank_slide(prs)
    add_text(s, eyebrow, MARGIN_L, Inches(0.9), Inches(10), Inches(0.35),
             font=SANS, size=12, color=STONE)
    add_text(s, title, MARGIN_L, Inches(1.9), Inches(8), Inches(1.2),
             font=SERIF, size=56, bold=True, color=BRAND)
    add_text(s, subtitle, MARGIN_L, Inches(3.15), Inches(9), Inches(0.5),
             font=SERIF, size=21, color=NEAR_BLACK)
    rule(s, MARGIN_L, Inches(3.85), Inches(1.1), color=BRAND, weight=1.2)
    add_text(s, proposition, MARGIN_L, Inches(4.12), Inches(7.6), Inches(0.9),
             font=SANS, size=14, color=DARK_WARM)
    add_text(s, stack, MARGIN_L, Inches(5.1), Inches(7.6), Inches(0.6),
             font=SANS, size=11.5, color=STONE)
    x = MARGIN_L
    for value, label in stats:
        add_text(s, value, x, Inches(6.0), Inches(2.2), Inches(0.5),
                 font=SERIF, size=26, bold=True, color=BRAND)
        add_text(s, label, x, Inches(6.52), Inches(2.4), Inches(0.35),
                 font=SANS, size=11, color=STONE)
        x += Inches(2.75)
    return s



def metrics_page(prs, eyebrow, title, metrics, body, note, page_num):
    """数据页：标题左对齐（与全篇一致）+ 四个数字 + 说明 + 口径。"""
    s = blank_slide(prs)
    head(s, eyebrow, title)
    n = len(metrics)
    gap = Inches(0.3)
    card_w = (CONTENT_W - gap * (n - 1)) / n
    x = MARGIN_L
    for value, label in metrics:
        add_text(s, value, x, Inches(2.45), Emu(int(card_w - Inches(0.2))), Inches(0.7),
                 font=SERIF, size=30, bold=True, color=BRAND)
        add_text(s, label, x, Inches(3.2), Emu(int(card_w - Inches(0.2))), Inches(0.4),
                 font=SANS, size=12, color=STONE)
        x += card_w + gap
    rule(s, MARGIN_L, Inches(3.9), CONTENT_W, weight=0.6)
    add_text(s, body, MARGIN_L, Inches(4.2), Inches(11.0), Inches(1.7),
             font=SANS, size=14.5, color=DARK_WARM)
    foot(s, note)
    pagenum(s, page_num)
    return s


def ending_page(prs, message, proposition, next_steps, contact, page_num):
    """收束页：金句 + 三件下一步 + 可复跑数据（Kami 的 ending_slide 太空）。"""
    s = blank_slide(prs)
    add_text(s, "结论", MARGIN_L, Inches(1.4), Inches(4), Inches(0.35),
             font=SANS, size=12, color=STONE)
    add_text(s, message, MARGIN_L, Inches(1.9), Inches(10.6), Inches(1.3),
             font=SERIF, size=32, bold=True, color=BRAND)
    rule(s, MARGIN_L, Inches(3.3), Inches(1.1), color=BRAND, weight=1.2)
    add_text(s, proposition, MARGIN_L, Inches(3.6), Inches(10.4), Inches(0.9),
             font=SANS, size=15, color=DARK_WARM)
    x = MARGIN_L
    for label, desc in next_steps:
        add_text(s, label, x, Inches(4.75), Inches(3.5), Inches(0.3),
                 font=SANS, size=13, bold=True, color=NEAR_BLACK)
        add_text(s, desc, x, Inches(5.1), Inches(3.4), Inches(0.9),
                 font=SANS, size=11.5, color=DARK_WARM)
        x += Inches(3.72)
    rule(s, MARGIN_L, Inches(6.2), CONTENT_W, weight=0.25)
    add_text(s, contact, MARGIN_L, Inches(6.4), Inches(11.13), Inches(0.4),
             font=SANS, size=12, color=STONE)
    pagenum(s, page_num)
    return s


# ═══════════════════════════════════════════════════════════
# 「知迹」答辩 PPT · 11 页（内容同 v3，视觉与流程换成 kami 设计系统）
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="知迹答辩.pptx")
    args = parser.parse_args()

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    # ───────── 封面 ─────────
    cover_kami(prs,
        eyebrow="全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育与智能软件类",
        title="知迹",
        subtitle="面向大学生的 AI 学习私教与智能复习系统",
        proposition="整理学习资料，自动出错题，结合知识库复习——三件事，一个应用。",
        stack="技术栈　Python 3.12 · LangGraph · FastAPI + SSE · SQLite · Next.js 16 · React 19 · MCP",
        stats=[("284", "项自动测试"), ("35", "道检索题"), ("7", "个功能页面"), ("1", "个 SQLite 文件")])

    # ───────── 目录 ─────────
    s = toc_slide(prs, ["背景", "技术", "应用与验证", "边界与下一步"])
    add_text(s, "技术篇六项：回合编排 · 工具调用 · 工具权限 · 检索 · MCP · 联网搜索",
             MARGIN_L, Inches(6.5), Inches(11.13), Inches(0.4),
             font=SANS, size=12, color=STONE)

    # ═══════ 第一段 · 背景 ═══════

    # 3 背景①：为什么做这个应用
    split_slide(prs, "01 背景",
        "整理资料，出题，复习——三件事连起来",
        "要做的三件事", [
            ("一、整理资料", "讲义、课件、笔记、错题照片传进来，按学科分好；PDF 能翻到第几页，拍照的板书也能转成文字。"),
            ("二、自动出题", "按你传进来的资料出题；上次做错的方向会多出几道，不是凑一套。"),
            ("三、结合知识库复习", "今天该练哪几题，按掌握度和到期时间排好；复习时能翻回原文那一页。"),
        ],
        "做完之后是这样", [
            ("找资料", "搜一句就定位到第几页"),
            ("出题", "题从你的资料和错因里来，不是凑的"),
            ("复习", "到期的自动排好，不用自己惦记"),
            ("不被乱改", "写进资料库前会先问你一句"),
        ], 3,
        note="后面几页讲的是支撑这三件事的做法：检索怎么保证找得准，过程怎么保证不丢，数据怎么保证不被模型改坏。")

    # 4 背景②：实际场景
    s4 = pipeline_slide(prs, "01 背景",
        "实际是这样用的：一周里发生的事",
        [("周一　把讲义传进来", "这周的课件、笔记、错题照片一次性丢进去，按学科分好；以后不用再翻各个平台找。"),
         ("周三　复习被问住了", "就着资料提问，答案标着出自哪份资料第几页，点开就能对；讲不清的地方当场记下。"),
         ("周五　自动出题", "按这周传的资料出题，做错的方向会多出几道；做完能看参考答案和关键步骤。"),
         ("周日　今天该练哪几题", "到期题和薄弱学科自动排好，练完打个分，复习时间跟着掌握度走。")],
        4)
    foot(s4, "这条链上任何一步断了，后面的都接不上——技术篇讲的就是怎么保证它不断。")

    # ═══════ 第二段 · 技术 ═══════

    # 5 技术①：回合编排
    split_slide(prs, "02 技术 · 回合编排",
        "一次学习回合，是画出来的一张图",
        "四个节点", [
            ("route", "先判这轮要干什么：讲解、练习、规划、检索、计算"),
            ("plan", "复杂任务才出计划，简单请求直接进模型"),
            ("agent", "模型推理，决定这一步调哪个工具"),
            ("tools", "执行工具、把结果回填，再回到 agent"),
        ],
        "为什么要画成图", [
            ("因为它会中断", "中途关页、下次进来要能从断的地方接着跑"),
            ("因为它要等人", "写数据前必须停下来问一句，不能自己决定"),
            ("因为它会出错", "哪一步出的问题要能查得到，而不是整段重跑"),
        ], 5,
        note="每个节点结束都落一次检查点——这既是「断了能接着跑」，也是「写库前停下来问你」的技术前提。")

    # 6 技术②：工具调用
    card_grid_slide(prs, "02 技术 · 工具调用",
        "九个工具，模型想调哪个就调哪个",
        [
            ("查自己的东西", "knowledge_search 查学科知识库、mistake_search 查错题记录，都能按关键词过滤", "返回片段时带出处"),
            ("存进去", "save_note 把结论沉淀进某个学科库；write_file 写进文件工作区", "存之前一定先问一句"),
            ("看工作区", "read_file 读文件、list_files 列出文件，按最近修改排序", "同名文件会被覆盖，工具说明里写明了"),
            ("问外面", "web_search 联网搜、fetch_url 读网页正文、calculator 算表达式", "资料里没有才用得上的那部分"),
        ], 6,
        note="工具失败不炸回合：单次超时 + 有限次重试，还失败就转成一条工具消息告诉模型，让它换条路走。")

    # 7 技术③：工具权限
    split_slide(prs, "02 技术 · 工具权限",
        "看得见的工具，不等于跑得动的工具",
        "第一层：模型看得见哪些", [
            ("讲解 · 检索", "全部工具都能用"),
            ("练习", "只给只读工具，练习时不允许写你的库"),
            ("进度", "不给任何工具"),
        ],
        "第二层：执行时放不放行", [
            ("讲解 · 检索", "放行；写操作仍要经过确认"),
            ("练习", "写操作直接拒绝"),
            ("进度", "一律拦截"),
        ], 7,
        note="两层都要有：只做第一层，模型仍会说出被禁工具的名字然后失败；只做第二层，模型会一遍遍重试浪费轮数。")

    # 8 技术④：检索
    card_grid_slide(prs, "02 技术 · 检索",
        "中文资料难找，所以不只找一路",
        [
            ("按字面找", "trigram 分词，中文按字面也能命中", "局限：错一个字就漏"),
            ("换个说法找", "本征值 → 特征值，queue → 队列", "局限：靠词典，推断有噪声"),
            ("短词兜底", "「秩」「队列」进不了 trigram 索引", "局限：按覆盖度排序，精度中等"),
            ("按意思找", "字面全不同、意思相近仍能召回", "局限：没有真实模型时不可靠"),
        ], 8,
        note="四路的分数不能直接相加（单位不一样），所以按名次加权融合，再补一层词面精排。关掉精排，MRR 从 0.9714 掉到 0.9571。")

    # 9 技术⑤：MCP
    split_slide(prs, "02 技术 · MCP",
        "接外部工具，用的是现成的标准",
        "我们做了什么", [
            ("自己写了一个最小客户端", "stdio 上的 JSON-RPC，能启动外部 server、列出工具、调用工具、关闭"),
            ("零外部依赖", "不用装任何第三方 MCP 库，一个文件就能跑；缺了的功能也不影响主流程"),
        ],
        "换来什么 / 代价", [
            ("工具能即插即用", "外部 server 的工具被发现后注册进工具表，模型直接能用"),
            ("代价是只覆盖常用方法", "完整规范还有采样、任务等扩展，我们没做，也暂时用不上"),
        ], 9,
        note="选它的理由：MCP 已经是事实标准，自研协议没有生态，跨宿主也复用不了。")

    # 10 技术⑥：联网搜索
    split_slide(prs, "02 技术 · 联网搜索",
        "资料里没有的，才去外面找",
        "怎么用", [
            ("一次给几个不同角度的问题", "不是只搜一次，而是拆成 2–4 个角度各搜一遍，再把结果合起来"),
            ("结果自动清洗", "网页正文会去掉标签和脚本，只留能读的文本"),
        ],
        "接了哪些源", [
            ("DuckDuckGo · Tavily", "通用搜索，海外内容多"),
            ("必应中国 · 博查", "中文内容更全"),
            ("DeepSeek 内置搜索", "接的是 DeepSeek 时自动启用，不用另配 key"),
        ], 10,
        note="搜回来的内容一律当「外部资料」标注来源，和你自己传的资料分开——避免混在一起分不清。")

    # ═══════ 第三段 · 应用与验证 ═══════

    # 11 应用与验证
    image_slide(prs, "03 应用与验证",
        "三件事在界面上是这样连起来的",
        "assets/ui-knowledge.png",
        "知识库页实拍：左边是学科目录树，中间是资料列表，右侧可以直接就着当前这个库提问",
        [("整理资料", "传进来就按学科分好，PDF 能翻到第几页"),
         ("自动出题", "按资料出题，做错的记下错因"),
         ("结合知识库复习", "到期题和薄弱学科自动排好"),
         ("过程留痕", "每一步都能回看，出问题查得到")],
        11,
        note="演示数据：7 个学科库 / 24 份资料 / 46 个可检索片段，全部带出处。验证：284 项自动测试、35 道检索题、意图 15 句全对。")

    # ═══════ 第四段 · 边界与下一步 ═══════

    # 12 边界
    table_slide(prs, "04 边界与下一步",
        "六项能力：两项达标，三项只做了一半，一项没做",
        ["能力项", "状态", "依据 / 还缺什么"],
        [
            ["中断可恢复", "达标", "状态图 + 检查点 + 中断恢复，均有回归测试"],
            ["检索准确 / 可追溯", "达标", "35 题考卷，接真实向量 35/35，引用精确到页"],
            ["工具执行治理", "一半", "有双层权限与超时兜底，缺按参数与资源的细粒度约束"],
            ["长上下文管理", "一半", "有抽取式摘要与预算控制，缺关键事实外置成结构化笔记"],
            ["长期记忆", "一半", "按课程隔离、写入前确认，缺过期、替换与删除机制"],
            ["任务级成功率评测", "没做", "现有考卷只测「找到没」「分类对不对」，不测「这次复习有没有用」"],
        ], [3.2, 1.3, 6.63], 12,
        note="接下来按这个顺序补：任务级成功率评测 → 记忆的过期与删除 → 更难的检索考卷。三项都能在现有门禁里验证。")

    # 13 收束
    ending_page(prs, "资料进去，题出来，复习排好——就这三件事。",
        "现在都能用。还在补的有三块，写在上一页：任务级评测、记忆的过期与删除、更难的题库。",
        [("下一步 · 任务级评测", "从「找到没」升级到「这次复习有没有用」"),
         ("下一步 · 记忆生命周期", "记错的东西能改、能删、过期会失效"),
         ("下一步 · 更难的题库", "题太简单就看不出改动的好坏")],
        "284 项自动测试 · 35 道检索题 · 7 个功能页面　|　赛道十三 智慧教育",
        13)

    prs.save(args.out)
    print(f"OK: 已生成 {args.out}")


if __name__ == "__main__":
    main()
