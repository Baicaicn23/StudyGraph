#!/usr/bin/env python3
"""生成知迹答辩 PPT 的 02–16 页 .slide 源文件（v6 叙事版）。

**v6 的三个变化**
1. **先情景再技术**：p02 是一周时间轴（情景代入），p03 才点出真问题，
   p04 才抽象成三道坎。技术段之前先建立代入感。
2. **代码 → 示意图**：技术段每页左边是**真实代码**（带 `文件:行号`），
   右边是把这段代码画成的示意图。读者能自己验证，不是听讲。
3. **一关一关过**：p06–p12 是同一条链上的七站（看得懂意图 → 看得准资料 →
   管得住工具 → 说得清出处 → 练得下去 → 记得住 → 省得下来），
   每关都是上一关逼出来的，不是模块罗列。

**为什么用 % 格式化而不是 f-string**
slidep 的 DSL 里到处是 JSX 花括号（``style={{ ... }}``）。f-string 要求把每个
``{`` 写成 ``{{``，几百行下来极易写错一个就整文件语法错。
``%`` 格式化只认 ``%s``，**完全不碰花括号** —— 这里唯一安全的做法。

**布局纪律（踩过的坑）**
- **示意图一律用 flex 相对布局**，不要用绝对定位画节点链 —— 绝对定位算坐标
  极易溢出容器，且改一个数字要重算全链。
- JSX 文本里裸的 ``{`` ``}`` ``<`` ``>`` 必须转成 HTML 实体，否则被当表达式/标签。

用法：
    uv run python scripts/build_slides.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

SLIDES_DIR = Path("docs/作品集/参赛/知迹答辩/slides")

# ---------------------------------------------------------------- 母版

MAST_HEAD = """<Slide style={{ width: 1280, height: 720, position: 'relative', background: '#FFFFFF', fontFamily: 'PingFang SC, Hiragino Sans GB, sans-serif' }}>
    <Box style={{ position: 'absolute', top: 0, left: 0, width: 1280, height: 56, background: '#1E4FA8' }} />
    <Box style={{ position: 'absolute', top: 0, left: 40, height: 56, flexDirection: 'row', alignItems: 'center', gap: 14 }}>
        <Text style={{ fontSize: 17, color: '#FFFFFF', fontWeight: 'bold' }}>知迹</Text>
        <Box style={{ width: 1, height: 16, background: '#5B8FD9' }} />
        <Text style={{ fontSize: 15, color: '#C9DDF5' }}>Agent 工程化实践</Text>
    </Box>
    <Box style={{ position: 'absolute', top: 0, right: 40, height: 56, flexDirection: 'row', alignItems: 'center' }}>
        <Text style={{ fontSize: 14, color: '#A9C6EF' }}>%(section)s</Text>
    </Box>
"""

MAST_TITLE = """    <Box style={{ position: 'absolute', top: 56, left: 40, width: 1200, height: 92, flexDirection: 'column', justifyContent: 'center', gap: 8 }}>
        <Text style={{ fontSize: 34, fontWeight: 'bold', color: '#0E3F8C' }}>%(title)s</Text>
        <Text style={{ fontSize: 19, color: '#4A5568' }}>%(subtitle)s</Text>
    </Box>
