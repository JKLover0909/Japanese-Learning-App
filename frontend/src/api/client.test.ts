import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, CSRF_HEADER, CSRF_HEADER_VALUE, MESSAGES, request } from './client';
import type { ApiError } from './client';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('API client', () => {
  it('sends same-origin credentials and the CSRF header on state-changing requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);

    await api.adminLogout();

    expect(fetchMock).toHaveBeenCalledWith('/api/admin/logout', expect.objectContaining({
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        [CSRF_HEADER]: CSRF_HEADER_VALUE,
      },
    }));
  });

  it('does not send the CSRF header on GET and encodes query parameters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ sessions: [] }));
    vi.stubGlobal('fetch', fetchMock);

    await api.listSessions({ lesson_slug: 'hiragana-extended', limit: 10 });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/sessions?lesson_slug=hiragana-extended&limit=10',
      expect.objectContaining({ method: 'GET', credentials: 'same-origin' }),
    );
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.headers).not.toHaveProperty(CSRF_HEADER);
  });

  it('maps string error detail to ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: 'Vui lòng đăng nhập quản trị.' }, { status: 401 })));

    await expect(api.adminOverview()).rejects.toMatchObject({
      name: 'ApiError', status: 401, detail: 'Vui lòng đăng nhập quản trị.',
    });
  });

  it('initializes the anonymous learner with a CSRF-protected POST', async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ status: 'ok' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.initLearner()).resolves.toEqual({ status: 'ok' });
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/learner/init');
    expect(options).toMatchObject({ method: 'POST', credentials: 'same-origin' });
    expect(options.headers).toHaveProperty(CSRF_HEADER, CSRF_HEADER_VALUE);
  });

  it('uses the generic message for FastAPI validation-error lists', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: [{ loc: ['body'], msg: 'bad' }] }, { status: 422 })));
    await expect(request('POST', '/admin/login', { body: {} })).rejects.toMatchObject({
      status: 422, detail: MESSAGES.validation,
    });
  });

  it('maps network failures to ApiError status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(request('GET', '/health')).rejects.toMatchObject({
      name: 'ApiError', status: 0, detail: MESSAGES.network,
    });
  });

  it('uses fallback messages for non-JSON errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('oops', { status: 503 })));
    await expect(request('GET', '/lessons')).rejects.toEqual(expect.objectContaining({
      status: 503, detail: MESSAGES.server,
    } satisfies Partial<ApiError>));
  });
});
