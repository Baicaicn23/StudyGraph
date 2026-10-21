# 知迹答辩 · HTML 演示版

用 [html-ppt-skill](https://github.com/lewislulu/html-ppt-skill)（MIT）生成的 13 页答辩演示。
**这一版是新的独立产物**，与同目录上级的 `知迹答辩/`（python-pptx 生成的原生可编辑 pptx）是两套并列方案。

## 怎么用

| 用途 | 怎么做 |
| --- | --- |
| 本地放映 | 双击 `index.html`（零构建、零依赖） |
| 演讲者模式 | 放映中按 **S**：弹出演讲者窗口（当前页 / 下一页 / 讲稿 / 计时器），与观众窗口同步 |
| 备注抽屉 | 按 **N** 看当前页讲稿 |
| 总览网格 | 按 **O** 一屏看完全部页 |
| 换主题 | 按 **T** 循环（默认 `academic-paper`，另有 `swiss-grid` / `engineering-whiteprint` / `editorial-serif` / `minimal-white`） |
| 全屏 / 翻页 | **F** / **← →** / 空格 |

## 交付物

| 文件 | 说明 |
| --- | --- |
| `index.html` | **可编辑源文件**——改文案、改版式都在这里改 |
| `知迹答辩.pptx` | 13 页 16:9，**每页为整页渲染图**（版式 100% 还原；PowerPoint 里不能直接改字，要改回 HTML 改完重新导出） |
| `知迹答辩.pdf` | 13 页，打印与分发用 |
| `png/index_01..13.png` | 每页 1920×1080 渲染图（PPTX / PDF 的来源） |
| `assets/` | 主题、排版、动画、运行时（来自上游 skill，MIT） |
| `img/ui-knowledge.png` | 知识库页实拍（第 11 页用） |

## 重新生成

```bash
D="$PWD"
# 1) 改 index.html
# 2) 渲染每页 PNG（需要本机 Chrome）
bash ~/.agents/skills/html-ppt-skill/scripts/render.sh "$D/index.html" 13 "$D/png"
# 3) 合成 PPTX 与 PDF
uv run --with python-pptx --with pillow python - <<'PY'
from pptx import Presentation
from pptx.util import Inches
from PIL import Image
import glob
files = sorted(glob.glob("png/index_*.png"))
prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
for f in files:
    prs.slides.add_slide(prs.slide_layouts[6]).shapes.add_picture(f, 0, 0, width=prs.slide_width, height=prs.slide_height)
prs.save("知迹答辩.pptx")
ims = [Image.open(f).convert("RGB") for f in files]
ims[0].save("知迹答辩.pdf", save_all=True, append_images=ims[1:], resolution=144.0)
PY
```

## 讲稿

每页都写了口播提纲，存放在该页的 `<aside class="notes">`（放映时不可见，按 S 或 N 调出）。
写法遵循三条：**提示信号而非逐字稿、每页 150–300 字、口语**。

## 已知限制

- 字体走 Google Fonts CDN，**离线时回退到系统字体**，换行与版式会与本机预览略有差异；
  离线展示请提前下载字体或改用 `assets/base.css` 里的系统字体栈。
- PPTX 是**每页一张图**，在 PowerPoint 里改不了文字；需要改文案请回到 `index.html`。
- CSS 动画与 Canvas 特效只在浏览器里有，导出为 PNG/PDF 时只捕获静态帧。
