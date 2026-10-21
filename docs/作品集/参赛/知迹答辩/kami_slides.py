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

    # 1 封面
    cover_kami(prs,
        eyebrow="全国大学生数字媒体科技作品及创意竞赛 · 赛道十三 · 智慧教育与智能软件类",
        title="知迹",
        subtitle="面向大学生的 AI 学习私教与智能复习系统",
        proposition="核心命题：把一次学习回合做成一张可恢复、可拦截、可度量的状态图 —— 而不是不可控的聊天框",
        stack="技术栈　Python 3.12 · LangGraph · FastAPI + SSE · SQLite · Next.js 16 · React 19 · MCP",
        stats=[("284", "项自动测试"), ("35", "道检索题"), ("7", "个功能页面"), ("1", "个 SQLite 文件")])

    # 2 目录
    s = toc_slide(prs, ["背景与目标", "技术选型与架构", "三项关键实现", "实际使用与指标", "边界与下一步"])
    add_text(s, "结论先行：下一页给出三条结论，后面每页只负责证明其中一条",
             MARGIN_L, Inches(6.5), Inches(11.13), Inches(0.4),
             font=SANS, size=12, color=STONE)

    # 3 背景与目标
    split_slide(prs, "01 背景与目标",
        "三个时刻的共性缺口：产出无法复用，复习成本被迫翻倍",
        "一学期里的三个时刻", [
            ("上课中 · 讲义散在三处", "课程平台、聊天记录、手机相册各存一半，找一页要翻三个地方 → 不可检索"),
            ("写作业 · 问完就走", "答案留在对话里，同类问题下次从零再问 → 不可复用"),
            ("期末时 · 资料在、题没有", "只能重读讲义重翻记录，练习量不足 → 不可练"),
        ],
        "由此定义四个可验证目标", [
            ("G1　中断后可无损续跑", "关页或断网后，能从未完成处继续"),
            ("G2　答案可追溯到具体页", "引用带「第 N 页」，原件可打开核对"),
            ("G3　数据不被越权修改", "写操作在执行层被拦，确认后才落库"),
            ("G4　改动好坏可被量化", "固定考卷 + 基线，掉分自动拦截"),
        ], 3,
        note="问题不在「有没有工具」，而在「用完即弃」：讲义、结论、错因都没留下可复用的形态")

    # 4 技术选型
    table_slide(prs, "02 技术选型与架构",
        "选型原则是零运维、可离线、可评测，不是追新",
        ["层次", "选型", "承担什么", "为什么不选更常见的替代"],
        [
            ["编排", "LangGraph 显式状态图", "回合路由、工具循环、检查点、中断恢复", "自研状态机要重复实现断点与中断"],
            ["服务", "FastAPI + SSE", "流式下发步骤、回传人工确认结果", "同步框架难以边算边推，过程不可见"],
            ["存储", "SQLite · FTS5 + 向量表", "单文件承载全部业务数据与检索索引", "换 MySQL 会牺牲中文检索与离线演示"],
            ["检索", "trigram 全文 + 向量 + LIKE + 加权 RRF", "中文短词、同义异名、语义近似的多路覆盖", "纯向量漏专有名词与两字词"],
            ["前端", "Next.js 16 · App Router", "页面路由、流式渲染、交互态管理", "纯 SPA 处理流式与多页状态更绕"],
            ["工具协议", "MCP · 自写 stdio 客户端", "外部工具即插即用、跨宿主复用", "自研协议没有生态，也谈不上复用"],
        ], [1.1, 2.5, 3.6, 3.93], 4,
        note="结果：整条链路可离线跑通，测试与评测零 API 消耗 —— 这是能反复验证的前提")

    # 5 架构
    split_slide(prs, "02 技术选型与架构",
        "依赖单向朝内、回合画成图",
        "四层边界 · 依赖只朝内", [
            ("interfaces", "API 与流式接口，唯一允许依赖全部的一层"),
            ("application", "用例编排、端口定义、LangGraph 状态图"),
            ("domain", "纯函数：路由、切块、融合排序、排期、护栏"),
            ("infrastructure", "SQLite、模型调用、向量、文件解析"),
        ],
        "一次回合 · 四个节点", [
            ("route", "判意图：讲解、练习、规划、检索、计算"),
            ("plan", "复杂任务才规划，简单请求直接进模型"),
            ("agent", "模型推理，决定调哪个工具"),
            ("tools", "执行工具、回填结果，可回到 agent"),
        ], 5,
        note="每个节点执行后都落一次检查点 —— 这既是「关掉页面还能接着跑」，也是「写库前停下问你」的共同前提")

    # 6 实现① 检索
    card_grid_slide(prs, "03 关键实现 ① 检索",
        "四路召回同时补上「中文短词」与「同义异名」两类漏召回",
        [
            ("原查询全文", "trigram 分词，中文按字面也能命中", "局限：错一个字就漏"),
            ("同义 · 中英扩写", "本征值 → 特征值，queue → 队列", "局限：靠词典，推断有噪声"),
            ("两字词 LIKE", "「秩」「队列」进不了 trigram 索引", "局限：按覆盖度排序，精度中等"),
            ("向量语义", "字面全不同、意思相近仍能召回", "局限：无真实模型时不可靠"),
        ], 6,
        note="四条不是堆料：每条都对应一个实测过的漏召回场景。消融：关掉精排后 MRR 由 0.9714 降至 0.9571，命中数不变 —— 它改善的是排序，不是召回")

    # 7 实现② 执行边界
    split_slide(prs, "03 关键实现 ② 执行边界",
        "检查点负责「接着跑」，权限两层负责「改不了」",
        "可恢复的三个必要件", [
            ("检查点", "每步结束落一次状态，存在 SQLite，进程重启也不丢"),
            ("中断", "写操作前主动暂停，等用户确认"),
            ("恢复", "确认后按原路径续跑，不重放整段对话"),
        ],
        "权限两层：看得见 ≠ 跑得动", [
            ("讲解 · 检索", "看得见全部工具 · 执行层放行，写操作仍需确认"),
            ("练习", "看得见只读工具 · 执行层直接拒绝写操作"),
            ("进度", "看不见任何工具 · 执行层一律拦截"),
        ], 7,
        note="写操作流程：模型发起落库 → 图在中断点暂停 → 用户点确认 → 从检查点恢复并落库。两层权限缺一不可：只遮列表模型仍会说出被禁工具名而失败，只拦执行模型会反复重试")

    # 8 实现③ 质量门禁
    metrics_page(prs, "03 关键实现 ③ 质量门禁",
        "0.05 的容差把「感觉变差」变成「命令失败」",
        [("284 项", "自动化测试，离线零 API 消耗"),
         ("0.9714", "检索 Hit@3 · 35 题考卷"),
         ("1.0000", "意图准确率 · 15 句考卷"),
         ("0.05", "掉分红线，超出即非零退出")],
        "为什么不用大模型判分：同一模型既写又评会共享盲区 —— 它看不见的错误，复核时也看不见，甚至会把好答案改坏。\n"
        "所以判据全部用「确定性比对」：命中的是哪一篇、分到的是哪一类，机器都能校验；模型的判断只用于人工抽检。",
        "口径：检索评测用确定性词面向量，同版本任何人复跑结果一致；真实语义效果由接真模型单独确认",
        8)

    # 9 实际使用
    image_slide(prs, "04 实际使用与指标",
        "四步走完一个学习周期：入库、溯源、记错因、到期复习",
        "assets/ui-knowledge.png",
        "知识库页实拍：左侧学科目录树，中间资料列表，右侧可直接就着当前库提问",
        [("讲义入库", "PDF / Word / PPT / Excel 秒传，板书照片经视觉转写后入库"),
         ("就着资料提问", "回答标注出自哪份资料、第几页，原件可内联打开核对"),
         ("错题按错因归档", "概念混淆 / 步骤遗漏 / 条件误读 / 计算失误 / 表述不清"),
         ("到期自动复盘", "今日复习只列到期题与薄弱学科，日程负责什么时候做")],
        9,
        note="演示数据：7 个学科库 / 24 份资料 / 46 个可检索片段，全部带出处")

    # 10 边界
    table_slide(prs, "05 边界与下一步",
        "六项能力：两项达标、三项部分达成、一项未做",
        ["能力项", "状态", "依据 / 尚缺什么"],
        [
            ["中断可恢复", "达标", "状态图 + 检查点 + 中断恢复，均有回归测试"],
            ["检索准确性 / 可追溯", "达标", "35 题考卷，接真实向量 35/35，引用精确到页"],
            ["工具执行治理", "部分", "有双层权限与超时兜底，缺按参数与资源的细粒度约束"],
            ["长上下文管理", "部分", "有抽取式摘要与预算控制，缺关键事实外置成结构化笔记"],
            ["长期记忆", "部分", "按课程隔离、写入前确认，缺过期、替换与删除机制"],
            ["任务级成功率评测", "未做", "现有考卷只测「找到没 / 分类对不对」，不测「本次会话是否达成目标」"],
        ], [3.2, 1.3, 6.63], 10,
        note="下一步优先级：任务级成功率评测 → 记忆生命周期 → 更难的检索考卷；均可在现有门禁内验证")

    # 11 收束
    ending_page(prs, "让 AI 帮上忙，靠的不是它多聪明，而是每一步都留痕、能被拦住、也能被复算。",
        "我们把它做成一个可交付的系统：能力有边界，缺口自己说出来，改动由指标说了算。",
        [("下一步 · 任务级评测", "从「找到没」升级到「一次会话是否达成目标」"),
         ("下一步 · 记忆生命周期", "能改、能删、过期会失效，不再用错旧偏好"),
         ("下一步 · 更难的考卷", "题不难，后面改什么都看不出好坏")],
        "284 项自动测试 · 35 道检索题 · 7 个功能页面　|　赛道十三 智慧教育",
        11)

    prs.save(args.out)
    print(f"OK: 已生成 {args.out}（{len(prs.slides.__iter__.__self__._sldIdLst)} 页）")


if __name__ == "__main__":
    main()
