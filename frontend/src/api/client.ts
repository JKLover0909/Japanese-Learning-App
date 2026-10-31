import type {
  AdminLoginRequest,
  AdminOverview,
  AnswerResult,
  AppConfig,
  ChapterTestAnswer,
  ChapterTestDetail,
  ChapterTestResult,
  ChaptersResponse,
  HealthResponse,
  LessonDetailResponse,
  LessonsResponse,
  ListSessionsParams,
  SessionDetail,
  SessionsResponse,
  SessionSummary,
  StatusResponse,
} from './types';

/** Header required by the backend's CSRF guard on every state-changing request. */
export const CSRF_HEADER = 'X-Requested-With';
export const CSRF_HEADER_VALUE = 'jp-practice';

export const MESSAGES = {
  network: 'Không kết nối được tới máy chủ. Hãy kiểm tra mạng rồi thử lại.',
  validation: 'Dữ liệu gửi đi chưa hợp lệ. Hãy kiểm tra lại.',
  server: 'Máy chủ đang gặp sự cố. Hãy thử lại sau ít phút.',
  unknown: 'Đã có lỗi xảy ra. Hãy thử lại.',
  unauthorized: 'Phiên quản trị đã hết hạn. Hãy đăng nhập lại.',
  notFound: 'Không tìm thấy nội dung bạn cần.',
} as const;

/** Every failed API call rejects with an ApiError. `status` is 0 for network failures. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

/** A user-facing Vietnamese message for any error thrown by the client. */
export function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.detail;
  return MESSAGES.unknown;
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

interface RequestOptions {
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = `/api${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  const search = params.toString();
  return search ? `${url}?${search}` : url;
}

function fallbackMessage(status: number): string {
  if (status === 401) return MESSAGES.unauthorized;
  if (status === 404) return MESSAGES.notFound;
  if (status === 422) return MESSAGES.validation;
  if (status >= 500) return MESSAGES.server;
  return MESSAGES.unknown;
}

async function toApiError(response: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object' && 'detail' in data) {
      detail = (data as { detail: unknown }).detail;
    }
  } catch {
    detail = undefined;
  }
  // FastAPI validation errors (422) carry a list; show a generic message for those.
  const message =
    typeof detail === 'string' && detail.trim() !== '' ? detail : fallbackMessage(response.status);
  return new ApiError(response.status, message);
}

export async function request<T>(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (method !== 'GET') headers[CSRF_HEADER] = CSRF_HEADER_VALUE;

  const init: RequestInit = {
    method,
    headers,
    credentials: 'same-origin',
    signal: options.signal,
  };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), init);
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError(0, MESSAGES.network);
  }

  if (!response.ok) throw await toApiError(response);

  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, MESSAGES.server);
  }
}

/** Typed wrappers for every endpoint in docs/api.md. */
export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>('GET', '/health', { signal }),

  config: (signal?: AbortSignal) => request<AppConfig>('GET', '/config', { signal }),

  /** Issues or refreshes the anonymous learner cookie; call before other learner requests. */
  initLearner: () => request<StatusResponse>('POST', '/learner/init'),

  adminLogin: (body: AdminLoginRequest) => request<StatusResponse>('POST', '/admin/login', { body }),

  adminLogout: () => request<void>('POST', '/admin/logout'),

  adminOverview: (signal?: AbortSignal) => request<AdminOverview>('GET', '/admin/overview', { signal }),

  listLessons: (signal?: AbortSignal) => request<LessonsResponse>('GET', '/lessons', { signal }),

  getLesson: (slug: string, signal?: AbortSignal) =>
    request<LessonDetailResponse>('GET', `/lessons/${encodeURIComponent(slug)}`, { signal }),

  resetLessonProgress: (slug: string) =>
    request<void>('DELETE', `/lessons/${encodeURIComponent(slug)}/progress`),

  createSession: (lessonSlug: string) =>
    request<SessionDetail>('POST', '/sessions', { body: { lesson_slug: lessonSlug } }),

  listSessions: (params: ListSessionsParams = {}, signal?: AbortSignal) =>
    request<SessionsResponse>('GET', '/sessions', {
      signal,
      query: { lesson_slug: params.lesson_slug, limit: params.limit },
    }),

  getSession: (id: string, signal?: AbortSignal) =>
    request<SessionDetail>('GET', `/sessions/${encodeURIComponent(id)}`, { signal }),

  submitAnswer: (id: string, position: number, answer: string) =>
    request<AnswerResult>('POST', `/sessions/${encodeURIComponent(id)}/answers`, {
      body: { position, answer },
    }),

  getSessionSummary: (id: string, signal?: AbortSignal) =>
    request<SessionSummary>('GET', `/sessions/${encodeURIComponent(id)}/summary`, { signal }),

  listChapters: (signal?: AbortSignal) => request<ChaptersResponse>('GET', '/chapters', { signal }),

  createChapterTest: (chapter: number) =>
    request<ChapterTestDetail>('POST', `/chapters/${chapter}/tests`),

  getChapterTest: (id: string, signal?: AbortSignal) =>
    request<ChapterTestDetail>('GET', `/tests/${encodeURIComponent(id)}`, { signal }),

  answerChapterTest: (id: string, position: number, choice: number) =>
    request<ChapterTestAnswer>('PUT', `/tests/${encodeURIComponent(id)}/answers`, {
      body: { position, choice },
    }),

  submitChapterTest: (id: string) =>
    request<ChapterTestResult>('POST', `/tests/${encodeURIComponent(id)}/submit`),

  getChapterTestResult: (id: string, signal?: AbortSignal) =>
    request<ChapterTestResult>('GET', `/tests/${encodeURIComponent(id)}/result`, { signal }),
};

export type Api = typeof api;
