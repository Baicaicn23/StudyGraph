# 接口参考（给前端）

> 后端基址默认 `http://127.0.0.1:8011`。除注明 `Form`/`multipart` 外均为 JSON；
> `user_id` 缺省为 `local`。SSE 事件协议见下方 `/api/chat/stream`。
> 更新时间：2026-10-10（对齐 fb01abf 之后的 main）。

## 健康检查

```
GET /api/health
→ {"status": "ok", "provider": "mock"}
```

## 知识库

```
GET /api/knowledge/libraries
→ {"libraries": [{"name": "线性代数", "document_count": 3}, ...]}
```

```
POST /api/knowledge/libraries      # 新建空库；重名幂等（视为已存在）
body(JSON): {"name": "线性代数"}
→ {"name": "线性代数"}             # 400 名称非法
```

```
GET /api/knowledge/documents?library=线性代数    # 某学科库下的资料列表（新的在前）
→ {"documents": [{"id": 1, "title": "特征值", "created_at": 1760000000.0, "chars": 120}, ...]}
```

```
GET /api/knowledge/document?id=1   # 单篇资料全文（笔记阅读页用）
→ {"document": {"id": 1, "title": "特征值", "content": "...", ...}}
# 404 资料不存在
```

```
PUT /api/knowledge/document        # 编辑资料：标题/正文更新并重建检索索引（切块+向量+FTS）
body(JSON): {"id": 1, "title": "特征值", "content": "..."}
→ {"id": 1, "title": "特征值"}
# 400 内容非法 / 404 资料不存在
```

```
DELETE /api/knowledge/document?id=1
→ {"deleted": 1}                   # 404 资料不存在
```

```
DELETE /api/knowledge/library?name=高等数学
→ {"deleted": "高等数学"}          # 删除整个库（资料与索引一起删）；404 库不存在
```

```
POST /api/knowledge/notes           # 写入一条笔记
body: {"library": "线性代数", "title": "特征值", "content": "..."}
→ {"id": 1, "library": "线性代数", "title": "特征值"}
```

```
POST /api/knowledge/documents        # 同上，长文本
body: {"library": "...", "title": "...", "content": "..."}
→ {"id": 1, "library": "...", "title": "..."}
```

```
POST /api/knowledge/upload           # multipart/form-data
form: library=高等数学   file=@导数笔记.md
→ {"id": 2, "library": "高等数学", "title": "导数笔记.md", "chars": 1234}
# 文本（PDF/TXT/MD）走抽取管线；图片（png/jpg/jpeg/webp）走视觉转写
# 400 不支持的类型 / 无文本 / Mock 模式传图；413 文件过大；502 视觉转写失败
```

## 项目空间（对话分组）

```
GET /api/projects                   # 首次访问自动建系统兜底空间「未归类」并收编无主会话
→ {"projects": [{"id": 1, "name": "未归类", "is_default": true,
                 "session_count": 16, ...}, ...]}
```

```
POST /api/projects                  # multipart/form-data
form: name=考研数学   user_id=local
→ {"id": 2, "name": "考研数学"}
# 400 名称空 / 409 同名项目已存在
```

```
PUT /api/projects/{project_id}      # 重命名，multipart/form-data
form: name=新名字
→ {"id": 2, "name": "新名字"}       # 404 项目不存在
```

```
DELETE /api/projects/{project_id}   # 级联删除：会话/消息/附件（含磁盘图片）一起清
→ {"deleted": 2, "sessions": 5}
# 400 系统兜底空间「未归类」不能删除 / 404 项目不存在
```

## 会话与消息

```
GET /api/chats?user_id=local&project_id=2     # project_id 可选，缺省=全部
→ {"chats": [{"id": 3, "project_id": 2, "thread_id": "web-abc",
              "title": "本周刷完二分查找", "updated_at": ...}, ...]}
```

```
GET /api/chats/{session_id}/messages   # 历史回放（含附件元数据与过程步骤）
→ {"messages": [{"id": 10, "role": "user", "content": "...",
                 "attachments": [{"id": 4, "name": "课件.pdf", "kind": "file"}],
                 "steps": [{"kind": "tool", "title": "检索知识库", "detail": "..."}],
                 "created_at": ...}, ...]}
```

```
GET /api/chat/activity?user_id=local&days=84    # 近 N 天提问频率（7≤days≤366，聊天页热力图）
→ {"days": [{"date": "2026-10-10", "questions": 3}, ...]}   # 恒 days 条、从旧到新、缺日补零
```

```
PUT /api/chats/{session_id}         # 重命名会话，multipart/form-data
form: title=新标题                  # （亦接受 project_id，但仅后端内部使用）
→ {"id": 3}                         # 404 会话不存在
```

```
DELETE /api/chats/{session_id}
→ {"deleted": 3}                    # 连带删消息与附件
```

## 聊天附件

