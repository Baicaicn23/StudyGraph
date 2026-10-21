#!/usr/bin/env python3
"""生成知迹答辩 PPT 的 03–16 页 .slide 源文件。

**为什么用脚本而不是手写 14 个文件**
- 母版（A 顶条 / B 标题 / C 内容 / 结论条 / D 页脚）在 16 页里完全一致，
  手写必然出现尺寸与位置漂移；
- 内容与版式分离：改文案改脚本里的 DATA，改版式改母版函数。

**为什么用 % 格式化而不是 f-string**
slidep 的 DSL 里到处是 JSX 花括号（``style={{ ... }}``）。f-string 要求把每个
``{`` 写成 ``{{``，几百行下来极易写错一个（``}}}}`` 这种）就整文件语法报错。
``%`` 格式化只认 ``%s``，**完全不碰花括号** —— 这是这里唯一安全的做法。

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

    尺寸契约（学术风基线）：
      A 顶条   y 0-56
      B 标题块  y 56-148
      C 内容区  y 156-636（480px，≥476 下限）
      结论条   y 648-704
      D 页脚   y 704-720
    """
    head = MAST_HEAD % {"section": section}
    title_block = MAST_TITLE % {"title": title, "subtitle": subtitle}
    tail = MAST_CONCL % {"conclusion": conclusion, "page": f"{page:02d}"}
    return head + title_block + "\n" + body + "\n" + tail


def kpi(num: str, unit: str, label: str, note: str, accent: str = "#1E4FA8") -> str:
    """KPI 巨数字块。"""
    return """<Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 16, flexDirection: 'column', gap: 4, justifyContent: 'center' }}>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 6 }}>
                <Text style={{ fontSize: 58, fontWeight: 'bold', color: '%(accent)s', lineHeight: 1.05 }}>%(num)s</Text>
                <Text style={{ fontSize: 20, color: '#4A5568', marginBottom: 8 }}>%(unit)s</Text>
            </Box>
            <Text style={{ fontSize: 21, fontWeight: 'bold', color: '#0E3F8C' }}>%(label)s</Text>
            <Text style={{ fontSize: 14, color: '#8B97A8', lineHeight: 1.6 }}>%(note)s</Text>
        </Box>""" % {
        "accent": accent, "num": num, "unit": unit, "label": label, "note": note
    }


# ---------------------------------------------------------------- 各页

def p03() -> str:
    """三行卡：三道坎 × 真实失效场景。"""
    rows = [
        ("可恢复", "会话崩在第 7 步，前 6 步的检索与工具调用全部作废",
         "状态在消息列表里，进程一挂就没了", "LangGraph 的 checkpointer 机制正是为此刻态而设计"),
        ("可拦截", "模型幻觉出一个被禁工具名并真的发起调用",
         "只在 schema 层裁剪工具，执行层没有第二道判定", "schema 层不够 —— 模型能「说出」工具名并失败"),
        ("可度量", "改了一行检索权重，重跑一次看着更好了",
         "没有固定考卷，波动和真实提升混在一起", "τ-bench 实测 pass^1 ≈ 61%、pass^8 &lt; 25%"),
    ]
    parts = []
    for i, (name, scene, why, evidence) in enumerate(rows, 1):
        y = 160 + (i - 1) * 162
        parts.append("""<Box style={{ position: 'absolute', top: %d, left: 40, width: 1200, height: 148, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, flexDirection: 'row', alignItems: 'center', padding: '0 22px', gap: 22 }}>
            <Box style={{ width: 52, height: 52, background: '#1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 27, color: '#FFFFFF', fontWeight: 'bold' }}>%d</Text>
            </Box>
            <Box style={{ width: 150, justifyContent: 'center' }}>
                <Text style={{ fontSize: 27, fontWeight: 'bold', color: '#0E3F8C' }}>%s</Text>
            </Box>
            <Box style={{ flex: 1, gap: 6 }}>
                <Text style={{ fontSize: 18, color: '#1A2230', lineHeight: 1.55 }}>失效场景：%s</Text>
                <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.55 }}>为什么难：%s</Text>
            </Box>
            <Box style={{ width: 340, background: '#E8EFF8', borderRadius: 5, padding: '12px 14px' }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.6 }}>%s</Text>
            </Box>
        </Box>""" % (y, i, name, scene, why, evidence))
    return master(
        3, "问题 · 三道坎的具体形态", "可恢复、可拦截、可度量：Agent 落地的三道坎",
        "每道坎背后都是一个具体的、会真实发生的失效场景",
        "\n".join(parts),
        "知迹把这三道坎都当作必须用工程手段解决的问题 —— 后面每一页对应其中一道",
    )


