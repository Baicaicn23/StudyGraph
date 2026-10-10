// 与 StudyGraph 后端（FastAPI + SSE）通信的客户端。
// SSE 事件协议见 docs/参考/API一览.md：token / interrupt / guard / done / error。

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8011";

export interface Library {
  name: string;
  document_count: number;
}

export interface DocumentItem {
  id: number;
  title: string;
  created_at: number;
  chars: number;
}

export interface Question {
  id: number;
  library: string;
  prompt: string;
  source: string;
  generator?: string;
  difficulty?: string;
  due_at: number;
  answered_count?: number;
  last_rating?: string | null;
}

export interface Feedback {
  id: number;
  library: string;
  question: string;
  note: string;
  created_at: number;
}

export interface WeakLibrary {
  library: string;
  mastery: number;
  updated_at: number;
}

export interface StudyPlan {
  due_questions: Question[];
  weak_libraries: WeakLibrary[];
  recent_mistakes: number;
  suggestions: string[];
}

export interface UsageSummary {
  total_tokens: number;
  daily_token_budget?: number;
  by_model: {
    model: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    calls: number;
  }[];
  by_day?: { date: string; total_tokens: number }[];
}

export interface ActivityDay {
  date: string;
  exercises: number;
  mistakes: number;
}

export interface AnswerResult {
  question_id: number;
  library: string;
  rating: string;
  mastery: number;
  due_at: number;
  due_in_days: number;
}

