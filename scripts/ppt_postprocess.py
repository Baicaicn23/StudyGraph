#!/usr/bin/env python3
"""答辩 PPT 交付后处理：写页名 → 出自查总览 → 校验。

背景：`.slide` 源文件经 `slidep` 生成后，每页的标题是普通文本框，**不是 PowerPoint
的标题占位符**。后果是：在 PowerPoint 的「大纲视图」里，11 页标题全是空白；任何
按标题检索或按页名跳转的工具也读不到内容。给每页写入**页名**（slide name）后，
文件自带一份可读的大纲（`officecli view deck.pptx outline` 能读到）。

同时提供两件我们反复需要的能力：
- `--render`：把整份 deck 渲染成一张缩略图总览，**一眼看完 11 页版式**（比逐页
  截图 + 视觉模型检查快得多，也不受接口限流影响）；
- 校验：文本溢出、格式不一致等问题由 `officecli validate` 报出。

前置：已安装 OfficeCLI（单二进制，无需 Office / LibreOffice / python-pptx）。
    curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash

⚠️ **用 `slidep upsert-dsl` 重灌某页后，必须重跑一次本脚本**：重灌会整页替换，
   该页刚写好的页名会被一起冲掉。

⚠️ **写入前必须关闭 WPS / PowerPoint 里的该文件**：文件被打开时编辑器持有写句柄，
   命令会报 "Updated" 但**不会落盘**（页名写不进去，文件修改时间不变）。

用法：
    uv run python scripts/ppt_postprocess.py --ppt docs/作品集/参赛/知迹答辩/知迹答辩.pptx
    uv run python scripts/ppt_postprocess.py --ppt <path> --render /tmp/deck-grid.png
    uv run python scripts/ppt_postprocess.py --ppt <path> --titles <自定义 json> --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DECK = REPO_ROOT / "docs/作品集/参赛/知迹答辩/知迹答辩.pptx"
DEFAULT_TITLES = REPO_ROOT / "docs/作品集/参赛/知迹答辩/slide_titles.json"


def _officecli() -> str:
    found = shutil.which("officecli")
    if not found:
        for candidate in (Path.home() / ".local/bin/officecli", Path("/usr/local/bin/officecli")):
            if candidate.exists():
                return str(candidate)
        raise SystemExit(
            "找不到 officecli。请先安装：\n"
            "  curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash"
        )
    return found


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def is_locked(ppt: Path) -> bool:
    """文件是否被 WPS / PowerPoint 打开（占用时写入不会落盘）。"""

    if sys.platform != "darwin":
        return False
    try:
        out = subprocess.run(
            ["lsof", "-nP", str(ppt)], capture_output=True, text=True, timeout=20
        ).stdout
    except Exception:  # noqa: BLE001 — 探测失败不阻断流程
        return False
    return "wpsoffice" in out or "Microsoft PowerPoint" in out or "soffice" in out



def _names_on_disk(ppt: Path, titles: dict[str, str]) -> set[str]:
    """直接读 pptx 内的 XML，确认页名真的写进了文件（而不是只在内存里）。"""

    import zipfile

    found: set[str] = set()
    try:
        with zipfile.ZipFile(ppt) as archive:
            for name in archive.namelist():
                if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                    continue
                xml = archive.read(name).decode("utf-8")
                for index, title in titles.items():
                    if title in xml:
                        found.add(index)
    except (OSError, zipfile.BadZipFile):
        return set()
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="答辩 PPT 交付后处理")
    parser.add_argument("--ppt", type=Path, default=DEFAULT_DECK, help="目标 pptx")
    parser.add_argument("--titles", type=Path, default=DEFAULT_TITLES, help="页名 JSON")
    parser.add_argument("--render", type=Path, default=None, help="输出缩略图总览 PNG")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要做的操作")
    args = parser.parse_args()

    ppt = args.ppt.resolve()
    if not ppt.exists():
        raise SystemExit(f"找不到文件：{ppt}")
    titles = json.loads(args.titles.read_text(encoding="utf-8"))

    cli = _officecli()

    if is_locked(ppt):
        print(f"⚠️  {ppt.name} 正被 WPS / PowerPoint 打开，写入不会落盘。")
        print("   请先关闭该文件再运行（或先保存你的修改再关闭）。")
        return 2

    if args.dry_run:
        for index, title in sorted(titles.items(), key=lambda kv: int(kv[0])):
            print(f"  第 {index:>2} 页 name = {title}")
        return 0

    # ⚠️ 必须用**常驻模式**（open → 多次 set → close）：一次性 `set` 进程退出时
    # 不会把内存里的改动落盘，命令照样报 "Updated"，但文件内容不变
    # （症状：文件修改时间不动、zip 内 XML 里搜不到页名）。
    _run([cli, "open", str(ppt)])
    failed = []
    for index, title in sorted(titles.items(), key=lambda kv: int(kv[0])):
        code, out = _run([cli, "set", str(ppt), f"/slide[{index}]", "--prop", f"name={title}"])
        if code != 0 or "Updated" not in out:
            failed.append((index, out[:120]))
    _run([cli, "close", str(ppt)])

    # 验收以**文件内容**为准，不信 get 的返回（它可能读的是内存状态）
    landed = _names_on_disk(ppt, titles)
    missing = [i for i in titles if str(i) not in landed]

    if failed or missing:
        print("✗ 写页名失败：")
        for index, reason in failed:
            print(f"   第 {index} 页：{reason}")
        if missing:
            print(f"   复查 zip 内容：这些页的页名没进文件 → {missing}")
            print("   （文件被占用时写入不落盘；或未用常驻模式 close）")
        return 1

    print(f"✓ 已写入 {len(titles)} 页的页名")

    code, out = _run([cli, "view", str(ppt), "outline"])
    if code == 0:
        for line in out.splitlines()[:4]:
            print("   " + line)

    if args.render:
        code, out = _run(
            [cli, "view", str(ppt), "screenshot", "--grid", "3", "-o", str(args.render)]
        )
        print(f"{'✓' if code == 0 else '✗'} 总览渲染：{args.render} {out[-60:] if code else ''}")

    code, out = _run([cli, "validate", str(ppt)])
    print(f"{'✓' if code == 0 else '✗'} 校验：{out.strip()[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
