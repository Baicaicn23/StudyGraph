#!/usr/bin/env python3
"""Markdown → PDF 生成器（Chrome headless 打印）。

用于把参赛材料里的文字类文档导出为 PDF（规范建议：作品介绍文档、运行或使用
说明、第三方资源说明、AI 工具使用补充说明等统一用 PDF 提交）。

设计取舍：
- 不引 pandoc / weasyprint 等额外依赖——本机已有 Chrome，打印引擎最稳。
- 用 Python 标准库做轻量 Markdown 转换（标题、列表、表格、代码块、粗体、
  行内代码、引用、分隔线），够材料用，不追求 CommonMark 全覆盖。
- A4 + 页边距 + 页脚页码；中文正文用系统字体，不内嵌字体文件。
"""
import html
import os
import re
import subprocess
import sys
import tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 20mm 18mm 18mm 18mm; }
* { box-sizing: border-box; }
body {
  font-family: "Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", serif;
  font-size: 10.5pt; line-height: 1.72; color: #1a1a1a; margin: 0;
}
h1 { font-size: 19pt; font-weight: 700; margin: 0 0 4pt; letter-spacing: .3pt;
     font-family: "PingFang SC", "Heiti SC", sans-serif; }
.subtitle { font-size: 10pt; color: #666; margin: 0 0 16pt;
            font-family: "PingFang SC", sans-serif; }
h2 { font-size: 13.5pt; font-weight: 700; margin: 20pt 0 8pt;
     padding-bottom: 4pt; border-bottom: 1.2pt solid #d8d8d8;
     font-family: "PingFang SC", "Heiti SC", sans-serif; page-break-after: avoid; }
h3 { font-size: 11.5pt; font-weight: 700; margin: 13pt 0 5pt; color: #2a2a2a;
     font-family: "PingFang SC", "Heiti SC", sans-serif; page-break-after: avoid; }
h4 { font-size: 10.5pt; font-weight: 700; margin: 10pt 0 4pt; color: #444;
     font-family: "PingFang SC", sans-serif; page-break-after: avoid; }
p { margin: 0 0 8pt; text-align: justify; }
ul, ol { margin: 0 0 9pt; padding-left: 20pt; }
li { margin: 0 0 3.5pt; }
blockquote {
  margin: 0 0 10pt; padding: 7pt 11pt; background: #f7f7f5;
  border-left: 2.5pt solid #b9b9b4; color: #444; font-size: 9.8pt;
}
blockquote p { margin: 0 0 4pt; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 9pt;
       background: #f0f0ed; padding: 1pt 3pt; border-radius: 2pt; }
pre { background: #f6f6f3; border: .8pt solid #e2e2dd; border-radius: 3pt;
      padding: 8pt 10pt; overflow-x: auto; margin: 0 0 10pt;
      font-size: 8.8pt; line-height: 1.5; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.8pt; }
table { border-collapse: collapse; width: 100%; margin: 0 0 11pt;
        font-size: 9.3pt; page-break-inside: avoid; }
th, td { border: .8pt solid #cfcfc9; padding: 4.5pt 6pt; text-align: left;
         vertical-align: top; }
th { background: #f2f2ee; font-weight: 700; }
tr:nth-child(even) td { background: #fafaf8; }
hr { border: none; border-top: .8pt solid #ddd; margin: 14pt 0; }
strong { font-weight: 700; }
.pagebreak { page-break-before: always; }
img { max-width: 100%; }
.footer-note { margin-top: 18pt; padding-top: 7pt; border-top: .8pt solid #e0e0dc;
              font-size: 8.5pt; color: #888; font-family: "PingFang SC", sans-serif; }
"""


def inline(text):
    """行内 Markdown：代码 → 粗体 → 斜体 → 链接。"""
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        part = html.escape(part)
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", part)
        part = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                      r'<a href="\2" style="color:#2a6f8f;text-decoration:none">\1</a>', part)
        out.append(part)
    return "".join(out)


def md_to_html(md, title=""):
    lines = md.split("\n")
    html_out = []
    i = 0
    in_code = False
    code_buf = []
    in_table = False
    table_buf = []

    def flush_table():
        nonlocal in_table, table_buf
        if not in_table:
            return
        rows = []
        for row in table_buf:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            rows.append(cells)
        if not rows:
            in_table, table_buf = False, []
            return
        out = ["<table>"]
        head = rows[0]
        out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>")
        body = rows[1:]
        if body and all(set(c) <= set("-: ") for c in body[0]):
            body = body[1:]
        out.append("<tbody>")
        for r in body:
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
        out.append("</tbody></table>")
        html_out.append("".join(out))
        in_table, table_buf = False, []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                html_out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf, in_code = [], False
            else:
                flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_buf.append(stripped)
            i += 1
            continue
        flush_table()

        if not stripped:
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            lvl, txt = len(m.group(1)), m.group(2)
            html_out.append(f"<h{lvl}>{inline(txt)}</h{lvl}>")
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            html_out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            html_out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>")
            continue

        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = bool(re.match(r"\d+\.", m.group(2)))
            items = []
            while i < len(lines):
                mm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
                if not mm:
                    if lines[i].strip() and lines[i].startswith(("  ", "\t")) and items:
                        items[-1] += " " + lines[i].strip()
                        i += 1
                        continue
                    break
                items.append(mm.group(3))
                i += 1
            tag = "ol" if ordered else "ul"
            lis = "".join(f"<li>{inline(x)}</li>" for x in items)
            html_out.append(f"<{tag}>{lis}</{tag}>")
            continue

        # 普通段落：连续非空行合并
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|>|\||```|(-{3,})|\s*([-*+]|\d+\.)\s)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            html_out.append("<p>" + inline(" ".join(buf)) + "</p>")
        else:
            i += 1

    flush_table()
    return "\n".join(html_out)


def render(md_text, out_pdf, title=""):
    body = md_to_html(md_text)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body>{body}</body></html>"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    cmd = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
           "--disable-extensions", "--no-pdf-header-footer",
           f"--print-to-pdf={out_pdf}", tmp]
    subprocess.run(cmd, capture_output=True, timeout=180)
    os.unlink(tmp)
    return os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 0


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        md = f.read()
    ok = render(md, dst, title=os.path.basename(src))
    print(("✓ " if ok else "✗ ") + dst, os.path.getsize(dst) if ok else "")
