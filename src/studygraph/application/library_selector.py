"""智能选库：让小模型根据问题从候选知识库里挑相关的子集。

多课程空间下知识库会越来越多，全库检索既慢又容易串出无关片段
（选「高等数学」却返回「四级英语」片段的教训）。这里用一次轻量的
模型调用先做判断：

- 输出必须是候选列表的子集（模型编造的名字一律过滤）；
- 挑不出 / 判断不了 / 模型不可用（Mock / None）→ 返回 None，
  调用方回落为「不限库」，绝不因为选库失败而拒答。
"""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from .ports import ChatModelPort

_SYSTEM_PROMPT = (
    "你是检索调度员。根据学生的问题，从候选知识库里选出与问题最相关的 1-3 个。"
    "只输出一个 JSON 字符串数组（例如 [\"高等数学\"]），"
    "不要输出候选之外的名字，不要解释，不要输出代码块。"
    "如果候选里没有与问题相关的知识库，输出 []。"
)


def _parse(content: str, libraries: list[str]) -> list[str] | None:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return None
    try:
        arr = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(arr, list):
        return None
    # 只保留候选之内的名字（去重保序）——模型编造的一律过滤
    chosen = [
        name
        for name in dict.fromkeys(str(item).strip() for item in arr)
        if name in libraries
    ]
    return chosen


async def select_libraries(
    model: ChatModelPort | None,
    *,
    question: str,
    libraries: list[str],
) -> list[str] | None:
    """返回与问题相关的知识库名子集；None = 判断不出（回落全库）。"""

    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return None
    if not libraries:
        return None
    try:
        response = await model.ainvoke(
            [
                SystemMessage(_SYSTEM_PROMPT),
                HumanMessage(
                    f"学生的问题：{question[:500]}\n"
                    f"候选知识库：{json.dumps(libraries, ensure_ascii=False)}"
                ),
            ]
        )
        chosen = _parse(str(getattr(response, "content", "")), libraries)
    except Exception:  # noqa: BLE001 — 判断失败回落全库
        return None
    return chosen or None