def p04() -> str:
    """左文右图：产品定义 + 工程规模。"""
    body = """    <Box style={{ position: 'absolute', top: 160, left: 40, width: 520, height: 476, flexDirection: 'column', gap: 16 }}>
        <Box style={{ background: '#E8EFF8', borderLeft: '4px solid #1E4FA8', borderRadius: 4, padding: '16px 18px' }}>
            <Text style={{ fontSize: 16, color: '#0E3F8C', lineHeight: 1.7 }}>
                知迹 = 一个把学习资料变成题、再把题变成复习计划的 Agent。
            </Text>
        </Box>
        <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.75 }}>
            之所以选学习场景，是因为它同时具备三个特征：
        </Text>
        <Box style={{ gap: 9 }}>
            <Text style={{ fontSize: 15, color: '#1A2230', lineHeight: 1.6 }}>
                <span style={{ fontWeight: 'bold', color: '#0E3F8C' }}>一 · </span>一次任务要串很多步（整理 → 出题 → 复习），适合验证「可恢复」
            </Text>
            <Text style={{ fontSize: 15, color: '#1A2230', lineHeight: 1.6 }}>
                <span style={{ fontWeight: 'bold', color: '#0E3F8C' }}>二 · </span>涉及写操作（沉淀笔记、写文件），适合验证「可拦截」
            </Text>
            <Text style={{ fontSize: 15, color: '#1A2230', lineHeight: 1.6 }}>
                <span style={{ fontWeight: 'bold', color: '#0E3F8C' }}>三 · </span>结果好坏能客观判定（题对不对、掌握度变没变），适合验证「可度量」
            </Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, justifyContent: 'center' }}>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.7 }}>
                这不是「我是个学生所以做了个学生 App」，而是
                <span style={{ fontWeight: 'bold', color: '#0E3F8C' }}>我需要一个能同时压测三项能力的场景</span>。
            </Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 160, left: 580, width: 660, height: 476, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, flexDirection: 'column', gap: 14 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>工程规模（非 Demo 的量级）</Text>
        <Box style={{ flexDirection: 'row', gap: 14 }}>
            %s
            %s
        </Box>
        <Box style={{ flexDirection: 'row', gap: 14 }}>
            %s
            %s
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 5, padding: '12px 14px', justifyContent: 'center' }}>
            <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.65 }}>
                技术栈：LangGraph 状态图 · FastAPI + SSE · SQLite（端口化，可替换）· Next.js 16
            </Text>
        </Box>
    </Box>""" % (
        kpi("10036", "行", "后端代码", "53 个 Python 模块，四层分层"),
        kpi("10325", "行", "前端代码", "15 个组件，Next.js 16"),
        kpi("50", "个", "API 端点", "含 SSE 流式与中断恢复"),
        kpi("284", "项", "自动测试", "全 Mock，零 API 消耗"),
    )
    return master(
        4, "问题 · 为什么是学习场景", "知迹：一个把三道坎都做掉的学习 Agent",
        "产品定义与工程规模 —— 这不是一个学生小工具",
        body,
        "选场景是为了压测能力，不是为了凑一个题目 —— 后面每一页都是这三道坎的具体解法",
    )


def p05() -> str:
    """横向流程：状态图。"""
    nodes = [
        ("START", "#F7F9FC", "#1E4FA8", 150),
        ("route", "#1E4FA8", "#FFFFFF", 168),
        ("plan", "#1E4FA8", "#FFFFFF", 168),
        ("agent", "#0E3F8C", "#FFFFFF", 168),
        ("tools", "#0E3F8C", "#FFFFFF", 168),
        ("END", "#F7F9FC", "#1E4FA8", 150),
    ]
    parts = []
    gap = 34          # 节点之间的间距（线 22 + 箭头 12）
    x = 46
    for i, (name, bg, fg, w) in enumerate(nodes):
        parts.append("""<Box style={{ position: 'absolute', top: 214, left: %d, width: %d, height: 74, background: '%s', border: '2px solid #1E4FA8', borderRadius: 8, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 24, fontWeight: 'bold', color: '%s' }}>%s</Text>
            </Box>""" % (x, w, bg, fg, name))
        if i < len(nodes) - 1:
            ax = x + w            # 节点右边界
            parts.append("""<Box style={{ position: 'absolute', top: 249, left: %d, width: 20, height: 3, background: '#1E4FA8' }} />
            <Box style={{ position: 'absolute', top: 241, left: %d, width: 11, height: 11, background: '#1E4FA8', borderRadius: 2, transform: 'rotate(45deg)' }} />"""
                         % (ax + 3, ax + 19))
        x += w + gap

    body = "\n".join(parts) + """
    <Box style={{ position: 'absolute', top: 296, left: 560, width: 168, height: 44, borderLeft: '2px solid #3D7BD9', borderBottom: '2px solid #3D7BD9', borderRight: '2px solid #3D7BD9', borderRadius: 6, background: '#E8EFF8', justifyContent: 'center', alignItems: 'center' }}>
        <Text style={{ fontSize: 16, color: '#0E3F8C', fontWeight: 'bold' }}>调用 — 回填</Text>
    </Box>

    <Box style={{ position: 'absolute', top: 362, left: 40, width: 1200, height: 118, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 5 }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>route · 判意图</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.6 }}>六类意图路由到四个子智能体，每个角色带各自的工具权限</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 5 }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>plan · 判要不要规划</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.6 }}>规则先判复杂度，简单请求直接跳过，需要才调模型（上限 5 步）</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 5 }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>agent ⇄ tools · 循环</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.6 }}>最多 6 轮工具调用；每轮结束都写检查点，可中断可续跑</Text>
        </Box>
    </Box>"""
    return master(
        5, "解法 ① · 可恢复", "一次学习回合，是画出来的一张图",
        "route → plan → agent ⇄ tools —— 循环与分支都写在明面上",
        body,
        "状态存在图里而不是消息列表里，所以第 7 步崩了，第 6 步的检查点还在",
    )


