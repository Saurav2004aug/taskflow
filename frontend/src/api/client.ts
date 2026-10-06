import type { AuthResponse, Stats, Task, TaskInput, TaskPage, User } from "./types";

/** Error thrown for any non-2xx response. `fields` holds per-field validation messages. */
export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;

  constructor(message: string, status: number, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

const TOKEN_KEY = "taskflow.token";

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string | null) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable (private mode): the session just won't persist */
    }
  },
};

/** Called when the server says our token is no longer valid (expired / revoked). */
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection.", 0);
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(data.error ?? `Request failed (${res.status})`, res.status, data.fields ?? {});
  }
  return data as T;
}

export interface TaskQuery {
  q?: string;
  priority?: string;
}

export const api = {
  register: (name: string, email: string, password: string) =>
    request<AuthResponse>("POST", "/api/auth/register", { name, email, password }),
  login: (email: string, password: string) => request<AuthResponse>("POST", "/api/auth/login", { email, password }),
  me: () => request<{ user: User }>("GET", "/api/auth/me"),

  listTasks: (query: TaskQuery = {}) => {
    const params = new URLSearchParams({ per_page: "500", sort: "position" });
    if (query.q) params.set("q", query.q);
    if (query.priority) params.set("priority", query.priority);
    return request<TaskPage>("GET", `/api/tasks?${params}`);
  },
  createTask: (input: TaskInput) => request<Task>("POST", "/api/tasks", input),
  updateTask: (id: number, input: TaskInput) => request<Task>("PATCH", `/api/tasks/${id}`, input),
  deleteTask: (id: number) => request<void>("DELETE", `/api/tasks/${id}`),
  stats: () => request<Stats>("GET", "/api/tasks/stats"),
};
