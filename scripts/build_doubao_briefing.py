#!/usr/bin/env python3
"""从「知迹答辩-插图交接文档.md」生成**一份自包含的、可直接粘给豆包 Agent 的提示词**。

为什么要有这个脚本：
- 16 页规格（标题 / 文案 / 配图 / 提示词 / 排版）原本散在一份 1200 行的大文档里，
  接手的人要自己拼装上下文。
- 这里把它压成**一段可以整段复制粘贴**的 briefing：项目背景 → 统一规范 → 16 页规格
  → 交付与验收，Agent 读完就能直接开工，不需要再问人。

用法：
    uv run python scripts/build_doubao_briefing.py
    uv run python scripts/build_doubao_briefing.py --check     # 只校验，不写文件
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SRC = Path("docs/作品集/参赛/知迹答辩-插图交接文档.md")
OUT = Path("docs/作品集/参赛/知迹答辩-豆包Agent交接提示词.md")

PAGES_WITH_FIG = ["p01", "p03", "p04", "p05", "p06", "p07", "p08", "p09",
                   "p10", "p11", "p12", "p13", "p14", "p16"]
PAGES_NO_FIG = ["p02", "p15"]

FILE_NAMES = {
    "p01": "封面-书桌场景", "p02": "目录-四份资料弧线", "p03": "三件事-三联静物",
    "p04": "一周-时间轴", "p05": "回合-四节点轨道", "p06": "工具-九宫格静物",
    "p07": "确认-半透明闸门", "p08": "检索-四路汇流漏斗", "p09": "出处-书与页签",
    "p10": "出题-双路径微缩", "p11": "复习-四轨汇环", "p12": "外部-核心球辐射",
    "p13": "隐形三件-静物三件套", "p14": "验证-体检桌面", "p15": "边界-六枚徽章",
    "p16": "收束-合上书桌",
}


def parse_pages(text: str) -> dict[str, dict]:
    """按页切块。

    注意：不能对全文做「前瞻式 split + 每段再抽字段」—— 那样同一页会被重复匹配。
    正确做法是**先切成互不重叠的页块**，再在**每块内**抽字段。
    """
    # 用行首锚点切：每页从 "### pNN " 开始，到下一个 "### pNN " 之前结束
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"^### (p\d\d)\b", text, re.M)]
    pages: dict[str, dict] = {}
    for i, (pos, pid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        sec = text[pos:end]

        def g(pat: str, _sec: str = sec) -> str:
            """取单行字段。

            ⚠️ 关键：这里**不能带 re.S** —— re.S 让 `.` 匹配换行，
            `(.+)` 就会一路吞掉整个页块（曾经把 66 行的 p08 块塞进 title 字段）。
            行内字段用 `[^\n]+` 表达，锚点用 re.M。
            """
            m = re.search(pat, _sec, re.M)
            return m.group(1).strip() if m else ""

        def code(heading: str, _sec: str = sec) -> str:
            """取某个小标题下的第一个围栏代码块内容。

            围栏内容用 ````(.*?)```` 配合"下一个字符不是反引号"的否定前瞻，
            保证不跨 ``` 边界（否则会一路吃到下一个代码块）。
            """
            m = re.search(
                heading + r"[^\n]*\n+```\n(.*?)(?<!`)\n```",
                _sec, re.S,
            )
            return m.group(1).strip() if m else ""

        pages[pid] = {
            "title": g(r"^\*\*标题\*\*：(.+)$"),
            "sub": g(r"^\*\*副标题\*\*：(.+)$"),
            "copy": code(r"\*\*核心文案"),
            "cn": code(r"\*\*中文提示词"),
            "en": code(r"\*\*英文提示词"),
            "lay": g(r"^\*\*排版建议\*\*：(.+)$"),
            "scene": g(r"- \*\*画面内容\*\*：(.+)"),
            "comp": g(r"- \*\*构图\*\*：(.+)"),
            "style": g(r"- \*\*风格\*\*：(.+)"),
            "ratio": g(r"- \*\*比例\*\*：(.+)"),
            "people": g(r"- \*\*人物/场景\*\*：(.+)"),
            "taboo": g(r"- \*\*禁忌\*\*：(.+)"),
        }
    return pages