def p06() -> str:
    """双层权限 + 九宫格。"""
    tools = [
        ("查", "knowledge_search"), ("查", "mistake_search"), ("查", "read_file"),
        ("存", "save_note"), ("存", "write_file"), ("查", "list_files"),
        ("外面", "web_search"), ("外面", "fetch_url"), ("外面", "calculator"),
    ]
    cells = []
    for i, (kind, name) in enumerate(tools):
        r, c = divmod(i, 3)
        x = c * 200          # 相对右栏容器
        y = 30 + r * 92
        color = {"查": "#1E4FA8", "存": "#0E3F8C", "外面": "#3D7BD9"}[kind]
        cells.append("""<Box style={{ position: 'absolute', top: %d, left: %d, width: 188, height: 80, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 12, justifyContent: 'center', gap: 3 }}>
                <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Box style={{ width: 4, height: 16, background: '%s' }} />
                    <Text style={{ fontSize: 17, fontWeight: 'bold', color: '%s' }}>%s</Text>
                </Box>
                <Text style={{ fontSize: 14, color: '#1A2230', fontFamily: 'SF Mono, Menlo, monospace' }}>%s</Text>
            </Box>""" % (y, x, color, color, kind, name))

    body = """    <Box style={{ position: 'absolute', top: 160, left: 40, width: 380, height: 476, flexDirection: 'column', gap: 12 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>双层权限：两道都得过</Text>
        <Box style={{ background: '#E8EFF8', borderRadius: 6, padding: 16, gap: 6 }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>第一层 · schema</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.65 }}>按角色裁剪工具表，禁用的工具根本不出现在提示词里</Text>
        </Box>
        <Box style={{ background: '#E8EFF8', borderRadius: 6, padding: 16, gap: 6 }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>第二层 · 执行</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.65 }}>is_tool_allowed 逐次判定，模型硬发被禁工具也执行不了</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14, gap: 6 }}>
            <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#D9534F' }}>为什么两道都要</Text>
            <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.65 }}>只做 schema 层，模型仍可能「说出」被禁工具名并失败；只做执行层，模型会反复尝试、白耗轮数。MCP 工具用 mcp_ 前缀兜底 —— 动态注册的名字没法枚举，只能按前缀拦。</Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 160, left: 440, width: 800, height: 476 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C', marginBottom: 8 }}>九个工具：查 · 存 · 问外面</Text>
        %s
    </Box>""" % "\n".join(cells)
    return master(
        6, "解法 ② · 可拦截", "九个工具，模型能调哪个由系统决定",
        "schema 层 + 执行层双道判定 —— 越权在写下去之前就被拦下",
        body,
        "权限是执行层的硬判定，不是提示词里的一句请求",
    )


def p07() -> str:
    """中心主视觉 + 两侧说明。"""
    body = """    <Box style={{ position: 'absolute', top: 160, left: 40, width: 1200, height: 476, flexDirection: 'row', gap: 20 }}>
        <Box style={{ width: 320, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 12, justifyContent: 'center' }}>
            <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>这道闸门在哪</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.75 }}>
                LangGraph 的 interrupt() 在工具执行前暂停整张图，用户点确认后用 Command(resume=...) 从检查点继续。
            </Text>
            <Box style={{ background: '#E8EFF8', borderRadius: 5, padding: 12 }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.6 }}>
                    中断信息写进消息流，前端能看到「正在等待确认」；确认与取消都走同一条恢复路径。
                </Text>
            </Box>
        </Box>

        <Box style={{ flex: 1, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 8, padding: 16, justifyContent: 'center', alignItems: 'center' }}>
            <Image src="assets/p07-gate.png" style={{ width: '100%', height: 396, objectFit: 'contain' }} />
            <Text style={{ fontSize: 13, color: '#8B97A8', marginTop: 6 }}>
                配图：半透明挡板拦住悬浮的笔，后方是待写入的卡片
            </Text>
        </Box>

        <Box style={{ width: 320, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 12, justifyContent: 'center' }}>
            <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>承诺 vs 请求</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.75 }}>
                「AI 不改你的数据」如果只写在提示词里，那是请求；写在 interrupt() 里，才是承诺。
            </Text>
            <Box style={{ background: '#E8EFF8', borderRadius: 5, padding: 12 }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.6 }}>
                    练习角色对写入类工具只读；这类越权有回归测试断言「数据确实没被改」。
                </Text>
            </Box>
        </Box>
    </Box>"""
    return master(
        7, "解法 ② · 可拦截", "写入之前，它会先问一句",
        "Human-in-the-Loop 是一道闸门，不是一句劝告",
        body,
        "点确认才落库，点取消就到此结束 —— 什么都不会变",
    )


