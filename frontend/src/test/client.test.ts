import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('API client', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('login stores token in localStorage', async () => {
    const mockResponse = { access_token: 'test-token-123' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    } as Response);

    const { login } = await import('../api/client');
    await login('admin', 'secret');
    expect(localStorage.getItem('token')).toBe('test-token-123');
  });

  it('logout removes token from localStorage', async () => {
    localStorage.setItem('token', 'some-token');
    const { logout } = await import('../api/client');
    logout();
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('getMe sends auth header', async () => {
    localStorage.setItem('token', 'my-jwt');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ username: 'admin' }),
    } as Response);

    const { getMe } = await import('../api/client');
    const me = await getMe();
    expect(me.username).toBe('admin');

    const [, init] = fetchSpy.mock.calls[0];
    expect(init?.headers).toHaveProperty('Authorization', 'Bearer my-jwt');
  });

  it('request redirects to login on 401', async () => {
    localStorage.setItem('token', 'expired');
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
    } as Response);

    // Mock window.location.href setter
    const hrefSetter = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });
    Object.defineProperty(window.location, 'href', {
      set: hrefSetter,
      get: () => '',
    });

    const { getMe } = await import('../api/client');
    await expect(getMe()).rejects.toThrow('Unauthorized');
    expect(localStorage.getItem('token')).toBeNull();
  });
});
