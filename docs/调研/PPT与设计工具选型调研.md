# PPT / 设计工具选型调研（10 项）

> 调研日期：2026-10-21 ｜ 对照对象：本项目「知迹」答辩 PPT（`docs/作品集/参赛/知迹答辩/`）
> 判据只有三条：**① 输出是不是原生可编辑 .pptx ② 能不能离线跑 ③ 能不能接进我们现有流程**

---

## 0. 先说结论

**这 10 个工具分三类，只有第二类能交报名材料。**

| 类别 | 工具 | 输出 | 能否作为提交材料 |
| --- | --- | --- | --- |
| ① HTML / 浏览器演示 | reveal.js、slidev（浏览器态）、impress.js、guizang-ppt-skill、frontend-slides、bento | HTML / PDF / 图片 | ❌ 交不了，但**适合录演示视频** |
| ② 原生可编辑 .pptx | **pandoc**、**ppt-master**、**OfficeCLI**、slidev（`pptx-editable`） | 真形状、真文本框 | ✅ |
| ③ 设计 / 素材辅助 | open-design、carbon | 原型 / 工作区、代码配图 | ⭕ 辅助，不是生成器 |

**对我们最重要的一条**：Marp 与 Slidev 的"可编辑导出"都**依赖 LibreOffice**；而本项目环境明确不装 LibreOffice。所以 Markdown 路里真正无依赖可用的只有 **pandoc**。

---

## 1. 逐项调研

### 1.1 ppt-master ⭐63.0k — 最正统的原生 PPTX 生成路线

- **工作流**：源材料 → Agent 读本地 SKILL.md → 内容分析与叙事规划 → **生成 SVG 视觉稿** → **转换为原生 DrawingML** → 注入模板/图表/表格/公式/动画 → 导出 `.pptx`
- **输出**：原生形状与连接线、可编辑文字与效果、**带 Edit Data 的原生图表**（需 `--native-charts-and-tables`）、原生表格、**可编辑 OMML 公式**、母版与版式继承（`p:sldMaster` / `p:sldLayout`）、切换与动画、演讲者备注与语音旁白
- **能否离线**：**否**。核心生成环节需要模型 API；图片搜索 / AI 生图 / 配音也各自可能要外部服务。作者原话：「The model sets the ceiling.」
- **已知限制**：不支持 SmartArt（作者明确"主动不做"）；快速模式不可恢复且无预览；可选 PDF 转换器依赖 PyMuPDF（**AGPL-3.0**，再分发要注意）
- **对我们**：**与现有路线是替代关系，不是互补**。它擅长"从一份文档 → 风格统一的高质量原生 pptx"；我们擅长"逐页精确控制版式与数据"。若要"一条命令出成品"，它更优；若要"第 6 页的表就长这样"，仍然是代码化生成（slidep）更可控。

### 1.2 OfficeCLI ⭐32.1k — 补上 slidep 缺的那几件事

- **形态**：面向智能体与自动化的 Office CLI，单个自包含二进制（内置 .NET 运行时），**不需要 Microsoft Office / LibreOffice / python-pptx**
- **能力**：读、写、创建、修改、删除、批量改、模板合并、校验（查文本溢出/格式不一致）、**HTML / PNG 渲染与实时预览**、MCP Server、Python / Node SDK
- **定位元素**：`/slide[1]/shape[1]` 这类路径，可**只改第 1 页第 1 个形状的文字**；`officecli view deck.pptx outline` 直接读大纲
- **对我们**：正好补齐我们这轮踩到的三个坑——
  ① 定点改字不用重灌整页；② **渲染 PNG 让 Agent 自己看版式**（比逐页 VLM 截图更省事）；③ `validate` 直接报文本溢出
- **可作为 Skill 安装**：`officecli install` 会装二进制 + skill 文件 + MCP 配置
- **代价**：多一个外部二进制依赖；Apache-2.0

### 1.3 pandoc ⭐46.6k — 最稳的「Markdown → 原生 pptx」

- **命令**：`pandoc slides.md -o slides.pptx --reference-doc=template.pptx`
- **输出**：**真 PowerPoint 形状、文本框、表格**，文字可选可编辑，继承 reference 的母版/主题色/字体/版式
- **能否离线**：**是**，单二进制、无运行时依赖
- **局限**：版式**受母版约束**（模板没有双栏版式就做不出双栏）；**数学公式不原生渲染**；复杂表格与 CSS 模式易崩；无 reference-doc 时出来是"白底加文字"，观感一般
- **对我们**：适合"快速把一份结构化讲义变成可编辑初稿"；但我们要的**表 + 双栏 + 精确网格**版式它表达不了，**不能替代 slidep**

### 1.4 slidev ⭐49.1k — 开发者向 Markdown 演示

- 浏览器内演示（Vue 3 + Vite），可执行代码、自定义组件、动画
- 导出：`slidev export --format pptx`（**图片版**）与 `--format pptx-editable`（**需 LibreOffice**；无对应对象的元素仍是图片）
- **对我们**：写作体验好，但交付链路上有 LibreOffice 依赖与图片化风险 → 只适合录屏

### 1.5 reveal.js ⭐72.4k / impress.js ⭐38.2k

- 纯 HTML 演示框架；impress.js 走 CSS3 3D 缩放平移，视觉炫
- **对我们**：均无原生 pptx 输出 → 只适合录屏；impress 的 3D 效果在学术答辩反而扣分