def p08() -> str:
    """四路召回漏斗。"""
    channels = [
        ("原查询 FTS", "字面 trigram", "1.0"),
        ("同义 / 中英扩写", "换个说法也能找到", "0.5"),
        ("两字词 LIKE", "短词专门兜底", "0.8"),
        ("向量语义", "零字面重叠", "1.0"),
    ]
    parts = []
    for i, (name, note, w) in enumerate(channels):
        y = 168 + i * 62
        parts.append("""<Box style={{ position: 'absolute', top: %d, left: 40, width: 330, height: 52, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: '0 14px', flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Box style={{ width: 5, height: 30, background: '#1E4FA8' }} />
                <Box style={{ flex: 1 }}>
                    <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#0E3F8C' }}>%s</Text>
                    <Text style={{ fontSize: 13, color: '#8B97A8' }}>%s</Text>
                </Box>
                <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#1E4FA8', fontFamily: 'SF Mono, Menlo, monospace' }}>%s</Text>
            </Box>""" % (y, name, note, w))

    body = "\n".join(parts) + """
    <Box style={{ position: 'absolute', top: 190, left: 400, width: 220, height: 216, background: '#E8EFF8', border: '2px solid #1E4FA8', borderRadius: 10, justifyContent: 'center', alignItems: 'center', gap: 8 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>加权 RRF</Text>
        <Text style={{ fontSize: 15, color: '#4A5568' }}>k = 60</Text>
        <Text style={{ fontSize: 13, color: '#8B97A8' }}>扩写路降权 0.5</Text>
    </Box>

    <Box style={{ position: 'absolute', top: 250, left: 654, width: 190, height: 96, background: '#FFFFFF', border: '2px solid #3D7BD9', borderRadius: 8, justifyContent: 'center', alignItems: 'center', gap: 5 }}>
        <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#0E3F8C' }}>词面精排</Text>
        <Text style={{ fontSize: 13, color: '#8B97A8' }}>只调顺序 · 不增删候选</Text>
    </Box>

    <Box style={{ position: 'absolute', top: 168, left: 876, width: 364, height: 240, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 16, gap: 10 }}>
        <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#0E3F8C' }}>top-k 片段，每条带出处</Text>
        <Text style={{ fontSize: 14, color: '#4A5568', lineHeight: 1.6 }}>精排权重</Text>
        <Box style={{ gap: 6 }}>
            <Text style={{ fontSize: 14, color: '#1A2230' }}>原查询覆盖　0.50</Text>
            <Text style={{ fontSize: 14, color: '#1A2230' }}>扩写覆盖　　0.15</Text>
            <Text style={{ fontSize: 14, color: '#1A2230' }}>标题命中　　0.35</Text>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 5, padding: 10, justifyContent: 'center' }}>
            <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.6 }}>
                35 题考卷 Hit@3 = MRR = 0.9714；关掉精排掉到 0.9571
            </Text>
        </Box>
    </Box>"""
    return master(
        8, "解法 ③ · 可度量", "中文资料难找，所以不只找一路",
        "四路并行召回 → 加权融合 → 词面精排 —— 每一步都可消融验证",
        body,
        "「本征值」能搜到写着「特征值」的资料 —— 靠的不是运气，是多路召回与可调的权重",
    )


def p09() -> str:
    """左文右图：逐页出处。"""
    body = """    <Box style={{ position: 'absolute', top: 160, left: 40, width: 470, height: 476, flexDirection: 'column', gap: 14 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>三步入库</Text>
        <Box style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
            <Box style={{ width: 34, height: 34, background: '#1E4FA8', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 18, color: '#FFFFFF', fontWeight: 'bold' }}>1</Text>
            </Box>
            <Text style={{ fontSize: 17, color: '#1A2230', lineHeight: 1.6, flex: 1 }}>原样秒传 —— 二进制文件先落盘，不解析、不调模型</Text>
        </Box>
        <Box style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
            <Box style={{ width: 34, height: 34, background: '#1E4FA8', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 18, color: '#FFFFFF', fontWeight: 'bold' }}>2</Text>
            </Box>
            <Text style={{ fontSize: 17, color: '#1A2230', lineHeight: 1.6, flex: 1 }}>需要参与问答时再点「解析」—— 用时才建索引</Text>
        </Box>
        <Box style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
            <Box style={{ width: 34, height: 34, background: '#1E4FA8', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 18, color: '#FFFFFF', fontWeight: 'bold' }}>3</Text>
            </Box>
            <Text style={{ fontSize: 17, color: '#1A2230', lineHeight: 1.6, flex: 1 }}>PDF / PPT 逐页切块，每一块记住自己来自第几页</Text>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 6, padding: 16, justifyContent: 'center', gap: 8 }}>
            <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#0E3F8C' }}>为什么必须这么设计</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                切块粒度决定引用能不能落到页。如果整篇 PDF 切成一个片段，引用就只能指向「整篇文档」，
                答案对不对就无从核验。逐页切块是让「引用到第几页」成立的前提。
            </Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 160, left: 530, width: 710, height: 476, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 14 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>切块与页码的对应关系</Text>
        <Box style={{ gap: 10 }}>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Box style={{ width: 86, height: 46, background: '#1E4FA8', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 19, color: '#FFFFFF', fontWeight: 'bold' }}>P12</Text>
                </Box>
                <Box style={{ flex: 1, height: 46, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 5, padding: '0 14px', justifyContent: 'center' }}>
                    <Text style={{ fontSize: 15, color: '#1A2230' }}>片段 1 · 携带页码标记</Text>
                </Box>
            </Box>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Box style={{ width: 86, height: 46, background: '#3D7BD9', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 19, color: '#FFFFFF', fontWeight: 'bold' }}>P12</Text>
                </Box>
                <Box style={{ flex: 1, height: 46, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 5, padding: '0 14px', justifyContent: 'center' }}>
                    <Text style={{ fontSize: 15, color: '#1A2230' }}>片段 2 · 同页不同段</Text>
                </Box>
            </Box>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Box style={{ width: 86, height: 46, background: '#0E3F8C', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 19, color: '#FFFFFF', fontWeight: 'bold' }}>P07</Text>
                </Box>
                <Box style={{ flex: 1, height: 46, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 5, padding: '0 14px', justifyContent: 'center' }}>
                    <Text style={{ fontSize: 15, color: '#1A2230' }}>片段 3 · 切到下一份资料</Text>
                </Box>
            </Box>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 6, padding: 16, justifyContent: 'center' }}>
            <Text style={{ fontSize: 15, color: '#0E3F8C', lineHeight: 1.7 }}>
                答案里点开任一条引用，能直接跳到那一页 —— 检索与引用的正确性因此变成<b>可核验</b>的，
                而不是「模型说的」。
            </Text>
        </Box>
    </Box>"""
    return master(
        9, "解法 ③ · 可度量", "每句结论，都能翻回原文那一页",
        "逐页切块是「引用可核验」的前提 —— 引用粒度决定了答案能不能被验证",
        body,
        "检索准确之外，还要引用可追溯 —— 否则「它答得对」只是无法证伪的说法",
    )