export type PracticeRating = "again" | "hard" | "good" | "easy";
export type PracticeSource = "knowledge_base" | "mistakes";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error("无法连接后端，请确认服务已启动。");
  }
  if (!response.ok) {
    let detail = `请求失败：${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- 知识库 ---------------------------------------------------------------

export async function getHealth(): Promise<{
  status: string;
  provider: string;
}> {
  return requestJson<{ status: string; provider: string }>("/api/health");
}

export async function listLibraries(): Promise<Library[]> {
  const data = await requestJson<{ libraries: Library[] }>(
    "/api/knowledge/libraries",
  );
  return data.libraries;
}

export async function createLibrary(name: string): Promise<void> {
  await postJson("/api/knowledge/libraries", { name });
}

export async function listDocuments(library: string): Promise<DocumentItem[]> {
  const data = await requestJson<{ documents: DocumentItem[] }>(
    `/api/knowledge/documents?library=${encodeURIComponent(library)}`,
  );
  return data.documents;
}

export interface KnowledgeDocument {
  id: number;
  library: string;
  title: string;
  content: string;
  created_at: number;
}

export async function getDocument(id: number): Promise<KnowledgeDocument> {
  const data = await requestJson<{ document: KnowledgeDocument }>(
    `/api/knowledge/document?id=${id}`,
  );
  return data.document;
}

export async function updateDocument(
  id: number,
  title: string,
  content: string,
): Promise<void> {
  await requestJson("/api/knowledge/document", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, title, content }),
  });
}

export async function deleteDocument(id: number): Promise<void> {
  await requestJson(`/api/knowledge/document?id=${id}`, { method: "DELETE" });
}

export async function deleteLibrary(name: string): Promise<void> {
  await requestJson(
    `/api/knowledge/library?name=${encodeURIComponent(name)}`,
    { method: "DELETE" },
  );
}

export function addNote(
  library: string,
  title: string,
  content: string,
): Promise<unknown> {
  return postJson("/api/knowledge/notes", { library, title, content });
}

export async function uploadDocument(
  library: string,
  file: File,
): Promise<{ title: string; chars: number }> {
  const form = new FormData();
  form.append("library", library);
  form.append("file", file);
  return requestJson("/api/knowledge/upload", { method: "POST", body: form });
}

// --- 学习闭环 -------------------------------------------------------------

// 出题难度：auto 按学科掌握度自动分档（<40 基础 / <80 进阶 / >=80 迁移）
export type PracticeDifficulty = "auto" | "basic" | "apply" | "transfer";

export async function generatePractice(
  source: PracticeSource,
  library: string,
  count: number,
  difficulty: PracticeDifficulty = "auto",
): Promise<Question[]> {
  const data = await postJson<{ questions: Question[] }>(
    "/api/practice/generate",
    { source, library, count, difficulty },
  );
  return data.questions;
}

export async function dueQuestions(): Promise<Question[]> {
  const data = await requestJson<{ questions: Question[] }>("/api/practice/due");
  return data.questions;
}

export function answerQuestion(
  questionId: number,
  rating: PracticeRating,
): Promise<AnswerResult> {
  return postJson("/api/practice/answer", {
    question_id: questionId,
    rating,
  });
}

export async function listFeedback(): Promise<Feedback[]> {
  const data = await requestJson<{ feedback: Feedback[] }>("/api/feedback");
  return data.feedback;
}

export function addFeedback(
  library: string,
  question: string,
  note: string,
): Promise<{ id: number }> {
  return postJson("/api/feedback", { library, question, note });
}

export async function deleteFeedback(id: number): Promise<void> {
  await requestJson(`/api/feedback/${id}`, { method: "DELETE" });
}

export async function deleteQuestion(id: number): Promise<void> {
  await requestJson(`/api/practice/${id}`, { method: "DELETE" });
}

export function studyPlan(): Promise<StudyPlan> {
  return requestJson<StudyPlan>("/api/study/plan");
}

export interface SprintDay {
  day: number;
  date: string;
  focus: string;
  mastery: number;
  tasks: string[];
}

export interface SprintPlan {
  days: number;
  schedule: SprintDay[];
  total_due: number;
  weak_libraries: WeakLibrary[];
  recent_mistakes: number;
  hint: string;
}

export function studySprint(days = 7): Promise<SprintPlan> {
  return requestJson<SprintPlan>(`/api/study/sprint?days=${days}`);
}

export async function studyActivity(days = 30): Promise<ActivityDay[]> {
  const data = await requestJson<{ days: ActivityDay[] }>(
    `/api/study/activity?days=${days}`,
  );
  return data.days;
}

export interface MemoryItem {
  id: number;
  content: string;
  created_at: number;
}

export async function listMemories(): Promise<MemoryItem[]> {
  const data = await requestJson<{ memories: MemoryItem[] }>("/api/memories");
  return data.memories;
}

export async function deleteMemory(id: number): Promise<void> {
  await requestJson(`/api/memories/${id}`, { method: "DELETE" });
}

export function usage(days = 1): Promise<UsageSummary> {
  return requestJson<UsageSummary>(`/api/usage?days=${days}`);
}

// --- 会话（项目分组 + 自动保存）---------------------------------------------

export interface ChatProject {
  id: number;
  name: string;
  is_default?: number; // 1 = 默认对话空间（不可删除）
  created_at: number;
}

export interface ChatSession {
  id: number;
  project_id: number | null;
  thread_id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

/** 聊天附件元信息（后端随消息一起存，前端据此渲染与预览） */
export interface AttachmentMeta {
  id: number;
  name: string;
  kind: "image" | "file";
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  /** 该消息携带的附件（后端还原好的数组） */
  attachments?: AttachmentMeta[];
  /** 该轮的过程步骤（后端随消息落库，历史回放可见） */
  steps?: AgentStep[];
  created_at: number;
}

export async function listProjects(): Promise<ChatProject[]> {
  const data = await requestJson<{ projects: ChatProject[] }>("/api/projects");
  return data.projects;
}

export async function createProject(name: string): Promise<ChatProject> {
  const form = new FormData();
  form.append("name", name);
  return requestJson("/api/projects", { method: "POST", body: form });
}

export async function renameProject(id: number, name: string): Promise<void> {
  const form = new FormData();
  form.append("name", name);
  await requestJson(`/api/projects/${id}`, { method: "PUT", body: form });
}

export async function deleteProject(id: number): Promise<void> {
  await requestJson(`/api/projects/${id}`, { method: "DELETE" });
}

export async function listChats(projectId?: number): Promise<ChatSession[]> {
  const query = projectId !== undefined ? `?project_id=${projectId}` : "";
  const data = await requestJson<{ chats: ChatSession[] }>(`/api/chats${query}`);
  return data.chats;
}

export async function listChatMessages(sessionId: number): Promise<ChatMessage[]> {
  const data = await requestJson<{ messages: ChatMessage[] }>(
    `/api/chats/${sessionId}/messages`,
  );
  return data.messages;
}

/** 重命名会话（后端 PUT /api/chats/{id} 支持 title 字段） */
export async function renameChat(sessionId: number, title: string): Promise<void> {
  const form = new FormData();
  form.append("title", title);
  await requestJson(`/api/chats/${sessionId}`, { method: "PUT", body: form });
}

export async function deleteChat(sessionId: number): Promise<void> {
  await requestJson(`/api/chats/${sessionId}`, { method: "DELETE" });
}

// --- 聊天（SSE）-----------------------------------------------------------

/** 过程步骤：思考（thinking）/ 工具调用（tool），由后端节点更新翻译而来 */
export interface AgentStep {
  kind: "thinking" | "tool";
  title: string;
  detail: string;
}

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "status"; label: string }
  | { type: "step"; kind: "thinking" | "tool"; title: string; detail: string }
  | { type: "session"; id: number; title: string }
  | {
      type: "interrupt";
      action: string;
      library: string;
      title: string;
      preview: string;
    }
  | { type: "guard"; reason: string }
  | { type: "done" }
  | { type: "error"; message: string };

function parseEvent(raw: string): StreamEvent | null {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice("event: ".length);
    else if (line.startsWith("data: ")) data += line.slice("data: ".length);
  }
  if (!data) return null;

  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(data) as Record<string, unknown>;
  } catch {
    return null;
  }

  switch (event) {
    case "token":
      return { type: "token", content: String(payload.content ?? "") };
    case "status":
      return { type: "status", label: String(payload.label ?? "") };
    case "session":
      return {
        type: "session",
        id: Number(payload.id ?? 0),
        title: String(payload.title ?? ""),
      };
    case "interrupt":
      return {
        type: "interrupt",
        action: String(payload.action ?? ""),
        library: String(payload.library ?? ""),
        title: String(payload.title ?? ""),
        preview: String(payload.preview ?? ""),
      };
    case "guard":
      return { type: "guard", reason: String(payload.reason ?? "") };
    case "done":
      return { type: "done" };
    case "error":
      return { type: "error", message: String(payload.message ?? "未知错误") };
    default:
      return null;
  }
}

async function stream(
  path: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    onEvent({ type: "error", message: "无法连接后端，请确认服务已启动。" });
    return;
  }

  if (!response.ok || !response.body) {
    onEvent({ type: "error", message: `请求失败：${response.status}` });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index: number;
    while ((index = buffer.indexOf("\n\n")) !== -1) {
      const event = parseEvent(buffer.slice(0, index));
      buffer = buffer.slice(index + 2);
      if (event) onEvent(event);
    }
  }
}

export interface ChatRequest {
  message: string;
  thread_id: string;
  user_id?: string;
  knowledge_bases?: string[];
  // 会话自动保存：不传 session_id → 后端新建会话；传了 → 续聊并追加消息。
  session_id?: number;
  project_id?: number;
  /** 本条消息携带的聊天附件 id（先经 uploadChatAttachment 上传） */
  attachment_ids?: number[];
}

/** 上传聊天附件（PDF/TXT/MD 抽文本，图片走视觉转写），返回附件 id 供发消息时携带 */
export async function uploadChatAttachment(
  file: File,
  sessionId?: number,
  projectId?: number,
): Promise<{ id: number; filename: string; kind: string; chars: number }> {
  const form = new FormData();
  form.append("file", file);
  if (sessionId !== undefined) form.append("session_id", String(sessionId));
  if (projectId !== undefined) form.append("project_id", String(projectId));
  return requestJson("/api/chat/attachments", { method: "POST", body: form });
}

/** 附件原文件地址（图片预览用，后端带归属校验） */
export function attachmentRawUrl(attachmentId: number): string {
  return `${API_BASE}/api/chat/attachments/${attachmentId}/raw`;
}

export function streamChat(
  request: ChatRequest,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  return stream("/api/chat/stream", request, onEvent);
}

export function resumeChat(
  threadId: string,
  approved: boolean,
  onEvent: (event: StreamEvent) => void,
  sessionId?: number,
): Promise<void> {
  return stream(
    "/api/chat/resume",
    {
      thread_id: threadId,
      approved,
      session_id: sessionId,
      user_id: "local",
    },
    onEvent,
  );
}