"""

MAST_CONCL = """
    <Box style={{ position: 'absolute', top: 648, left: 40, width: 1200, height: 56, background: '#E8EFF8', borderTop: '2px solid #1E4FA8', flexDirection: 'row', alignItems: 'center', padding: '0 20px', gap: 12 }}>
        <Box style={{ width: 4, height: 24, background: '#1E4FA8' }} />
        <Text style={{ fontSize: 19, color: '#0E3F8C', fontWeight: 'bold' }}>%(conclusion)s</Text>
    </Box>

    <Box style={{ position: 'absolute', bottom: 8, left: 40, flexDirection: 'row', alignItems: 'center' }}>
        <Text style={{ fontSize: 14, color: '#8B97A8' }}>知迹 · 赛道十三 · 智慧教育</Text>
    </Box>
    <Box style={{ position: 'absolute', bottom: 8, right: 40, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Text style={{ fontSize: 15, color: '#1E4FA8', fontWeight: 'bold' }}>%(page)s</Text>
        <Text style={{ fontSize: 14, color: '#8B97A8' }}>/ 16</Text>
    </Box>
</Slide>
"""


def master(page: int, section: str, title: str, subtitle: str, body: str, conclusion: str) -> str:
    """A 顶条 + B 标题块 + C 内容 + 结论条 + D 页脚。

    尺寸契约：顶条 0-56 / 标题块 56-148 / 内容 156-636 / 结论条 648-704 / 页脚 704-720
    """
    head = MAST_HEAD % {"section": section}
    title_block = MAST_TITLE % {"title": title, "subtitle": subtitle}
    tail = MAST_CONCL % {"conclusion": conclusion, "page": f"{page:02d}"}
    return head + title_block + "\n" + body + "\n" + tail


def esc(text: str) -> str:
    """JSX 文本转义：裸的 { } < > 会被当表达式/标签。"""
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("{", "&#123;").replace("}", "&#125;"))


def code_block(path: str, lines: list[str]) -> str:
    """左侧真实代码块：深色底 + 等宽字体 + 文件:行号。

    刻意用深色 —— 代码块是"证据"，深底与浅底的对比让它一眼可辨，
    也符合论文图里「代码区用深底」的惯例。
    """
    body = "<br />".join(esc(ln) for ln in lines)
    return """<Box style={{ background: '#1B2A44', borderRadius: 8, padding: 13, gap: 8, height: '100%%' }}>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Box style={{ width: 8, height: 8, borderRadius: 4, background: '#5B8FD9' }} />
                <Text style={{ fontSize: 14, color: '#8FB4E8', fontFamily: 'SF Mono, Menlo, monospace' }}>%(path)s</Text>
            </Box>
            <Text style={{ fontSize: 13, color: '#E3ECFA', lineHeight: 1.52, fontFamily: 'SF Mono, Menlo, monospace', flex: 1 }}>%(body)s</Text>
        </Box>""" % {"path": path, "body": body}


def gate_badge(n: int, label: str) -> str:
    """右上角「第 N 关」徽标 —— 让连续七页在视觉上是同一条链。"""
    return """<Box style={{ position: 'absolute', top: 72, right: 40, background: '#1E4FA8', borderRadius: 6, padding: '7px 14px', flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>第 %(n)d 关</Text>
        <Box style={{ width: 1, height: 14, background: '#5B8FD9' }} />
        <Text style={{ fontSize: 15, color: '#C9DDF5' }}>%(label)s</Text>
    </Box>""" % {"n": n, "label": label}


def split_code_diagram(code: str, diagram: str, code_w: int = 460) -> str:
    """技术段统一版式：左代码 + 右示意图。"""
    return """    <Box style={{ position: 'absolute', top: 168, left: 40, width: 1200, height: 468, flexDirection: 'row', gap: 20 }}>
        <Box style={{ width: %(cw)d, height: '100%%' }}>%(code)s</Box>
        <Box style={{ flex: 1, height: '100%%' }}>%(diagram)s</Box>
    </Box>""" % {"cw": code_w, "code": code, "diagram": diagram}


def gate_page(page: int, n: int, label: str, section: str, title: str, subtitle: str,
              code: str, diagram: str, conclusion: str, code_w: int = 460) -> str:
    """技术段统一版式：徽标 + 左代码 + 右示意图 + 结论条。"""
    body = gate_badge(n, label) + "\n" + split_code_diagram(code, diagram, code_w)
    return master(page, section, title, subtitle, body, conclusion)


def node(text: str, bg: str, fg: str, w: int = 104, h: int = 56, size: int = 19) -> str:
    """状态图节点（flex 链中的一节）。"""
    return """<Box style={{ width: %(w)d, height: %(h)d, background: '%(bg)s', border: '2px solid #1E4FA8', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: %(size)d, fontWeight: 'bold', color: '%(fg)s' }}>%(text)s</Text>
            </Box>""" % {"text": text, "bg": bg, "fg": fg, "w": w, "h": h, "size": size}


def arrow_h(color: str = "#1E4FA8", w: int = 20) -> str:
    """横向箭头（flex 链中的一节）。"""
    return """<Box style={{ width: %(w)d, height: 22, flexDirection: 'row', alignItems: 'center' }}>
                <Box style={{ flex: 1, height: 3, background: '%(color)s' }} />
                <Box style={{ width: 9, height: 9, background: '%(color)s', borderRadius: 2, transform: 'rotate(45deg)' }} />
            </Box>""" % {"color": color, "w": w}


def arrow_v(color: str = "#3D7BD9", h: int = 30) -> str:
    """纵向箭头。"""
    return """<Box style={{ width: 22, height: %(h)d, alignItems: 'center', justifyContent: 'center' }}>
                <Box style={{ width: 3, height: %(ah)d, background: '%(color)s' }} />
                <Box style={{ width: 9, height: 9, background: '%(color)s', borderRadius: 2, transform: 'rotate(45deg)' }} />
            </Box>""" % {"color": color, "h": h, "ah": h - 12}


# ---------------------------------------------------------------- p02 情景

def p02() -> str:
    """一周时间轴：情景代入。"""
    days = [
        ("周一", "传讲义", "《高数》《四级》《数据结构》<br />三份资料进知识库", "#1E4FA8"),
        ("周三", "提个问", "「拉格朗日中值定理的条件是什么」<br />要求给出处", "#3D7BD9"),
        ("周五", "出点题", "按讲义出题，昨天做错的方向<br />多出几道变式题", "#0E3F8C"),
        ("周日", "练一下", "打开今日复习做三道<br />自评完，明天的题自己排好", "#4FB3A4"),
    ]
    parts = []
    for day, act, desc, color in days:
        parts.append("""<Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 10 }}>
                <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Box style={{ width: 52, height: 30, background: '%s', borderRadius: 4, justifyContent: 'center', alignItems: 'center' }}>
                        <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>%s</Text>
                    </Box>
                    <Text style={{ fontSize: 25, fontWeight: 'bold', color: '#0E3F8C' }}>%s</Text>
                </Box>
                <Box style={{ height: 2, background: '#E8EFF8' }} />
                <Text style={{ fontSize: 16, color: '#4A5568', lineHeight: 1.75 }}>%s</Text>
            </Box>""" % (color, day, act, desc))

    body = """    <Box style={{ position: 'absolute', top: 172, left: 40, width: 1200, height: 336, flexDirection: 'column', gap: 20 }}>
        <Box style={{ flexDirection: 'row', alignItems: 'center', height: 30 }}>
            <Box style={{ width: 10, height: 10, borderRadius: 5, background: '#1E4FA8' }} />
            <Box style={{ flex: 1, height: 3, background: '#C9DDF5' }} />
            <Box style={{ width: 10, height: 10, borderRadius: 5, background: '#1E4FA8' }} />
            <Box style={{ flex: 1, height: 3, background: '#C9DDF5' }} />
            <Box style={{ width: 10, height: 10, borderRadius: 5, background: '#1E4FA8' }} />
            <Box style={{ flex: 1, height: 3, background: '#C9DDF5' }} />
            <Box style={{ width: 10, height: 10, borderRadius: 5, background: '#1E4FA8' }} />
        </Box>
        <Box style={{ flex: 1, flexDirection: 'row', gap: 20 }}>
            %s
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 528, left: 40, width: 1200, height: 92, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, flexDirection: 'row', alignItems: 'center', padding: '0 24px', gap: 18 }}>
        <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#0E3F8C' }}>四件事，四个动作：</Text>
        <Text style={{ fontSize: 18, color: '#4A5568', flex: 1 }}>资料进得来　·　问题问得清　·　题目出得准　·　复习排得对</Text>
        <Text style={{ fontSize: 16, color: '#8B97A8' }}>听着都是小事 —— 下一页看第三件为什么最难</Text>
    </Box>""" % "\n".join(parts)
    return master(
        2, "情景 · 一个学生的普通一周", "一个学生的一周，三个动作",
        "先不谈技术。这是知迹被使用的样子 —— 四个动作，一周",
        body,
        "这四件事看着都顺，但第三件有个说不清的问题 —— 下一页说它",
    )


# ---------------------------------------------------------------- p03

def p03() -> str:
    """点出真问题：不是答不出来，是答错了你不知道。"""
    body = """    <Box style={{ position: 'absolute', top: 168, left: 40, width: 1200, height: 460, flexDirection: 'row', gap: 20 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 24, gap: 14 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#4A5568' }}>前两件：做个脚本也能做</Text>
            <Box style={{ gap: 12, marginTop: 4 }}>
                <Box style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
                    <Box style={{ width: 8, height: 8, borderRadius: 4, background: '#8B97A8', marginTop: 8 }} />
                    <Text style={{ fontSize: 17, color: '#1A2230', lineHeight: 1.65, flex: 1 }}>存资料 —— 上传、分类、抽文本，没有 Agent 也能做</Text>
                </Box>
                <Box style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
                    <Box style={{ width: 8, height: 8, borderRadius: 4, background: '#8B97A8', marginTop: 8 }} />
                    <Text style={{ fontSize: 17, color: '#1A2230', lineHeight: 1.65, flex: 1 }}>出题 —— 按模板抽关键词组题，能凑出题，但凑不出好题</Text>
                </Box>
            </Box>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 16, justifyContent: 'center' }}>
                <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                    这两件事的共同点：<b>做错了你能看出来</b>。文件没进去、题目明显跑题，你自己一眼就知道。
                </Text>
            </Box>
        </Box>

        <Box style={{ flex: 1, background: '#E8EFF8', border: '2px solid #1E4FA8', borderRadius: 8, padding: 24, gap: 14 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#0E3F8C' }}>第三件：绕不开 Agent</Text>
            <Text style={{ fontSize: 16, color: '#4A5568', lineHeight: 1.7 }}>
                题要「基于你的资料」，错题要「影响难度」，复习要「按掌握度排」——
                一旦要读懂你的资料并据此判断，就绕不开一个会自己推理的东西。
            </Text>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #1E4FA8', borderRadius: 6, padding: 18, justifyContent: 'center', gap: 10 }}>
                <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#D9534F' }}>但它带来了一个新问题</Text>
                <Text style={{ fontSize: 18, color: '#1A2230', lineHeight: 1.7 }}>
                    前两件事做错了你能看出来，<b>这件事做错了你不知道</b>。
                </Text>
                <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.65 }}>
                    它答得很流畅、引用了一堆资料，看着全对 —— 但可能整段都是编的。
                </Text>
            </Box>
        </Box>
    </Box>"""
    return master(
        3, "情景 · 转折", "第三件事最难：凭什么它就比前两个准",
        "答案不是「更聪明的模型」，而是「一套能被检查的流程」",
        body,
        "所以难的从来不是 AI 会不会答，而是答了之后你敢不敢信 —— 这才是要解决的问题",
    )


# ---------------------------------------------------------------- p04

def p04() -> str:
    """三道坎 + 失效场景。"""
    rows = [
        ("可恢复", "会话崩在第 7 步，前 6 步的检索与工具调用全部作废",
         "状态在消息列表里，进程一挂就没了", "LangGraph 的 checkpointer 正是为此刻态而设计"),
        ("可拦截", "模型幻觉出一个被禁工具名并真的发起调用",
         "只在 schema 层裁剪工具，执行层没有第二道判定", "schema 层不够 —— 模型能「说出」工具名并失败"),
        ("可度量", "改了一行检索权重，重跑一次看着更好了",
         "没有固定考卷，波动和真实提升混在一起", "τ-bench 实测 pass^1 ≈ 61%、pass^8 &lt; 25%"),
    ]
    parts = []
    for i, (name, scene, why, evidence) in enumerate(rows, 1):
        parts.append("""<Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 22, gap: 11, justifyContent: 'center' }}>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <Box style={{ width: 46, height: 46, background: '#1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 24, color: '#FFFFFF', fontWeight: 'bold' }}>%d</Text>
                </Box>
                <Text style={{ fontSize: 27, fontWeight: 'bold', color: '#0E3F8C' }}>%s</Text>
            </Box>
            <Box style={{ height: 2, background: '#E8EFF8' }} />
            <Text style={{ fontSize: 16, color: '#1A2230', lineHeight: 1.55 }}>失效场景：%s</Text>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.5 }}>为什么难：%s</Text>
            <Box style={{ background: '#E8EFF8', borderRadius: 5, padding: '10px 12px' }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.6 }}>%s</Text>
            </Box>
        </Box>""" % (i, name, scene, why, evidence))

    body = """    <Box style={{ position: 'absolute', top: 168, left: 40, width: 1200, height: 456, flexDirection: 'row', gap: 20 }}>
        %s
    </Box>

    <Box style={{ position: 'absolute', top: 636, left: 40, width: 1200, height: 60, background: '#E8EFF8', borderRadius: 6, flexDirection: 'row', alignItems: 'center', padding: '0 20px', gap: 12 }}>
        <Text style={{ fontSize: 18, color: '#0E3F8C', fontWeight: 'bold' }}>这三件事都不是模型能力问题，是系统设计问题</Text>
        <Text style={{ fontSize: 17, color: '#4A5568', flex: 1 }}>—— 下面跟着一次提问，看它依次怎么过这七关</Text>
    </Box>""" % "\n".join(parts)
    return master(
        4, "问题 · 三道坎", "可信比聪明重要：可恢复、可拦截、可度量",
        "每道坎背后都是一个具体的、会真实发生的失效场景",
        body,
        "知迹选了一个具体领域，把这三道坎都当作必须用工程手段解决的问题",
    )


# ---------------------------------------------------------------- p05

def p05() -> str:
    """技术选型：为什么用 LangGraph。"""
    code = code_block("application/graph.py:311-320", [
        "builder = StateGraph(StudyState)",
        "builder.add_node('route', route_node)",
        "builder.add_node('plan',  plan_node)",
        "builder.add_node('agent', agent_node)",
        "builder.add_node('tools', tools_node)",
        "builder.add_edge(START, 'route')",
        "builder.add_edge('route', 'plan')",
        "builder.add_edge('plan',  'agent')",
        "builder.add_conditional_edges(",
        "    'agent', should_continue,",
        "    {'tools': 'tools', END: END})",
        "builder.add_edge('tools', 'agent')",
    ])
    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>画出来的回合</Text>
        <Text style={{ fontSize: 14, color: '#8B97A8' }}>上面那段代码编译后长这样</Text>

        <Box style={{ flex: 1, flexDirection: 'column', gap: 8, justifyContent: 'center' }}>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                <Box style={{ width: 78, height: 44, background: '#F7F9FC', border: '2px solid #1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 14, fontWeight: 'bold', color: '#1E4FA8' }}>START</Text>
                </Box>
                %s
                %s
                %s
                %s
                %s
                %s
                <Box style={{ width: 70, height: 44, background: '#F7F9FC', border: '2px solid #1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 14, fontWeight: 'bold', color: '#1E4FA8' }}>END</Text>
                </Box>
            </Box>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 26 }}>
                %s
                <Box style={{ width: 120, height: 54, background: '#0E3F8C', border: '2px solid #1E4FA8', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#FFFFFF' }}>tools</Text>
                </Box>
                <Box style={{ flex: 1, height: 34, border: '2px solid #3D7BD9', borderRadius: 6, background: '#E8EFF8', justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#0E3F8C', fontWeight: 'bold' }}>tools → agent 回到模型（结果回填）</Text>
                </Box>
            </Box>
        </Box>

        <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 5 }}>
            <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#0E3F8C' }}>为什么不用 while 循环自己写</Text>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.6 }}>检查点、循环上限、中断恢复、条件跳转这四件事，用框架写是十几行；自己写是几百行状态管理，而且每加一个能力都要重写一遍。</Text>
        </Box>
    </Box>""" % (
        arrow_h(w=18),
        node("route", "#1E4FA8", "#FFFFFF", 100),
        arrow_h(w=18),
        node("plan", "#1E4FA8", "#FFFFFF", 100),
        arrow_h(w=18),
        node("agent", "#0E3F8C", "#FFFFFF", 100),
        arrow_v(h=26),
    )
    body = split_code_diagram(code, diagram, 460)
    return master(
        5, "解法 · 技术选型", "为什么用 LangGraph，而不是自己写个 while 循环",
        "状态、检查点、中断、条件跳转 —— 这四件事是选型的全部理由",
        body,
        "框架负责编排，决策留给自己 —— 我要的是控制权，不是省事",
    )