```
POST /api/chat/attachments           # multipart/form-data
form: file=@课件.pdf   session_id=3(可选)   project_id=2(可选)   user_id=local
→ {"id": 4, "filename": "课件.pdf", "kind": "file", "chars": 5200}
# 文本（PDF/TXT/MD）抽文本；图片（png/jpg/jpeg/webp）走视觉转写 → kind="image"，
# 且原文件落盘供预览。单文件 ≤5MB（413）；Mock 模式传图 400；转写失败 502。
# project_id 记录附件归属：消息发出前会话可能还不存在，删项目时才能清掉孤儿附件。
```

```
GET /api/chat/attachments/{attachment_id}/raw?user_id=local
→ FileResponse（图片原文件，消息缩略图/点击预览用）
# 404 附件不存在（含越权）或文件已丢失
```

## 聊天（SSE）

```
POST /api/chat/stream
body: {"message": "我的笔记里怎么讲导数的？", "thread_id": "web-1",
       "user_id": "local", "knowledge_bases": ["高等数学"],
       "session_id": 3,              # 可选：续接已保存会话；缺省自动新建（自动保存+自动起标题）
       "project_id": 2,              # 可选：本轮记忆按课程空间隔离；缺省兜底到「未归类」
       "attachment_ids": [4]}        # 可选：≤6 个；单附件取前 8000 字拼进消息
→ text/event-stream
```

事件（`data` 为 JSON）：

```text
event: token      data: {"content": "..."}                     # 逐块输出，追加到最后一条助手消息
event: step       data: {"kind": "thinking"|"tool", "title": "理解问题",
                         "detail": "..."}                       # 智能体过程流（随消息落库，回放可见）
event: status     data: {"label": "检索知识库"}                 # 节点/工具进展（状态行）
event: session    data: {"id": 3, "title": "导数与极限"}        # 会话保存 / 自动标题生成后重推
event: interrupt  data: {"action":"save_note","library":"...",
                         "title":"...","preview":"..."}         # HITL：弹确认框，等用户决定
event: guard      data: {"reason": "..."}                       # 输出护栏告警（可选）
event: done       data: {}                                      # 本回合结束
event: error      data: {"message": "..."}                      # 失败
```

```
POST /api/chat/resume                # 对 interrupt 作答后继续
body: {"thread_id": "web-1", "approved": true, "session_id": 3, "user_id": "local"}
→ text/event-stream（同上）
```

> 前端用 `fetch` + `ReadableStream` 解析 SSE（`EventSource` 不支持 POST）。
> `thread_id` 相同即续接同一会话（断点持久化，LangGraph checkpointer）。
> 输入护栏（越界/注入）在进入图之前拦截，直接流式返回拒绝话术。

## 学习闭环

```
POST /api/feedback                   # 记录错题（误区）
body: {"user_id":"local","library":"线性代数","question":"什么是特征值？","note":"我把特征向量搞混了",
       "kind":"concept"}   # 错误类型可选：concept|step|condition|calc|wording
→ {"id": 1}                        # 400 非法错误类型

GET  /api/feedback?user_id=local
→ {"feedback": [{"id":1,"library":"...","question":"...","note":"...","created_at":...}]}

DELETE /api/feedback/{feedback_id}?user_id=local
→ {"deleted": 1}                     # 404 误区记录不存在
```

```
POST /api/practice/generate          # 出题
body: {"user_id":"local","source":"mistakes","library":"","count":3,
       "difficulty":"auto","mistake_ids":[1,2]}
#   source: "mistakes"（从错题） | "knowledge_base"（从知识库，需 library）
#   difficulty: "basic" | "apply" | "transfer" | "auto"（auto 按该学科掌握度分档：
#               <40% basic / <80% apply / >=80% transfer）
→ {"questions":[{"id":1,"library":"线性代数","prompt":"...","source":"mistake",
                 "generator":"template","difficulty":"apply","due_at":...}]}
#  mistake_ids 非空 → 按**选定错题**出变式题（一条误区一道），忽略 source/library 的筛选
# 400：没有可用错题 / 未选知识库 / 片段用尽 / 选中的错题都出过题 / 错题不存在
```

```
POST /api/practice/generate/stream   # 流式出题：每出一题推一帧（练习页进度）
body: {"user_id":"local","source":"knowledge_base","library":"数据结构",
       "count":3,"difficulty":"auto"}
→ text/event-stream
# event: progress  data: {"done": 2, "total": 3, "library": "数据结构", "difficulty": "apply"}
# event: done      data: {"questions": [...]}      # 全量题目（同 /generate 的字段）
# event: error     data: {"message": "..."}        # 业务错误也走事件流，不回 4xx
# 注意：实际生成数受"未用过的片段数"限制，total 是真实候选数而非请求的 count
```

```
GET  /api/practice/due?user_id=local
→ {"questions":[{"id":1,"library":"...","prompt":"...","source":"...","difficulty":"...",
                 "due_at":...,"answered_count":0,"last_rating":null}]}

POST /api/practice/answer            # 作答自评（间隔重复 + 掌握度）
body: {"user_id":"local","question_id":1,"rating":"good"}
#   rating: again | hard | good | easy
→ {"question_id":1,"library":"线性代数","rating":"good","mastery":5,"due_at":...,"due_in_days":3.0}

DELETE /api/practice/{question_id}?user_id=local
→ {"deleted": 1}                     # 404 练习题不存在（连带删作答记录）
```

