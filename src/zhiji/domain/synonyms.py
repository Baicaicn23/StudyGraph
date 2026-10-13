"""查询扩写用的同义词组表（纯数据 + 纯函数，零模型调用、确定性）。

**为什么需要**：学生用口语或简称提问，资料里写的是教材术语或英文原名，字面
不同 → trigram FTS 与关键词路都召不回来。实测三个空洞：「本征值」搜不到
「特征值」文档、「queue」搜不到「队列」文档、长查询里 2 字关键词被 jieba 的
≥3 字过滤静默丢弃。这里解决前两个——维护**等价术语组**：组内任一术语出现在
查询里，就用同组其它术语补一路召回（原查询的排名不受影响）。

**两条来源**：① 中文异名（本征值 / 特征值）；② 中英对照（队列 / queue）——
中文资料夹英文术语极常见。

**表刻意保守**：只收**无歧义**的等价词，宁可少扩不可错扩——多扩会污染精确率，
所以扩写路在 RRF 融合时按低权重（默认 0.5）计入。可用 ``ZHIJI_SYNONYMS_FILE``
指向 JSON 追加自定义组（格式：``[["术语甲", "术语乙"], ...]``）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 每组 = 一组可互换的等价术语。保守收录：字面不同但语义等价的教材术语。
DEFAULT_GROUPS: tuple[tuple[str, ...], ...] = (
    # —— 高等数学 ——
    ("导数", "微商"),
    ("导数", "derivative"),
    ("微分", "differential"),
    ("积分", "integral"),
    ("定积分", "definite integral"),
    ("极限", "limit"),
    ("凹凸性", "凸性"),
    ("数列", "序列"),
    # —— 线性代数 ——
    ("向量", "矢量"),
    ("矩阵", "matrix"),
    ("行列式", "determinant"),
    ("特征值", "本征值"),
    ("特征向量", "本征向量"),
    ("转置", "transpose"),
    # —— 概率统计 ——
    ("概率", "几率"),
    ("期望", "均值", "平均值"),
    ("方差", "variance"),
    ("标准差", "均方差"),
    ("正态分布", "高斯分布"),
    # —— 数据结构与计算机基础 ——
    ("队列", "queue"),
    ("栈", "stack"),
    ("数组", "array"),
    ("链表", "linked list"),
    ("二叉树", "binary tree"),
    ("哈希表", "散列表", "hash table"),
    ("排序", "sort"),
    ("查找", "搜索"),
    ("遍历", "traversal"),
    ("递归", "recursion"),
    ("迭代", "iteration"),
    ("时间复杂度", "time complexity"),
    ("进程", "process"),
    ("线程", "thread"),
    ("死锁", "deadlock"),
    ("缓存", "cache"),
    # —— 大学物理 ——
    ("位移", "displacement"),
    ("速度", "velocity"),
    ("加速度", "acceleration"),
    ("动量", "momentum"),
)

_ASCII_TERM_RE = re.compile(r"^[a-z0-9][a-z0-9 +#+.\-]*$")


def _contains(haystack: str, needle: str) -> bool:
    """判断术语是否出现在文本里。

    英文/数字术语按**词边界**匹配（否则 "sort" 会命中 "consortium"、方向相反）；
    中文术语直接子串匹配。单字符术语一律忽略（太泛，只会引入噪声）。
    """

    if len(needle) < 2:
        return False
    if _ASCII_TERM_RE.match(needle):
        pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    return needle in haystack


def expand_terms(
    text: str, groups: tuple[tuple[str, ...], ...] | None = None
) -> list[str]:
    """返回与查询中术语等价的扩展词。

    ``groups`` 为 None 时用内置表（传 ``()`` 可彻底关闭扩写）。查询里已经出现
    的术语不重复返回——扩写的意义是补**查询没写的**那一面。
    """

    active = DEFAULT_GROUPS if groups is None else groups
    source = (text or "").lower()
    if not source:
        return []
    found: list[str] = []
    for group in active:
        lowered = [(term, term.lower()) for term in group]
        if not any(_contains(source, low) for _term, low in lowered):
            continue
        for term, low in lowered:
            if _contains(source, low) or term in found:
                continue
            found.append(term)
    return found


def load_synonym_groups(path: str | Path = "") -> tuple[tuple[str, ...], ...]:
    """内置组 + 可选 JSON 文件追加（每项 = 一组等价术语的字符串数组）。

    文件不存在/格式非法/单组不足两个术语 → 一律忽略该部分，不阻塞启动。
    """

    groups: list[tuple[str, ...]] = list(DEFAULT_GROUPS)
    target = str(path or "").strip()
    if not target:
        return tuple(groups)
    file = Path(target)
    if not file.is_file():
        return tuple(groups)
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return tuple(groups)
    if not isinstance(payload, list):
        return tuple(groups)
    for item in payload:
        if not isinstance(item, list):
            continue
        terms = tuple(str(term).strip() for term in item if str(term).strip())
        if len(terms) >= 2:
            groups.append(terms)
    return tuple(groups)