### 1.6 open-design ⭐101.8k

- 协作式 AI 设计智能体工作区，本地优先开源；做原型 / 网站 / App / 仪表盘 / PPT / 图 / 视频
- **对我们**：它是"工作区"不是"PPT 生成器"。我们已有完整前端与 PPT 流水线，增益有限 → **暂不引入**

### 1.7 carbon ⭐36.1k

- 源码 → 精美分享图（主题化、窗口拟态）
- **对我们**：**可补一页「关键实现：8 行核心代码 + 设计意图」**——这类页在毕设/答辩里很常见，我们现在没有（v3 的 p07 只有机制说明）→ 可选增强

### 1.8 frontend-slides ⭐30.8k / guizang-ppt-skill ⭐28.1k / bento-slides（本机已装）

- 均为**零依赖单文件 HTML**：frontend-slides 偏动画丰富的网页演示；guizang 偏杂志 / Swiss 排版 + 配图提示词 + 社媒封面
- **对我们**：视觉效果好，但交不了报名材料 → 定位为**录屏备用**（与 reveal.js 二选一）

---

## 2. 三种「Markdown/生成物 → pptx」输出模型（最容易踩坑的地方）

| 输出模型 | 代表工具 | 可编辑性 | 适用判断 |
| --- | --- | --- | --- |
| **原生 .pptx 生成** | pandoc、Quarto、ppt-master | 高（文本真可选） | **交付给别人继续改** → 首选 |
| **渲染后塞进 pptx** | Marp 默认、Slidev `--format pptx` | 低（整页是图） | 只为分享 / 录屏 |
| **半可编辑导出** | Marp `--pptx-editable`、Slidev `pptx-editable` | 中（部分元素仍是图，**依赖 LibreOffice**） | 需本地装 LO |

**还有一条与中文直接相关**：PPTX 用**查看者机器上的字体**渲染，字体缺失会被替换、换行全变（中日韩尤甚）。图片化导出不会有这个问题——但那正是它不可编辑的代价。**「字体稳定」与「文字可编辑」天然互斥**。

---

## 3. 对本项目的建议

| 建议 | 动作 | 成本 | 收益 |
| --- | --- | --- | --- |
| **A（推荐）** | 装 **OfficeCLI** 作为**补充**工具链：定点改字 / 渲染 PNG 自查 / `validate` 查溢出 | 一个二进制 + 一个 skill | 补齐 slidep 缺的读写与自查能力，**不动现有生成路线** |
| **B（可选）** | 用 **carbon** 补一页「关键实现：8 行核心代码 + 设计意图」 | 半小时 | 补上评审常期待看的"硬代码"证据 |
| **C（备选）** | 若将来要"丢一份 PDF 出一份高质量原生 pptx"，改用 **ppt-master** 路线 | 需建 SKILL 工作流 + 模型 API | 视觉与原生度都更强，**但版式可控性不如代码化生成** |
| **D（不建议）** | 把 pandoc 引入主流程 | 低 | 我们的版式（表 / 双栏 / 精确网格）它表达不了；只在"批量把讲义转初稿"时有用 |
| **E（仅录屏）** | reveal.js / guizang / frontend-slides 做**演示视频**的底片 | 低 | 视频环节更好看；**与提交材料无关** |

**结论**：**主生成路线维持"代码化生成 + 逐页视觉检查"（workbuddy-pptx / slidep）**——它的优势是"每页的版式与数据都可精确控制"，这正是答辩材料需要的；
**用 OfficeCLI 做补充**（读回、定点改、渲染自查），**用 carbon 补一页硬证据**，**用 HTML 系工具录视频**。

---

## 参考

- ppt-master：https://github.com/hugohe3/ppt-master
- OfficeCLI：https://github.com/iOfficeAI/OfficeCLI
- pandoc：https://pandoc.org/ ｜ PPTX 写出与 reference-doc
- slidev：https://github.com/slidevjs/slidev ｜ export `--format pptx / pptx-editable`
- reveal.js：https://github.com/hakimel/reveal.js ｜ impress.js：https://github.com/impress/impress.js
- carbon：https://github.com/carbon-app/carbon ｜ open-design：https://github.com/nexu-io/open-design
- frontend-slides：https://github.com/zarazhangrui/frontend-slides ｜ guizang-ppt-skill：https://github.com/op7418/guizang-ppt-skill

---

## 附：调研结论已落地（2026-10-21）

用户指定 `tw93/kami` 后，**它被采纳为答辩 PPT 的生成管线**（`kami_slides.py` → 原生可编辑 pptx），
与调研中"模板/设计系统路线优于自己拼版式"的判断一致。补充两条落地后才发现的事实：

- **Kami 的 PPTX 走 python-pptx**，其默认字体名只作用于西文（`a:latin`），中文要显式写
  `a:ea` / `a:cs`——否则换台机器中文就变样。这是"模板给了你设计系统，但没给你跨机器的字体安全"。
- ** Kami 自带 `TsangerJinKai02` 中文字体仅限个人免费使用**，商业使用需另行授权；
  本项目因此改用系统自带 `Songti SC`，避免把授权风险带进参赛材料。

本项目最终的工具组合：**kami（生成与设计系统）+ OfficeCLI（后处理与自查）**，
两者都本地可跑、不依赖生成式 API。