## 今日复习 / 记忆 / 用量

```
GET /api/study/plan?user_id=local
→ {"due_questions":[...], "weak_libraries":[{"library":"线性代数","mastery":5,"updated_at":...}],
   "recent_mistakes":1, "suggestions":["复习「线性代数」（掌握度 5%）", ...]}

GET /api/study/activity?user_id=local&days=30     # 学习热力图（1≤days≤60）
→ {"days": [{"date":"2026-10-09","count":12}, ...]}

GET /api/memories?user_id=local&project_id=2
# project_id 缺省 → 全部记忆；传了 → 只看该项目（记忆按项目隔离，对话记忆专属）
→ {"memories":[{"id":7,"content":"我在准备月底的微积分测验","project_id":"2",...}]}

DELETE /api/memories/{memory_id}?user_id=local
→ {"deleted": 7}                     # 404 记忆不存在

GET /api/usage?user_id=local&days=1
→ {"total_tokens":357,
   "by_model":[{"model":"study-mock","input_tokens":301,"output_tokens":56,
                "total_tokens":357,"calls":3}],
   "by_day":[{"day":"2026-10-09","total_tokens":1234}, ...],
   "daily_token_budget":200000}
```

## 日程（时间轴 + 收件箱）

> date 为空的日程任务 = 留在收件箱；时间轴固定 06:00–24:00。
> `start_minutes` 是当天分钟数（0–1439）。

```
GET /api/schedule?date=2026-10-10        # 某天时间轴 + 收件箱计数（页面一次拿全）
→ {"date": "2026-10-10",
   "tasks": [{"id": 1, "title": "背单词", "note": "", "date": "2026-10-10",
              "start_minutes": 360, "duration_minutes": 30, "done": false, ...}],
   "inbox_count": 3}
# 400 日期格式必须是 YYYY-MM-DD
```

```
GET /api/schedule/inbox?user_id=local
→ {"tasks": [{"id": 2, "title": "写实验报告", "date": null, "start_minutes": null,
              "duration_minutes": 90, "done": false, ...}]}
```

```
GET /api/schedule/week?date=2026-10-10    # 周条密度（周日开头的 7 天）
→ {"start": "2026-10-04", "end": "2026-10-10",
   "days": [{"date": "2026-10-04", "total": 2, "done": 1}, ...]}
```

```
POST /api/schedule/tasks                  # 新建（date 缺省 = 进收件箱）
body: {"title": "复习特征值", "note": "教材 P120", "duration_minutes": 45,
       "date": "2026-10-10", "start_minutes": 1265}   # date 给了但 start_minutes 缺省 → 自动落最早空档
→ {"task": {...}}
# 400 标题空/日期非法/时长越界；422 参数不合法
```

```
PUT /api/schedule/tasks/{id}              # 更新（只传要改的字段）
body: {"title": "新标题", "note": "...", "date": "2026-10-11",
       "start_minutes": 600, "duration_minutes": 60, "done": true}
→ {"task": {...}}                         # 400 任务不存在 / 无字段可更新
```

```
POST /api/schedule/tasks/{id}/arrange?date=2026-10-10   # 一键安排：落到该日最早空档
POST /api/schedule/tasks/{id}/unarrange                 # 退回收件箱（清日期与时间，保留时长）
→ {"task": {...}}
```

```
DELETE /api/schedule/tasks/{id}?user_id=local
→ {"deleted": 1}                          # 404 任务不存在
```

## 建议的前端页面 ↔ 接口映射

| 页面 | 主要接口 |
| --- | --- |
| 聊天 `/` | `POST /api/chat/stream`（+ `/resume` 处理 HITL）、`/api/chat/attachments`（上传/预览）、`GET /api/chat/activity`（提问热力图）、`GET /api/study/plan`（欢迎区数据卡片） |
| 全局侧栏（对话区） | `GET|POST /api/projects`、`PUT|DELETE /api/projects/{id}`、`GET /api/chats`、`PUT|DELETE /api/chats/{id}`、`GET /api/chats/{id}/messages` |
| 知识库管理 | `GET|POST /api/knowledge/libraries`、`DELETE /api/knowledge/library`、`GET|PUT|DELETE /api/knowledge/document`、`POST /api/knowledge/upload` |
| 练习 / 复习 | `POST /api/practice/generate/stream`（流式出题进度）、`GET /api/practice/due`、`POST|DELETE /api/practice/...` |
| 错题本 | `POST|GET /api/feedback`、`DELETE /api/feedback/{id}` |
| 今日复习 | `GET /api/study/plan`、`GET /api/study/activity` |
| 日程 `/schedule` | `GET /api/schedule`、`/api/schedule/inbox`、`/api/schedule/week`、`POST|PUT|DELETE /api/schedule/tasks...`、`POST .../arrange`、`POST .../unarrange` |
| 记忆 / 用量 | `GET /api/memories`、`DELETE /api/memories/{id}`、`GET /api/usage` |

> CORS 已放行 `http://localhost:3000` 与 `http://127.0.0.1:3000`。
