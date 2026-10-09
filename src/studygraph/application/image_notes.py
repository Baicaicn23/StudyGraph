"""图片 → Markdown 笔记（视觉转写）——应用层编排。

学生把课件拍照、板书截图传进知识库，由（带原生视觉能力的）多模态模型
转写成结构化 Markdown 后入库。失败时抛 `ImageNoteError`，由接口层转成
HTTP 错误——与 question_writer 的"永不抛异常"不同，这里失败必须让用户
知道（上传是显式动作，静默降级会产生垃圾笔记）。
"""

from __future__ import annotations

import base64

from langchain_core.messages import HumanMessage

from ..domain.note_style import NOTE_STYLE_BRIEF
from ..infrastructure.extract import image_mime

_VISION_PROMPT = (
    "你是学习资料整理助手。把这张图片（课件、板书、笔记或习题）整理成一份"
    "结构化 Markdown 学习笔记，要求：\n"
    "1. 内容忠实于图片：保留原文的知识结构与细节，"
    "字迹或印刷看不清的地方用「（此处无法辨认）」标注，不要编造内容；\n"
    "2. 如果图片里有习题，原题收录进「例题」小节，不要自己做删改；\n"
    f"3. {NOTE_STYLE_BRIEF}\n"
    "4. 只输出 Markdown 正文，不要额外解释。"
)


class ImageNoteError(ValueError):
    pass


async def image_to_markdown(model, filename: str, data: bytes) -> str:
    """把一张图片转写成 Markdown 文本；模型为空或转写失败时抛错。"""

    if model is None:
        raise ImageNoteError("当前没有可用的视觉模型")
    mime = image_mime(filename) or "image/png"
    encoded = base64.b64encode(data).decode("ascii")
    message = HumanMessage(
        content=[
            {"type": "text", "text": _VISION_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            },
        ]
    )
    try:
        response = await model.ainvoke([message])
    except Exception as exc:  # noqa: BLE001 — 底层错误转成可读提示
        raise ImageNoteError(f"图片识别失败：{exc}") from exc
    text = str(getattr(response, "content", "") or "").strip()
    # 有些模型把 Markdown 包在代码块里，剥掉外层围栏。
    if text.startswith("```"):
        text = text.strip("`").lstrip("markdown\n").strip()
    if len(text) < 10:
        raise ImageNoteError("图片识别结果为空，请换一张更清晰的照片")
    return text