def build(pages: dict[str, dict]) -> str:
    out: list[str] = []
    w = out.append

    w("""# 知迹答辩 PPT · 豆包 Agent 交接提示词

> **用法**：把下面「任务说明」起始的整段内容复制粘贴给豆包 Agent。
> 这份文档是**自包含**的 —— 背景、规范、16 页规格、验收标准全在里面，不需要再问人。
> 页序与内容是定稿，**不要另起一套**。

---

## 任务说明（从这里开始复制给 Agent）

你现在接手一个已经完成开发、正在做参赛交付的项目，负责**产出答辩 PPT 的全部插图**。

### 一、项目背景（决定你画什么）

**知迹** 是一个面向大学生的个人学习管理台，产品只做三件事：

1. **整理学习资料** —— 讲义、课件、笔记、拍照的板书传进来，按学科分好；PDF 能翻到第几页，
   图片由多模态模型转成文字。
2. **自动出错题** —— 按传进来的资料出题；上次做错的方向会多出几道变式题。
3. **结合知识库复习** —— 今天该练哪几题，按掌握度和到期时间排好；复习时能翻回原文那一页。

技术底座：**LangGraph 显式状态图**（`route → plan → agent ⇄ tools`）+ FastAPI + SQLite
+ Next.js 16。检索是**四路召回**（字面 FTS / 同义扩写 / 两字词 LIKE / 向量语义）→ 加权 RRF
→ 词面精排。工具侧做**双层最小权限**与**写入前人工确认**。

> ⚠️ **只画上面这三件事和它们的支撑，不要画成"AI 教育大平台"**。
> 也不要在图上写"沉淀""错因进脑子""过程没处查"这类说法 —— 那是已废弃的叙事。

### 二、你要交付什么

| # | 交付物 | 说明 |
| --- | --- | --- |
| 1 | **14 张插图**（p01、p03–p14、p16） | 16:9，**≥1920×1080**，PNG。页面 p02（目录）与 p15（边界）**不用配图**，用 PPT 排版与表格 |
| 2 | 插图存到 | `docs/作品集/参赛/知迹答辩/figures/`，命名 `p01-封面-书桌场景.png` 等（见每页规格） |
| 3 | 交付一份 | **每页的正文文案**（已给好，直接用）与**数字口径**（见第五节，数字一律不要画进图里） |

### 三、全篇统一视觉规范（每张图都必须满足）

| 项 | 规范 |
| --- | --- |
| **色调** | 明亮浅色调。底色米白 / 象牙 / 浅灰 / 淡蓝白。**不要深色背景**，不要暗调氛围 |
| **光线** | **统一右上方 45° 柔光**。大面积柔光，不要硬阴影、不要逆光剪影、不要戏剧性强光 |
| **投影** | 浅淡（淡度约 20–30%），**方向完全一致** |
| **色温** | 偏暖（奶白、浅木色）。不要冷蓝调，不要黄昏暖橙 |
| **材质** | 全部**哑光**：磨砂陶瓷、哑光纸、浅木、磨砂树脂、轻微磨砂金属。**不要**高光镜面、镀铬、彩虹渐变、霓虹 |
| **质感** | **3D 写实 / 摄影级**。不要扁平矢量、扁平插画、线框图、二维流程图 |
| **镜头** | 85mm 视角，浅景深，背景轻微虚化 |
| **构图** | 主体居中或居中偏一侧，另一侧留白；**负空间充足**，不把画面塞满 |
| **人物** | **全篇不出现人物**（p07 最多给一只手，且只到手腕、无袖口花纹）。人脸崩坏是答辩事故高发区 |
| **图上文字** | **只放该页的标题与副标题**，用思源黑体、笔画完整、字形端正。**除标题外不出现任何其他文字** |
| **数字** | 🚫 **图上一律不出现任何数字**（比例、分数、版本号、日期、页码都不行）。数字由 PPT 文本框叠加 —— 写错一位就是编造数据 |

### 四、16 页逐页规格

每一页给出：**标题 / 副标题**（直接印在图上）、**画面内容**（画什么）、
**可直接复制的生图提示词**、**排版建议**（这张图在 PPT 里怎么用）。

> **提示词使用方法**：复制「生图提示词」代码块 → 粘进豆包 → **选比例 16:9** → 生成。
> 每页出 3–4 张候选，挑最好的。**中文版优先**，效果不好再用英文版。
""")

    for pid in PAGES_WITH_FIG:
        p = pages[pid]
        w(f"\n---\n\n### {pid} · {p['title']}\n")
        w(f"**副标题（也印在图上）**：{p['sub']}\n")
        w(f"**画面内容**：{p['scene']}\n")
        w(f"**构图**：{p['comp']}\n")
        w(f"**风格**：{p['style']}\n")
        w(f"**人物/场景**：{p['people']}\n")
        if p["taboo"]:
            w(f"**禁忌**：{p['taboo']}\n")
        w(f"**生图提示词（复制这段，比例选 16:9）**\n\n```\n{p['cn']}\n```\n")
        w(f"**排版建议**：{p['lay']}\n")
        w(f"**文件命名**：`{pid}-{FILE_NAMES[pid]}.png`\n")

    w("""
---

### 五、每页的正文文案（**直接复制进 PPT 文本框**，数字也在这里）

> 文字由你在 PPT 里排，**不要画进图里**。每页正文不超过 120 字。
""")
    for pid in [f"p{i:02d}" for i in range(1, 17)]:
        p = pages[pid]
        if not p["copy"]:
            continue
        w(f"\n**{pid} · {p['title']}**\n\n```\n{p['copy']}\n```\n")

    w("""
### 六、怎么做才快且风格统一（关键技巧）

1. **一致性靠「以图生图」，不靠反复改提示词。**
   从第 3 页起，把**第 2 页你满意的成品当参考图上传**给豆包，再追加一句：
   `保持与参考图完全一致的光线方向、材质质感、色调与阴影角度`
   这是整套图看起来像一套的**最大杠杆**。
2. **不满意用「改」而不是「重新生成」。**
   豆包支持图像编辑：上传不满意的图 + 一句具体要求（"光线改成右上方 45 度"、
   "漏斗改成哑光陶瓷不要金属感"、"整体再亮一点"）。**一次只改一件事**。
3. **应急追加语**（贴在提示词末尾）：

| 情况 | 追加 |
| --- | --- |
| 图偏暗 / 偏冷 | `brighten the image, warm up the color temperature, keep shadows very soft` |
| 标题有错字 / 缺笔画 | `the Chinese headline must be rendered with perfectly correct, complete characters` |
| 误生出多余文字 | `remove everything except the specified headline, no other text or numbers` |
| 质感不够立体 | `more pronounced three-dimensional form, real material texture, stronger sense of depth` |
| 构图太挤 | `more breathing room around the subject, wider composition` |
| 背景不干净 | `clean seamless background, remove all distracting elements` |
| 标题压住主体 | `move the headline to the top edge with generous empty margin, do not overlap` |

4. **每页出 3–4 张候选再挑**。同一个提示词多跑几次是正常的。

### 七、交付前自检（每张图都要过）

- [ ] **标题文字与规格完全一致** —— 逐字核对，不看"像不像"
- [ ] 标题无缺笔画、无错字、无变形字符
- [ ] **图上没有任何数字**
- [ ] 主体完整，四边没被裁
- [ ] 整体浅色调，**光从右上来**，投影柔和
- [ ] 材质是哑光的（无镜面 / 镀铬 / 霓虹）
- [ ] 无人物（p07 最多一只手）
- [ ] 与前面几页的光线与色调**接得上**

### 八、完成后回报

1. 14 张图已存到 `docs/作品集/参赛/知迹答辩/figures/`，按上表命名
2. 逐页一句说明：用了哪张候选、标题是否需要人工微调
3. 有任何一页反复生成都不达标的，**明确说哪一页、卡在哪** —— 不要用相近的结果糊过去

### 九、几条硬约束（别踩）

- **数字不画进图**。检索 35 题 / Hit@3 = MRR = 0.9714 / 消融 0.9571 / 284 项测试 /
  意图 15 句准确率 1.0 / 检索权重 1.0、0.5、0.8 / 掌握度 0–100 / 四档 ±10、±3、±5、±10 /
  间隔 0、1、3、7 天 / 难度分档 40、80 / 2048 维 —— **全部只在 PPT 文本框里出现**。
- **不要改项目代码**。你的产出只有插图（和可能的排版建议），`src/`、`frontend/`、`tests/`
  一律不动。
- **不要重新设计页序**。16 页的结构已定稿（① 它是什么 → ② 三件事怎么被做稳 →
  ③ 看不见的三件事 + 怎么证明 → ④ 边界与收束）。
- **p02 与 p15 不出图**。p02 用 PPT 卡片排版，p15 用 PPT 原生表格。
- **表格一律用 PPT 原生表格**，不要用生图做表格。

---

## 附：项目事实与数字口径（写文案时对照，别写错）

| 项 | 口径 |
| --- | --- |
| 检索评测 | 35 题 / 21 篇语料，Hit@3 = MRR = **0.9714** |
| 检索 · 接真实向量 | **35 / 35** 全中 |
| 消融 · 关掉词面精排 | MRR **0.9714 → 0.9571** |
| 意图分类 | 15 句，准确率 **1.0** |
| 自动测试 | **284 passed**（全 Mock，零 API 消耗） |
| 检索权重 | 原查询 1.0 / 同义扩写 0.5 / 两字词 0.8 / 向量 1.0，RRF k=60 |
| 精排权重 | 原查询覆盖 0.50 / 扩写覆盖 0.15 / 标题命中 0.35 |
| 上下文 | 24 条上限 · 保留最近 14 条 · 抽取式摘要 ≤ 240 字 |
| 掌握度 | 0–100；自评 again −10 / hard −3 / good +5 / easy +10，间隔 0 / 1 / 3 / 7 天 |
| 出题难度 | <40 基础 / <80 进阶 / ≥80 迁移 |
| 向量维度 | 2048（智谱 embedding-3） |
| 工具 | 9 个：knowledge_search / mistake_search / save_note / read_file / write_file / list_files / web_search / fetch_url / calculator |

**边界（必须诚实交代，不得写成已完成）**：单用户无鉴权；未做任务级成功率评测、
在线监控聚合面板、Reranker 重排、反思式自我批判。

（复制到这里结束）""")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    text = SRC.read_text(encoding="utf-8")
    pages = parse_pages(text)

    missing = [pid for pid in [f"p{i:02d}" for i in range(1, 17)] if pid not in pages]
    if missing:
        print(f"! 源文档缺页：{missing}")
        return 1
    for pid, p in pages.items():
        for k in ("title", "cn", "en", "lay"):
            if not p[k]:
                print(f"! {pid} 缺字段：{k}")
                return 1

    briefing = build(pages)
    if args.check:
        print(f"✓ 校验通过，briefing {len(briefing)} 字符 / {len(briefing.splitlines())} 行")
        return 0

    OUT.write_text(briefing, encoding="utf-8")
    print(f"✓ 写入 {OUT}（{len(briefing) / 1024:.1f} KB，{len(briefing.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