def p10() -> str:
    """双路径分叉。"""
    body = """    <Box style={{ position: 'absolute', top: 166, left: 40, width: 1200, height: 220, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#0E3F8C' }}>出题：模型写题 → 校验 → 成题</Text>
        <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Box style={{ width: 200, height: 66, background: '#1E4FA8', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 20, color: '#FFFFFF', fontWeight: 'bold' }}>模型出题</Text>
            </Box>
            <Box style={{ width: 24, height: 3, background: '#1E4FA8' }} />
            <Box style={{ width: 11, height: 11, background: '#1E4FA8', borderRadius: 2, transform: 'rotate(45deg)' }} />
            <Box style={{ width: 200, height: 66, background: '#1E4FA8', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 20, color: '#FFFFFF', fontWeight: 'bold' }}>解析校验</Text>
            </Box>
            <Box style={{ width: 24, height: 3, background: '#1E4FA8' }} />
            <Box style={{ width: 11, height: 11, background: '#1E4FA8', borderRadius: 2, transform: 'rotate(45deg)' }} />
            <Box style={{ width: 200, height: 66, background: '#0E3F8C', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 20, color: '#FFFFFF', fontWeight: 'bold' }}>成题入库</Text>
            </Box>
            <Box style={{ flex: 1, height: 66, background: '#E8EFF8', borderRadius: 7, padding: '0 16px', justifyContent: 'center' }}>
                <Text style={{ fontSize: 15, color: '#0E3F8C', lineHeight: 1.6 }}>解析失败或写坏 → 退回模板题，<b>绝不抛异常</b>。一条误区只出一道题，不重复刷</Text>
            </Box>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 404, left: 40, width: 1200, height: 232, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 12 }}>
        <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#0E3F8C' }}>详解：按需生成 + 落库缓存</Text>
        <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Box style={{ width: 220, height: 66, background: '#3D7BD9', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 19, color: '#FFFFFF', fontWeight: 'bold' }}>首次生成</Text>
            </Box>
            <Box style={{ width: 24, height: 3, background: '#3D7BD9' }} />
            <Box style={{ width: 11, height: 11, background: '#3D7BD9', borderRadius: 2, transform: 'rotate(45deg)' }} />
            <Box style={{ width: 220, height: 66, background: '#3D7BD9', borderRadius: 7, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 19, color: '#FFFFFF', fontWeight: 'bold' }}>写入缓存</Text>
            </Box>
            <Box style={{ width: 24, height: 3, background: '#3D7BD9' }} />
            <Box style={{ width: 11, height: 11, background: '#3D7BD9', borderRadius: 2, transform: 'rotate(45deg)' }} />
            <Box style={{ flex: 1, height: 66, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 7, padding: '0 16px', justifyContent: 'center' }}>
                <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.6 }}>再次查看：直接命中缓存</Text>
            </Box>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 6, padding: 14, justifyContent: 'center' }}>
            <Text style={{ fontSize: 15, color: '#0E3F8C', lineHeight: 1.7 }}>
                <b>详解没有退路</b> —— 答案对错由学科事实决定，编一个参考答案比不给更糟。
                所以这一环宁可不给，也不乱给；出题那一步有模板兜底，是因为题错了可以再出一张。
            </Text>
        </Box>
    </Box>"""
    return master(
        10, "解法 ④ · 工程完备性", "模型写不出来的时候，题也不会停",
        "退路是提前设计好的，不是临时打补丁",
        body,
        "有退路的地方要退得干脆，没退路的地方宁可停下来 —— 两种情况都是设计，不是意外",
    )