# ---------------------------------------------------------------- 七关

def p06() -> str:
    """第一关 · 看得懂意图。"""
    code = code_block("application/routing.py:61 / :132", [
        "def classify(text: str) -> tuple[str, float]:",
        "    # 判断意图，返回 (意图, 置信度)",
        "    ...",
        "    return best_intent, best_score",
        "",
        "AGENT_PROFILES: dict[str, AgentProfile] = {",
        "    'tutor':    AgentProfile(...),",
        "    'practice': AgentProfile(...),   # 只读",
        "    'progress': AgentProfile(",
        "        deny_all=True, ...),       # 一个工具都不给",
        "}",
    ])
    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>六类意图，四个角色</Text>
        <Box style={{ flex: 1, flexDirection: 'row', gap: 12 }}>
            <Box style={{ width: 236, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 12, gap: 8 }}>
                <Text style={{ fontSize: 14, color: '#8B97A8' }}>classify(text)</Text>
                <Box style={{ gap: 5, marginTop: 4 }}>
                    <Text style={{ fontSize: 15, color: '#1A2230' }}>讲解　检索　练习</Text>
                    <Text style={{ fontSize: 15, color: '#1A2230' }}>进度　计算　闲聊</Text>
                </Box>
                <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 4, padding: 8, justifyContent: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#0E3F8C' }}>识别错了，后面全是错的</Text>
                </Box>
            </Box>
            <Box style={{ width: 24, justifyContent: 'center', alignItems: 'center' }}>
                <Box style={{ width: 18, height: 3, background: '#1E4FA8' }} />
                <Box style={{ width: 9, height: 9, background: '#1E4FA8', borderRadius: 2, transform: 'rotate(45deg)' }} />
            </Box>
            <Box style={{ flex: 1, gap: 8 }}>
                <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 5, padding: 10, gap: 2 }}>
                    <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>tutor 讲解</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>可读可写</Text>
                </Box>
                <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 5, padding: 10, gap: 2 }}>
                    <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>practice 练习</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>只读，不给写工具</Text>
                </Box>
                <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 5, padding: 10, gap: 2 }}>
                    <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>progress 进度</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>deny_all，一个工具都没有</Text>
                </Box>
            </Box>
        </Box>
        <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 12, gap: 4 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>顺带解决了第三关的一半</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>权限跟着角色走 —— 讲题的角色不给写文件的工具，练题的角色只给读的工具</Text>
        </Box>
    </Box>"""
    return gate_page(
        6, 1, "看得懂意图", "解法 · 一次提问，七道关",
        "第一关 · 看得懂意图",
        "先判这是哪一类问题 —— 判错了，检索和权限都会跟着错",
        code, diagram,
        "意图识别不是「小功能」，它是后面所有权限与检索策略的前提",
    )


def p07() -> str:
    """第二关 · 看得准资料。"""
    code = code_block("infrastructure/knowledge.py:643", [
        "rankings = [",
        "    self._search_fts(cleaned, ...),      # 字面",
        "    self._search_expanded(cleaned, ...), # 扩写",
        "    self._search_like(cleaned, ...),     # 短词",
        "    self._search_vectors(cleaned, ...),  # 向量",
        "]",
        "# 权重：原查询字面命中最高，扩写路按推断降权",
        "weights = [1.0, self.expansion_weight, 0.8, 1.0]",
        "fused = rrf_fuse(rankings, k=self.rrf_k,",
        "               weights=weights)[:pool]",
    ])
    chans = [
        ("字面 FTS", "trigram", "1.0", "#1E4FA8", "100%"),
        ("同义扩写", "中英对照", "0.5", "#3D7BD9", "50%"),
        ("短词 LIKE", "两字兜底", "0.8", "#E5B54B", "80%"),
        ("向量语义", "零字面", "1.0", "#9B7FD4", "100%"),
    ]
    cells = []
    for name, note, w, color, wdt in chans:
        cells.append("""<Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 10, gap: 4, justifyContent: 'space-between' }}>
                    <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>%s</Text>
                    <Text style={{ fontSize: 12, color: '#8B97A8' }}>%s</Text>
                    <Box style={{ height: 10, width: '%s', background: '%s', borderRadius: 5 }} />
                    <Text style={{ fontSize: 13, color: '%s', fontFamily: 'SF Mono, Menlo, monospace' }}>%s</Text>
                </Box>""" % (name, note, wdt, color, color, w))

    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>四条通道，一个出口</Text>
        <Box style={{ flexDirection: 'row', gap: 8, height: 172 }}>
            %s
        </Box>
        <Box style={{ background: '#E8EFF8', border: '2px solid #1E4FA8', borderRadius: 6, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#0E3F8C' }}>加权 RRF 融合</Text>
            <Text style={{ fontSize: 14, color: '#4A5568', flex: 1 }}>k = 60，按权重合并四路排名</Text>
        </Box>
        <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 12, gap: 4 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>为什么降权扩写路</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>「本征值」能搜到写着「特征值」的资料，靠的是推断；字面命中的可信度不该和它一样</Text>
        </Box>
    </Box>""" % "\n".join(cells)
    return gate_page(
        7, 2, "看得准资料", "解法 · 一次提问，七道关",
        "第二关 · 看得准资料",
        "中文资料难找 —— 同义不同词、短词进不了索引，所以不只找一路",
        code, diagram,
        "35 题考卷 Hit@3 = MRR = 0.9714；关掉精排掉到 0.9571，机制有用当场可见",
    )


