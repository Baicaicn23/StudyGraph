# 接口参考（给前端）

> 后端基址默认 `http://127.0.0.1:8011`。除上传外均为 JSON；`user_id` 缺省为 `local`。
> SSE 事件协议见下方 `/api/chat/stream`。

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
# 400 不支持的类型 / 无文本；413 文件过大
```

## 聊天（SSE）

```
POST /api/chat/stream
body: {"message": "我的笔记里怎么讲导数的？", "thread_id": "web-1",
       "user_id": "local", "knowledge_bases": ["高等数学"]}
→ text/event-stream
```

事件（`data` 为 JSON）：

```text
event: token      data: {"content": "..."}                     # 逐块输出，追加到最后一条助手消息
event: interrupt  data: {"action":"save_note","library":"...",
                         "title":"...","preview":"..."}         # HITL：弹确认框，等用户决定
event: guard      data: {"reason": "..."}                       # 输出护栏告警（可选）
event: done       data: {}                                      # 本回合结束
event: error      data: {"message": "..."}                      # 失败
```

```
POST /api/chat/resume                # 对 interrupt 作答后继续
body: {"thread_id": "web-1", "approved": true}
→ text/event-stream（同上）
```

> 前端用 `fetch` + `ReadableStream` 解析 SSE（`EventSource` 不支持 POST）。
> `thread_id` 相同即续接同一会话（断点持久化）。

## 学习闭环

```
POST /api/feedback                   # 记录错题（误区）
body: {"user_id":"local","library":"线性代数","question":"什么是特征值？","note":"我把特征向量搞混了"}
→ {"id": 1}

GET  /api/feedback?user_id=local
→ {"feedback": [{"id":1,"library":"...","question":"...","note":"...","created_at":...}]}
```

```
POST /api/practice/generate          # 出题
body: {"user_id":"local","source":"mistakes","library":"","count":3}
#   source: "mistakes"（从错题） | "knowledge_base"（从知识库，需 library）
→ {"questions":[{"id":1,"library":"线性代数","prompt":"...","source":"mistake","generator":"template","due_at":...}]}
# 400：没有可用错题 / 未选知识库 / 片段用尽

GET  /api/practice/due?user_id=local
→ {"questions":[{"id":1,"library":"...","prompt":"...","source":"...","due_at":...,"answered_count":0,"last_rating":null}]}

POST /api/practice/answer            # 作答自评（间隔重复 + 掌握度）
body: {"user_id":"local","question_id":1,"rating":"good"}
#   rating: again | hard | good | easy
→ {"question_id":1,"library":"线性代数","rating":"good","mastery":5,"due_at":...,"due_in_days":3.0}
```

## 今日复习 / 记忆 / 用量

```
GET /api/study/plan?user_id=local
→ {"due_questions":[...], "weak_libraries":[{"library":"线性代数","mastery":5,"updated_at":...}],
   "recent_mistakes":1, "suggestions":["复习「线性代数」（掌握度 5%）", ...]}

GET /api/memories?user_id=local
→ {"memories":["我在准备月底的微积分测验", ...]}

GET /api/usage?user_id=local&days=1
→ {"total_tokens":357,"by_model":[{"model":"study-mock","input_tokens":301,"output_tokens":56,"total_tokens":357,"calls":3}]}
```

## 建议的前端页面 ↔ 接口映射

| 页面 | 主要接口 |
| --- | --- |
| 聊天 | `POST /api/chat/stream`（+ `/resume` 处理 HITL） |
| 知识库管理 | `GET /api/knowledge/libraries`、`POST /api/knowledge/upload` |
| 练习 / 复习 | `POST /api/practice/generate`、`GET /api/practice/due`、`POST /api/practice/answer` |
| 错题本 | `POST|GET /api/feedback` |
| 今日复习 | `GET /api/study/plan` |
| 记忆 / 用量 | `GET /api/memories`、`GET /api/usage` |

> CORS 已放行 `http://localhost:3000` 与 `http://127.0.0.1:3000`。