def p11() -> str:
    """环形调度 + 四档表。"""
    rows = [
        ("again", "忘了", "−10", "立即", "#D9534F"),
        ("hard", "有点难", "−3", "1 天", "#E5B54B"),
        ("good", "掌握了", "+5", "3 天", "#3D7BD9"),
        ("easy", "太简单", "+10", "7 天", "#1E4FA8"),
    ]
    trs = []
    for i, (key, cn, delta, gap, color) in enumerate(rows):
        y = 190 + i * 78
        trs.append("""<Box style={{ position: 'absolute', top: %d, left: 700, width: 540, height: 66, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 6, flexDirection: 'row', alignItems: 'center', padding: '0 18px', gap: 14 }}>
                <Box style={{ width: 6, height: 34, background: '%s' }} />
                <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#0E3F8C', fontFamily: 'SF Mono, Menlo, monospace', width: 80 }}>%s</Text>
                <Text style={{ fontSize: 16, color: '#4A5568', width: 84 }}>%s</Text>
                <Text style={{ fontSize: 22, fontWeight: 'bold', color: '%s', width: 70, fontFamily: 'SF Mono, Menlo, monospace' }}>%s</Text>
                <Text style={{ fontSize: 16, color: '#1A2230' }}>掌握度</Text>
                <Box style={{ flex: 1 }} />
                <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#0E3F8C', fontFamily: 'SF Mono, Menlo, monospace' }}>%s</Text>
                <Text style={{ fontSize: 14, color: '#8B97A8' }}>后再见</Text>
            </Box>""" % (y, color, key, cn, color, delta, gap))

    body = "\n".join(trs) + """
    <Box style={{ position: 'absolute', top: 160, left: 40, width: 620, height: 476, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 14 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>自评 → 掌握度增减 → 到期重排</Text>
        <Box style={{ flex: 1, background: '#FFFFFF', border: '2px solid #1E4FA8', borderRadius: 10, margin: '14px 70px', justifyContent: 'center', alignItems: 'center', gap: 6 }}>
            <Text style={{ fontSize: 46, fontWeight: 'bold', color: '#0E3F8C' }}>0 – 100</Text>
            <Text style={{ fontSize: 16, color: '#4A5568' }}>掌握度区间，夹紧不外溢</Text>
        </Box>
        <Box style={{ background: '#E8EFF8', borderRadius: 6, padding: 14, gap: 6 }}>
            <Text style={{ fontSize: 15, color: '#0E3F8C', lineHeight: 1.7 }}>
                整个排期是<b>纯函数</b>：给定当前掌握度与自评档位，算出下次到期时间。
                不调模型、不随机 —— 所以它能被单测覆盖，也能被复算。
            </Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 160, left: 690, width: 550, height: 476 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C', marginBottom: 8 }}>四档自评 → 间隔</Text>
    </Box>"""
    return master(
        11, "解法 ⑤ · 学习闭环", "答完这一题，决定下次什么时候再见到它",
        "四档自评 → 掌握度增减 → 到期重排 —— 全部可复算",
        body,
        "复习计划不是模型「建议」的，是按规则算出来的 —— 同样的输入永远得到同样的排期",
    )


def p12() -> str:
    """三栏：看不见的三件事。"""
    cols = [
        ("上下文压缩", "24 条上限 · 保留最近 14 条",
         "只从整轮边界裁剪，不拆散「工具调用—结果」配对；摘要用抽取式，240 字以内，不额外调模型。",
         "拆散了模型会看到孤立的结果并报错 —— 这是踩过的坑"),
        ("模型路由与预算", "按意图与复杂度选档位",
         "每次调用记 token，当日超预算直接阻止真实调用；简单意图走小模型，复杂请求走大模型。",
         "省的是不该省的地方，不是在关键处省"),
        ("护栏", "输入拦越界与注入 · 输出拦泄漏",
         "规则写成纯函数，可单测。系统提示词与内部工具标识符出现在正文里会被拦下。",
         "不靠模型自觉 —— 自觉不是工程手段"),
    ]
    parts = []
    for i, (title, sub, desc, note) in enumerate(cols):
        x = 40 + i * 408
        parts.append("""<Box style={{ position: 'absolute', top: 160, left: %d, width: 384, height: 480, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 22, flexDirection: 'column', gap: 12 }}>
            <Box style={{ width: 46, height: 46, background: '#1E4FA8', borderRadius: 6, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 24, color: '#FFFFFF', fontWeight: 'bold' }}>%d</Text>
            </Box>
            <Text style={{ fontSize: 25, fontWeight: 'bold', color: '#0E3F8C' }}>%s</Text>
            <Text style={{ fontSize: 16, color: '#3D7BD9', fontWeight: 'bold' }}>%s</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.75 }}>%s</Text>
            <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 5, padding: 12, justifyContent: 'center' }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.65 }}>%s</Text>
            </Box>
        </Box>""" % (x, i + 1, title, sub, desc, note))
    return master(
        12, "解法 ⑥ · 成本与约束", "看不见的三件事，撑住上面所有能力",
        "上下文、预算、护栏 —— 用户看不到，但少了任何一样系统都会垮",
        "\n".join(parts),
        "这三件事决定系统能撑多久 —— 而它们全都不在界面上",
    )