def p08() -> str:
    """第三关 · 管得住工具。"""
    code = code_block("application/routing.py:294 · tools.py:196", [
        "def is_tool_allowed(profile, name) -> bool:",
        "    if profile.deny_all:",
        "        return False",
        "    if not profile.mcp_enabled and is_mcp_tool(name):",
        "        return False        # 幻觉出的 MCP 工具也执行不了",
        "    ...",
        "",
        "@tool",
        "def save_note(title, content, library) -> str:",
        "    approved = interrupt({        # ← 图在这里暂停",
        "        'action': 'save_note',",
        "        'preview': content[:200],",
        "    })",
        "    if not approved:",
        "        return '已取消，未保存。'",
    ])
    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>两道闸门，一个确认框</Text>
        <Box style={{ flex: 1, flexDirection: 'row', gap: 10 }}>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '2px solid #1E4FA8', borderRadius: 6, padding: 12, gap: 6 }}>
                <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#1E4FA8' }}>① schema 层</Text>
                <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>按角色裁剪工具表，禁用的工具不出现在提示词里</Text>
                <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 4, padding: 8, justifyContent: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#0E3F8C', lineHeight: 1.5 }}>模型「看不见」它</Text>
                </Box>
            </Box>
            <Box style={{ width: 24, justifyContent: 'center', alignItems: 'center' }}>
                <Box style={{ width: 18, height: 3, background: '#1E4FA8' }} />
                <Box style={{ width: 9, height: 9, background: '#1E4FA8', borderRadius: 2, transform: 'rotate(45deg)' }} />
            </Box>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '2px solid #0E3F8C', borderRadius: 6, padding: 12, gap: 6 }}>
                <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>② 执行层</Text>
                <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>逐次判定，模型硬发被禁工具也执行不了</Text>
                <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 4, padding: 8, justifyContent: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#0E3F8C', lineHeight: 1.5 }}>模型「说了」也跑不了</Text>
                </Box>
            </Box>
        </Box>
        <Box style={{ background: '#FCF6E4', border: '2px solid #E5B54B', borderRadius: 6, padding: 12, gap: 5 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#7A5A16' }}>写操作：再加第三道 —— 问一句</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>interrupt() 在工具执行前暂停整张图，用户点确认才继续；点取消就到此结束，什么都没变</Text>
        </Box>
    </Box>"""
    return gate_page(
        8, 3, "管得住工具", "解法 · 一次提问，七道关",
        "第三关 · 管得住工具",
        "模型能说什么由它定，能做什么由系统定 —— 写操作还要再问一次",
        code, diagram,
        "「AI 不改你的数据」写在提示词里是请求，写在 interrupt() 里才是承诺",
    )


def p09() -> str:
    """第四关 · 说得清出处。"""
    code = code_block("infrastructure/extract.py · chunk_pages", [
        "def chunk_pages(pages: list[str]) -> list[Chunk]:",
        "    # PDF / PPT 逐页切块，每块记住来自第几页",
        "    chunks = []",
        "    for page_no, text in enumerate(pages, start=1):",
        "        for piece in split_by_structure(text):",
        "            chunks.append(Chunk(",
        "                content=piece,",
        "                page_no=page_no,   # ← 出处就在这儿定下",
        "            ))",
        "    return chunks",
    ])
    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>一页纸，切成三块</Text>
        <Box style={{ flexDirection: 'row', gap: 10, height: 200 }}>
            <Box style={{ width: 112, background: '#FFFFFF', border: '2px solid #1E4FA8', borderRadius: 6, padding: 10, gap: 6 }}>
                <Box style={{ width: 44, height: 24, background: '#1E4FA8', borderRadius: 4, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#FFFFFF', fontWeight: 'bold' }}>P12</Text>
                </Box>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>片段 1</Text>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>片段 2</Text>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>片段 3</Text>
                <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 4, padding: 6, justifyContent: 'center' }}>
                    <Text style={{ fontSize: 12, color: '#0E3F8C' }}>同一页</Text>
                </Box>
            </Box>
            <Box style={{ width: 112, background: '#FFFFFF', border: '2px solid #3D7BD9', borderRadius: 6, padding: 10, gap: 6 }}>
                <Box style={{ width: 44, height: 24, background: '#3D7BD9', borderRadius: 4, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#FFFFFF', fontWeight: 'bold' }}>P07</Text>
                </Box>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>片段 4</Text>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>片段 5</Text>
                <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 4, padding: 6, justifyContent: 'center' }}>
                    <Text style={{ fontSize: 12, color: '#0E3F8C' }}>下一份资料</Text>
                </Box>
            </Box>
            <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 6, padding: 14, justifyContent: 'center', gap: 8 }}>
                <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#0E3F8C' }}>检索结果</Text>
                <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>每条片段都带着自己的页码</Text>
            </Box>
        </Box>
        <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 12, gap: 4 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>为什么必须这么切</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>整篇切成一个片段，引用就只能指向「整篇文档」—— 答案对不对就无从核验</Text>
        </Box>
    </Box>"""
    return gate_page(
        9, 4, "说得清出处", "解法 · 一次提问，七道关",
        "第四关 · 说得清出处",
        "检索准不代表引用对得上原文 —— 切块粒度决定答案能不能被验证",
        code, diagram,
        "点开任一条引用能跳到那一页，检索与引用的正确性才变成可核验的",
    )


def p10() -> str:
    """第五关 · 练得下去。"""
    code = code_block("application/question_writer.py", [
        "def write_question(...):",
        "    try:",
        "        raw = model.invoke(prompt)",
        "        question = parse(raw)      # 解析失败会抛",
        "    except Exception:",
        "        return fallback_question()  # ← 退回模板，不抛异常",
        "    return question",
        "",
        "def write_explanation(question_id):",
        "    cached = repo.get_explanation(question_id)",
        "    if cached:",
        "        return cached             # ← 命中缓存 0.02s",
        "    ...                          # 首次约 3.7s",
    ])
    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>一条主路，一条退路</Text>
        <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 5, height: 80 }}>
            <Box style={{ flex: 1, height: 60, background: '#1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>模型写题</Text>
            </Box>
            %s
            <Box style={{ flex: 1, height: 60, background: '#1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>解析校验</Text>
            </Box>
            %s
            <Box style={{ flex: 1, height: 60, background: '#0E3F8C', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>成题入库</Text>
            </Box>
        </Box>
        <Box style={{ background: '#FFFFFF', border: '1px dashed #8B97A8', borderRadius: 6, padding: 10, gap: 5 }}>
            <Text style={{ fontSize: 14, color: '#4A5568' }}>↓ 失败时走这条</Text>
            <Box style={{ background: '#F7F9FC', borderRadius: 5, padding: 10, alignItems: 'center' }}>
                <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#4A5568' }}>退回模板题 · 绝不抛异常</Text>
            </Box>
        </Box>
        <Box style={{ background: '#FCF6E4', border: '2px solid #E5B54B', borderRadius: 6, padding: 12, gap: 5 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#7A5A16' }}>但详解没有退路</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>答案对错由学科事实决定，编一个参考答案比不给更糟 —— 这一环宁可不给，也不乱给</Text>
        </Box>
    </Box>""" % (arrow_h(w=16), arrow_h(w=16))
    return gate_page(
        10, 5, "练得下去", "解法 · 一次提问，七道关",
        "第五关 · 练得下去",
        "模型写题会失败 —— 所以出题有退路，而详解没有",
        code, diagram,
        "有退路的地方退得干脆，没退路的地方宁可停下来 —— 两种都是设计，不是意外",
    )


def p11() -> str:
    """第六关 · 记得住。"""
    code = code_block("domain/scheduling.py:15-18", [
        "_RATING = {",
        "    'again': (-10,        0),            # 掌握度, 间隔秒",
        "    'hard':  (-3,  24 * 60 * 60),      # 1 天",
        "    'good':  (+5,   3 * 24 * 60 * 60), # 3 天",
        "    'easy':  (+10,  7 * 24 * 60 * 60), # 7 天",
        "}",
        "def review(rating, current_mastery):",
        "    delta, interval = _RATING[rating]",
        "    return ReviewResult(",
        "        mastery=clamp_mastery(current + delta),",
        "        due_in_seconds=interval)",
    ])
    bars = [
        ("again", "−10", "立即", "#D9534F", 64),
        ("hard", "−3", "1 天", "#A87F22", 98),
        ("good", "+5", "3 天", "#3D7BD9", 132),
        ("easy", "+10", "7 天", "#1E4FA8", 164),
    ]
    cells = []
    for name, delta, gap, color, h in bars:
        cells.append("""<Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 10, gap: 3, height: %(h)d, justifyContent: 'center' }}>
                    <Text style={{ fontSize: 15, fontWeight: 'bold', color: '%(color)s' }}>%(name)s</Text>
                    <Text style={{ fontSize: 13, color: '%(color)s' }}>%(delta)s</Text>
                    <Text style={{ fontSize: 12, color: '#8B97A8' }}>%(gap)s</Text>
                </Box>""" % {"h": h, "color": color, "name": name, "delta": delta, "gap": gap})

    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>自评四档 → 下次什么时候见</Text>
        <Box style={{ flexDirection: 'row', gap: 10, height: 176, alignItems: 'flex-end' }}>
            %s
        </Box>
        <Box style={{ background: '#E8EFF8', borderRadius: 6, padding: 12, gap: 4 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>整个排期是纯函数</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>不调模型、不随机 —— 同样的输入永远得到同样的排期，所以能被单测覆盖</Text>
        </Box>
        <Box style={{ background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 12, gap: 4 }}>
            <Text style={{ fontSize: 15, fontWeight: 'bold', color: '#0E3F8C' }}>长期记忆按课程隔离</Text>
            <Text style={{ fontSize: 13, color: '#4A5568', lineHeight: 1.55 }}>学期的数据不串到下学期；写入前先问一句要不要记</Text>
        </Box>
    </Box>""" % "\n".join(cells)
    return gate_page(
        11, 6, "记得住", "解法 · 一次提问，七道关",
        "第六关 · 记得住",
        "答完这一题，下次什么时候再见到它 —— 是算出来的，不是建议的",
        code, diagram,
        "复习计划不是模型「建议」的，是按规则算出来的 —— 这才排得住",
    )


def p12() -> str:
    """第七关 · 省得下来。"""
    code = code_block("application/context.py:72 · domain/guardrails.py", [
        "def compress(messages, *, max_messages=24,",
        "               keep_recent=14):",
        "    # 只从整轮边界裁，不拆散「调用—结果」配对",
        "    head = summarize(messages[:-keep_recent])",
        "    tail = messages[-keep_recent:]",
        "    return head + tail    # 摘要 ≤ 240 字，不额外调模型",
        "",
        "def check_input(text):",
        "    for marker in _INJECTION_MARKERS:",
        "        if marker in text: return BLOCK",
    ])
    diagram = """    <Box style={{ position: 'absolute', top: 0, left: 0, width: 700, height: 468, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>三件用户看不见的事</Text>
        <Box style={{ flex: 1, gap: 10 }}>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 6, justifyContent: 'center' }}>
                <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#0E3F8C' }}>上下文压缩</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>24 条上限 · 保留最近 14 条</Text>
                </Box>
                <Box style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
                    <Box style={{ flex: 1, height: 22, background: '#E8EFF8', borderRadius: 4, justifyContent: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#0E3F8C' }}>摘要 ≤ 240 字</Text>
                    </Box>
                    <Box style={{ width: 18, height: 3, background: '#1E4FA8' }} />
                    <Box style={{ width: 118, height: 22, background: '#1E4FA8', borderRadius: 4, justifyContent: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#FFFFFF' }}>保留 14 条</Text>
                    </Box>
                </Box>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>只从整轮边界裁 —— 拆散「调用—结果」模型会报错</Text>
            </Box>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 6, justifyContent: 'center' }}>
                <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#0E3F8C' }}>模型路由与预算</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>按意图与复杂度选档位</Text>
                </Box>
                <Box style={{ flexDirection: 'row', gap: 6 }}>
                    <Box style={{ flex: 1, height: 26, background: '#E8EFF8', borderRadius: 4, justifyContent: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#0E3F8C' }}>简单意图 → 小模型</Text>
                    </Box>
                    <Box style={{ flex: 1, height: 26, background: '#1E4FA8', borderRadius: 4, justifyContent: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#FFFFFF' }}>复杂请求 → 大模型</Text>
                    </Box>
                </Box>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>token 记账 + 当日超预算直接阻止调用</Text>
            </Box>
            <Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 6, justifyContent: 'center' }}>
                <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#0E3F8C' }}>护栏</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>纯函数，可单测</Text>
                </Box>
                <Box style={{ flexDirection: 'row', gap: 6 }}>
                    <Box style={{ flex: 1, height: 26, background: '#FFF4F3', borderRadius: 4, justifyContent: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#D9534F' }}>输入：拦越界与注入</Text>
                    </Box>
                    <Box style={{ flex: 1, height: 26, background: '#E8EFF8', borderRadius: 4, justifyContent: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#0E3F8C' }}>输出：拦泄漏与空答</Text>
                    </Box>
                </Box>
                <Text style={{ fontSize: 13, color: '#4A5568' }}>不靠模型自觉 —— 自觉不是工程手段</Text>
            </Box>
        </Box>
    </Box>"""
    return gate_page(
        12, 7, "省得下来", "解法 · 一次提问，七道关",
        "第七关 · 省得下来",
        "上下文、预算、护栏 —— 用户看不到，但少了任何一样系统都会垮",
        code, diagram,
        "这三件事决定系统能撑多久 —— 而它们全都不在界面上",
    )


# ---------------------------------------------------------------- p13 收束

def p13() -> str:
    """把七关串成一条完整路径。"""
    gates = [
        ("1", "看得懂意图", "#1E4FA8"),
        ("2", "看得准资料", "#3D7BD9"),
        ("3", "管得住工具", "#0E3F8C"),
        ("4", "说得清出处", "#4FB3A4"),
        ("5", "练得下去", "#E5B54B"),
        ("6", "记得住", "#A87F22"),
        ("7", "省得下来", "#6B4E9E"),
    ]
    cells = []
    for n, name, color in gates:
        cells.append("""<Box style={{ flex: 1, background: '%s', borderRadius: 8, padding: 14, gap: 3, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 13, color: '#FFFFFF', opacity: 0.75 }}>第 %s 关</Text>
                    <Text style={{ fontSize: 18, color: '#FFFFFF', fontWeight: 'bold' }}>%s</Text>
                </Box>""" % (color, n, name))

    body = """    <Box style={{ position: 'absolute', top: 176, left: 40, width: 1200, height: 104, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        %s
    </Box>

    <Box style={{ position: 'absolute', top: 300, left: 40, width: 1200, height: 112, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, flexDirection: 'row', alignItems: 'center', padding: '0 24px', gap: 20 }}>
        <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#0E3F8C' }}>一次提问</Text>
        <Box style={{ width: 30, height: 3, background: '#1E4FA8' }} />
        <Text style={{ fontSize: 18, color: '#4A5568', flex: 1 }}>七道关全过，产出一个带出处的答案；中间任何一关失守，最终答案就不可信</Text>
        <Box style={{ background: '#E8EFF8', borderRadius: 6, padding: '10px 16px' }}>
            <Text style={{ fontSize: 16, color: '#0E3F8C', fontWeight: 'bold' }}>最多 6 轮工具调用</Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 432, left: 40, width: 1200, height: 184, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 8, justifyContent: 'center' }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>这七关的共同点</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                每一关都不是「让模型更聪明」，而是<b>给模型加一道能被检查的约束</b>。
                关掉了它们，系统照样能跑 —— 只是你没法相信它的输出。
            </Text>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 8, padding: 18, gap: 8, justifyContent: 'center' }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>为什么值得讲这些</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                因为这些是<b>能被单测覆盖、能被复现、能进 CI</b>的部分。
                下一段就讲：怎么证明它们真的在起作用。
            </Text>
        </Box>
    </Box>""" % "\n".join(cells)
    return master(
        13, "解法 · 收束", "一次提问，走完七道关",
        "七道关不是模块清单，是一条链 —— 每一关都是上一关逼出来的",
        body,
        "模型能力决定上限，工程约束决定下限 —— 知迹做的是后者",
    )


# ---------------------------------------------------------------- p14 评测

def p14() -> str:
    """评测：固定考卷 / 基线门禁 / 消融。"""
    body = """    <Box style={{ position: 'absolute', top: 168, left: 40, width: 1200, height: 218, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10, justifyContent: 'center' }}>
            <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>固定考卷</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <Text style={{ fontSize: 54, fontWeight: 'bold', color: '#1E4FA8', lineHeight: 1.05 }}>35</Text>
                <Text style={{ fontSize: 19, color: '#4A5568', marginBottom: 7 }}>题检索 + 15 句意图</Text>
            </Box>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.6 }}>每题标注正确片段，覆盖同义换词与短词考点</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10, justifyContent: 'center' }}>
            <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>基线门禁</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <Text style={{ fontSize: 54, fontWeight: 'bold', color: '#1E4FA8', lineHeight: 1.05 }}>0.05</Text>
                <Text style={{ fontSize: 19, color: '#4A5568', marginBottom: 7 }}>容差</Text>
            </Box>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.6 }}>掉出容差，命令返回非零 —— 能进提交前检查</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10, justifyContent: 'center' }}>
            <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>当前水平</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <Text style={{ fontSize: 54, fontWeight: 'bold', color: '#0E3F8C', lineHeight: 1.05 }}>0.9714</Text>
                <Text style={{ fontSize: 19, color: '#4A5568', marginBottom: 7 }}>Hit@3 = MRR</Text>
            </Box>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.6 }}>意图准确率 1.0；接真实向量 35 题全中</Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 404, left: 40, width: 1200, height: 232, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#0E3F8C' }}>消融：机制有用，当场可见</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
                <Box style={{ background: '#1E4FA8', borderRadius: 6, padding: '9px 16px' }}>
                    <Text style={{ fontSize: 25, fontWeight: 'bold', color: '#FFFFFF', fontFamily: 'SF Mono, Menlo, monospace' }}>0.9714</Text>
                </Box>
                <Text style={{ fontSize: 19, color: '#8B97A8' }}>→</Text>
                <Box style={{ background: '#D9534F', borderRadius: 6, padding: '9px 16px' }}>
                    <Text style={{ fontSize: 25, fontWeight: 'bold', color: '#FFFFFF', fontFamily: 'SF Mono, Menlo, monospace' }}>0.9571</Text>
                </Box>
                <Text style={{ fontSize: 15, color: '#4A5568', flex: 1 }}>关掉词面精排，MRR 立刻掉下来 —— 不需要「我觉得更好」</Text>
            </Box>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.65 }}>
                评测用确定性向量（同版本任何人跑出同样分数），有基线 JSON 与容差门禁。
            </Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#0E3F8C' }}>但还有测不出来的</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                目前只能测「找到没」和「分类对不对」，<b>测不了「这次复习到底有没有用」</b>。
            </Text>
            <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 5, padding: 12, justifyContent: 'center' }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.6 }}>
                    下一步要补任务级成功率，并用 pass^k 看稳定性 —— 报 pass@1 会把「偶尔能成」包装成「稳定可用」。
                </Text>
            </Box>
        </Box>
    </Box>"""
    return master(
        14, "证据 · 怎么判断今天没比昨天变笨", "怎么证明它没坏",
        "不是「我觉得挺准」，是每次改动都能复跑同一份考卷",
        body,
        "评测的价值不在分数高，在<b>分数掉了能立刻知道</b> —— 这是它能进 CI 的前提",
    )


# ---------------------------------------------------------------- p15 边界

def p15() -> str:
    """六项能力状态表。"""
    rows = [
        ("中断可恢复", "达标", "#1E4FA8", "状态图 + 检查点 + 中断恢复，孤儿线程级联清理"),
        ("检索准确可追溯", "达标", "#1E4FA8", "35 题考卷，真实向量 35/35，引用精确到页"),
        ("工具执行治理", "一半", "#E5B54B", "有双层权限、超时退避、并发与失败转消息；缺参数级约束"),
        ("长上下文管理", "一半", "#E5B54B", "有抽取式摘要与预算控制；缺关键事实外置成结构化笔记"),
        ("长期记忆", "一半", "#E5B54B", "按课程隔离、写入前确认；缺过期、替换与删除机制"),
        ("任务级成功率评测", "没做", "#D9534F", "考卷只测「找到没」「分类对不对」，不测「复习有没有用」"),
    ]
    trs = []
    for i, (name, status, color, note) in enumerate(rows):
        y = 186 + i * 64
        bg = "#F7F9FC" if i % 2 == 0 else "#FFFFFF"
        trs.append("""<Box style={{ position: 'absolute', top: %d, left: 40, width: 1200, height: 54, background: '%s', border: '1px solid #D6DCE5', borderRadius: 5, flexDirection: 'row', alignItems: 'center', padding: '0 20px', gap: 18 }}>
                <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C', width: 244 }}>%s</Text>
                <Box style={{ width: 72, height: 30, background: '%s', borderRadius: 4, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>%s</Text>
                </Box>
                <Text style={{ fontSize: 16, color: '#4A5568', flex: 1 }}>%s</Text>
            </Box>""" % (y, bg, name, color, status, note))

    body = "\n".join(trs) + """
    <Box style={{ position: 'absolute', top: 162, left: 40, width: 1200, flexDirection: 'row', gap: 18, paddingBottom: 6 }}>
        <Text style={{ fontSize: 16, color: '#8B97A8', width: 244, paddingLeft: 20 }}>能力项</Text>
        <Text style={{ fontSize: 16, color: '#8B97A8', width: 72, textAlign: 'center' }}>状态</Text>
        <Text style={{ fontSize: 16, color: '#8B97A8', flex: 1 }}>依据 / 还缺什么</Text>
    </Box>

    <Box style={{ position: 'absolute', top: 578, left: 40, width: 1200, height: 58, background: '#E8EFF8', borderRadius: 6, flexDirection: 'row', alignItems: 'center', padding: '0 20px', gap: 12 }}>
        <Text style={{ fontSize: 18, color: '#0E3F8C', fontWeight: 'bold' }}>下一步排序：</Text>
        <Text style={{ fontSize: 18, color: '#0E3F8C' }}>① 任务级成功率评测　② 记忆的过期与删除　③ 更难的检索考卷</Text>
    </Box>"""
    return master(
        15, "边界 · 诚实清单", "六项能力：两项达标，三项一半，一项没做",
        "把没做的说出来，比多做一点更有用 —— 这是下一步的排序依据",
        body,
        "另外四项也标为「计划中」：多用户与数据隔离、在线监控聚合面板、Reranker 重排、反思式自我批判",
    )


# ---------------------------------------------------------------- p16 收束

def p16() -> str:
    """收束整版。"""
    return """<Slide style={{ width: 1280, height: 720, position: 'relative', background: '#0E3F8C', fontFamily: 'PingFang SC, Hiragino Sans GB, sans-serif' }}>
    <Image src="assets/p16-closing-desk.png" style={{ position: 'absolute', top: 0, right: 0, width: 520, height: 720, objectFit: 'cover' }} />
    <Box style={{ position: 'absolute', top: 0, right: 0, width: 520, height: 720, background: '#0E3F8C', opacity: 0.45 }} />

    <Box style={{ position: 'absolute', top: 84, left: 80, width: 700, flexDirection: 'column', gap: 20 }}>
        <Text style={{ fontSize: 15, color: '#A9C6EF', letterSpacing: 3 }}>收束</Text>
        <Text style={{ fontSize: 46, fontWeight: 'bold', color: '#FFFFFF', lineHeight: 1.3 }}>
            资料进去，题出来，复习排好
        </Text>
        <Box style={{ width: 64, height: 3, background: '#3D7BD9' }} />
        <Text style={{ fontSize: 19, color: '#C9DDF5', lineHeight: 1.7 }}>
            支撑这三件事的，是七道能被检查的关卡。
        </Text>
        <Text style={{ fontSize: 16, color: '#8FB4E8', lineHeight: 1.7 }}>
            每一步能恢复 · 每次写入先问 · 改动有没有变差算得出来
        </Text>
    </Box>

    <Box style={{ position: 'absolute', top: 396, left: 80, width: 1120, flexDirection: 'row', gap: 14 }}>
        <Box style={{ flex: 1, background: '#1E4FA8', borderRadius: 8, padding: 16, gap: 6 }}>
            <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#FFFFFF' }}>整理资料</Text>
            <Text style={{ fontSize: 14, color: '#C9DDF5', lineHeight: 1.6 }}>传进来，按学科分好，能翻到第几页</Text>
        </Box>
        <Box style={{ flex: 1, background: '#1E4FA8', borderRadius: 8, padding: 16, gap: 6 }}>
            <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#FFFFFF' }}>出题</Text>
            <Text style={{ fontSize: 14, color: '#C9DDF5', lineHeight: 1.6 }}>按你的资料出，做错的方向多出几道</Text>
        </Box>
        <Box style={{ flex: 1, background: '#1E4FA8', borderRadius: 8, padding: 16, gap: 6 }}>
            <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#FFFFFF' }}>复习</Text>
            <Text style={{ fontSize: 14, color: '#C9DDF5', lineHeight: 1.6 }}>今天练哪几题排好，翻得回原文那一页</Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', bottom: 44, left: 80, flexDirection: 'row', alignItems: 'center', gap: 24 }}>
        <Box style={{ width: 4, height: 40, background: '#3D7BD9' }} />
        <Box style={{ flexDirection: 'column', gap: 3 }}>
            <Text style={{ fontSize: 15, color: '#FFFFFF' }}>知迹 ZhiJi · AI 学习私教与智能复习系统</Text>
            <Text style={{ fontSize: 13, color: '#8FB4E8' }}>284 项测试 · 检索 35 题 Hit@3 = MRR = 0.9714 · 意图 15 句准确率 1.0</Text>
        </Box>
    </Box>
</Slide>
"""


PAGES = {
    2: p02, 3: p03, 4: p04, 5: p05, 6: p06, 7: p07, 8: p08, 9: p09,
    10: p10, 11: p11, 12: p12, 13: p13, 14: p14, 15: p15, 16: p16,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    for no, fn in sorted(PAGES.items()):
        path = SLIDES_DIR / f"{no:02d}.slide"
        path.write_text(fn(), encoding="utf-8")
        print(f"✓ {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
