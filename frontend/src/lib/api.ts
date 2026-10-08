// 与 StudyGraph 后端（FastAPI + SSE）通信的最小客户端。
// SSE 事件协议见后端 api.py：token / interrupt / done / error。

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8011";

export interface Library {
  name: string;
  document_count: number;
}

export type StreamEvent =
  | { type: "token"; content: string }
  | {
      type: "interrupt";
      action: string;
      library: string;
      title: string;
      preview: string;
    }
  | { type: "done" }
  | { type: "error"; message: string };

export async function listLibraries(): Promise<Library[]> {
  const response = await fetch(`${API_BASE}/api/knowledge/libraries`);
  if (!response.ok) throw new Error(`加载知识库失败：${response.status}`);
  const data = (await response.json()) as { libraries: Library[] };
  return data.libraries;
}

export async function addNote(
  library: string,
  title: string,
  content: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/knowledge/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ library, title, content }),
  });
  if (!response.ok) throw new Error(`保存失败：${response.status}`);
}

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
    case "interrupt":
      return {
        type: "interrupt",
        action: String(payload.action ?? ""),
        library: String(payload.library ?? ""),
        title: String(payload.title ?? ""),
        preview: String(payload.preview ?? ""),
      };
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
): Promise<void> {
  return stream(
    "/api/chat/resume",
    { thread_id: threadId, approved },
    onEvent,
  );
}