def p13() -> str:
    """KPI 数据页。"""
    body = """    <Box style={{ position: 'absolute', top: 162, left: 40, width: 1200, height: 236, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 12, justifyContent: 'center' }}>
            <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#0E3F8C' }}>固定考卷</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <Text style={{ fontSize: 56, fontWeight: 'bold', color: '#1E4FA8', lineHeight: 1.05 }}>35</Text>
                <Text style={{ fontSize: 20, color: '#4A5568', marginBottom: 8 }}>题检索 + 15 句意图</Text>
            </Box>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>每题标注正确片段（gold），覆盖同义换词与短词考点</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 12, justifyContent: 'center' }}>
            <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#0E3F8C' }}>基线门禁</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <Text style={{ fontSize: 56, fontWeight: 'bold', color: '#1E4FA8', lineHeight: 1.05 }}>0.05</Text>
                <Text style={{ fontSize: 20, color: '#4A5568', marginBottom: 8 }}>容差</Text>
            </Box>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>掉出容差，命令返回非零 —— 能直接进提交前检查</Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 12, justifyContent: 'center' }}>
            <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#0E3F8C' }}>当前水平</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <Text style={{ fontSize: 56, fontWeight: 'bold', color: '#0E3F8C', lineHeight: 1.05 }}>0.9714</Text>
                <Text style={{ fontSize: 20, color: '#4A5568', marginBottom: 8 }}>Hit@3 = MRR</Text>
            </Box>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>意图准确率 1.0；接真实向量 35 题全中</Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 412, left: 40, width: 1200, height: 224, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10 }}>
            <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>消融：机制有用，当场可见</Text>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 16, marginTop: 6 }}>
                <Box style={{ background: '#1E4FA8', borderRadius: 6, padding: '10px 18px' }}>
                    <Text style={{ fontSize: 26, fontWeight: 'bold', color: '#FFFFFF', fontFamily: 'SF Mono, Menlo, monospace' }}>0.9714</Text>
                </Box>
                <Text style={{ fontSize: 20, color: '#8B97A8' }}>→</Text>
                <Box style={{ background: '#D9534F', borderRadius: 6, padding: '10px 18px' }}>
                    <Text style={{ fontSize: 26, fontWeight: 'bold', color: '#FFFFFF', fontFamily: 'SF Mono, Menlo, monospace' }}>0.9571</Text>
                </Box>
                <Text style={{ fontSize: 16, color: '#4A5568', flex: 1 }}>关掉词面精排，MRR 立刻掉下来 —— 不需要「我觉得更好」</Text>
            </Box>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                评测用确定性向量（同版本任何人跑出同样分数），有基线 JSON 与容差门禁；接真实向量复验 35 题全中。
            </Text>
        </Box>
        <Box style={{ flex: 1, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 10 }}>
            <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>还能测出「变差」吗</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.75 }}>
                目前只能测「找到没」和「分类对不对」，<b>测不了「这次复习到底有没有用」</b>。
            </Text>
            <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 5, padding: 12, justifyContent: 'center' }}>
                <Text style={{ fontSize: 14, color: '#0E3F8C', lineHeight: 1.65 }}>
                    下一步要补任务级成功率，并用 pass^k 看稳定性 —— 报 pass@1 会把「偶尔能成」包装成「稳定可用」。
                </Text>
            </Box>
        </Box>
    </Box>"""
    return master(
        13, "证据 · 怎么判断今天没比昨天变笨", "怎么证明它没坏",
        "不是「我觉得挺准」，是每次改动都能复跑同一份考卷",
        body,
        "评测的价值不在分数高，在<b>分数掉了能立刻知道</b> —— 这是它能进 CI 的前提",
    )


def p14() -> str:
    """表格主导：六项能力。"""
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
        14, "边界 · 诚实清单", "六项能力：两项达标，三项一半，一项没做",
        "把没做的说出来，比多做一点更有用 —— 这是下一步的排序依据",
        body,
        "另外四项也标为「计划中」：多用户与数据隔离、在线监控聚合面板、Reranker 重排、反思式自我批判",
    )


def p15() -> str:
    """左文右图：记忆生命周期。"""
    body = """    <Box style={{ position: 'absolute', top: 160, left: 40, width: 560, height: 476, flexDirection: 'column', gap: 14 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>记忆为什么是最弱的一环</Text>
        <Box style={{ background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 18, gap: 10 }}>
            <Text style={{ fontSize: 16, color: '#4A5568', lineHeight: 1.75 }}>
                事实抽取用的是<b>正则规则</b>（只认「记住：X」「我在准备 X」这类明确句式），抽取后<b>全量注入</b>提示词。
            </Text>
            <Box style={{ background: '#FFF4F3', borderRadius: 5, padding: 12 }}>
                <Text style={{ fontSize: 15, color: '#D9534F', lineHeight: 1.7 }}>
                    表里只有 created_at，没有有效状态。<br />
                    大二说「我在准备四级」、大三说「我在准备考研」——<br />
                    两条会同时注入，模型两件都当真。
                </Text>
            </Box>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 8, padding: 18, gap: 8, justifyContent: 'center' }}>
            <Text style={{ fontSize: 19, fontWeight: 'bold', color: '#0E3F8C' }}>用得越久越脏</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.75 }}>
                记忆是无条件注入的，过期记忆会污染每一次对话。LongMemEval（ICLR 2025）的结论也是
                「简单记忆设计在时间推理上表现差」—— 这正是要补的短板。
            </Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', top: 160, left: 620, width: 620, height: 476, background: '#F7F9FC', border: '1px solid #D6DCE5', borderRadius: 8, padding: 20, gap: 14 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#0E3F8C' }}>记忆生命周期：三个状态</Text>
        <Box style={{ gap: 10 }}>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 12, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14 }}>
                <Box style={{ width: 88, height: 40, background: '#1E4FA8', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>有效</Text>
                </Box>
                <Text style={{ fontSize: 15, color: '#4A5568', flex: 1 }}>当前成立、参与注入</Text>
            </Box>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 12, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14 }}>
                <Box style={{ width: 88, height: 40, background: '#E5B54B', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>被替代</Text>
                </Box>
                <Text style={{ fontSize: 15, color: '#4A5568', flex: 1 }}>同类新事实写入时，旧的自动让位</Text>
            </Box>
            <Box style={{ flexDirection: 'row', alignItems: 'center', gap: 12, background: '#FFFFFF', border: '1px solid #D6DCE5', borderRadius: 6, padding: 14 }}>
                <Box style={{ width: 88, height: 40, background: '#8B97A8', borderRadius: 5, justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 16, color: '#FFFFFF', fontWeight: 'bold' }}>失效</Text>
                </Box>
                <Text style={{ fontSize: 15, color: '#4A5568', flex: 1 }}>到期或长期未被引用，不再注入</Text>
            </Box>
        </Box>
        <Box style={{ flex: 1, background: '#E8EFF8', borderRadius: 6, padding: 16, justifyContent: 'center', gap: 6 }}>
            <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#0E3F8C' }}>注入也要按需</Text>
            <Text style={{ fontSize: 15, color: '#4A5568', lineHeight: 1.7 }}>
                不全量拼进提示词，而是复用项目里已有的四路召回，只取与当前问题相关的几条。
            </Text>
        </Box>
    </Box>"""
    return master(
        15, "边界 · 最该先补的", "记忆是最弱的一环，也是最该先补的",
        "六项能力里唯一的「一半」里，问题最集中的地方",
        body,
        "下一步① 任务级评测　② 记忆的过期与删除　③ 更难的检索考卷 —— 都能在现有门禁里验证",
    )


def p16() -> str:
    """收束整版。"""
    return """<Slide style={{ width: 1280, height: 720, position: 'relative', background: '#0E3F8C', fontFamily: 'PingFang SC, Hiragino Sans GB, sans-serif' }}>
    <Image src="assets/p16-closing-desk.png" style={{ position: 'absolute', top: 0, right: 0, width: 520, height: 720, objectFit: 'cover' }} />
    <Box style={{ position: 'absolute', top: 0, right: 0, width: 520, height: 720, background: '#0E3F8C', opacity: 0.42 }} />

    <Box style={{ position: 'absolute', top: 96, left: 80, width: 700, flexDirection: 'column', gap: 22 }}>
        <Text style={{ fontSize: 16, color: '#A9C6EF', letterSpacing: 3 }}>收束</Text>
        <Text style={{ fontSize: 52, fontWeight: 'bold', color: '#FFFFFF', lineHeight: 1.3 }}>
            资料进去，题出来，复习排好
        </Text>
        <Box style={{ width: 72, height: 3, background: '#3D7BD9' }} />
        <Text style={{ fontSize: 21, color: '#C9DDF5', lineHeight: 1.7 }}>
            支撑这三件事的：每一步能恢复、每次写入先问、改动有没有变差算得出来。
        </Text>
    </Box>

    <Box style={{ position: 'absolute', top: 430, left: 80, width: 1120, flexDirection: 'row', gap: 16 }}>
        <Box style={{ flex: 1, background: '#1E4FA8', borderRadius: 8, padding: 18, gap: 8 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#FFFFFF' }}>整理资料</Text>
            <Text style={{ fontSize: 15, color: '#C9DDF5', lineHeight: 1.65 }}>传进来，按学科分好，能翻到第几页</Text>
        </Box>
        <Box style={{ flex: 1, background: '#1E4FA8', borderRadius: 8, padding: 18, gap: 8 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#FFFFFF' }}>出题</Text>
            <Text style={{ fontSize: 15, color: '#C9DDF5', lineHeight: 1.65 }}>按你的资料出，做错的方向多出几道</Text>
        </Box>
        <Box style={{ flex: 1, background: '#1E4FA8', borderRadius: 8, padding: 18, gap: 8 }}>
            <Text style={{ fontSize: 23, fontWeight: 'bold', color: '#FFFFFF' }}>复习</Text>
            <Text style={{ fontSize: 15, color: '#C9DDF5', lineHeight: 1.65 }}>今天练哪几题排好，翻得回原文那一页</Text>
        </Box>
    </Box>

    <Box style={{ position: 'absolute', bottom: 48, left: 80, flexDirection: 'row', alignItems: 'center', gap: 28 }}>
        <Box style={{ width: 4, height: 40, background: '#3D7BD9' }} />
        <Box style={{ flexDirection: 'column', gap: 3 }}>
            <Text style={{ fontSize: 16, color: '#FFFFFF' }}>知迹 ZhiJi · AI 学习私教与智能复习系统</Text>
            <Text style={{ fontSize: 14, color: '#8FB4E8' }}>284 项测试 · 检索 35 题考卷 Hit@3 = MRR = 0.9714 · 意图 15 句准确率 1.0</Text>
        </Box>
    </Box>
</Slide>
"""


PAGES = {
    3: p03, 4: p04, 5: p05, 6: p06, 7: p07, 8: p08, 9: p09,
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
