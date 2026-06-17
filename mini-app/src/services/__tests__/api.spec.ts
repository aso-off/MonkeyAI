import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@tma.js/sdk-vue', () => ({
  initData: { raw: () => 'rawinit' },
}))

import { api, type TelegramUser } from '@/services/api'

function makeUser(): TelegramUser {
  return {
    id: 1, chat_id: 1, username: 'u', first_name: 'F', last_name: null,
    language: 'ru', is_admin: false, is_whitelisted: true,
    first_seen: '', last_interaction: '',
    current_dialog_id: null, current_chat_mode: 'x',
    mini_app_chat_mode: 'y', current_model: 'gpt-4o', theme: 'dark',
    n_used_tokens: {}, n_generated_images: 0, n_transcribed_seconds: 0,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response
}

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('apiFetch · success path', () => {
  it('returns parsed body and sends Telegram auth header', async () => {
    const user = makeUser()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(user))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.getMe()
    expect(result).toEqual(user)

    const [url, opts] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/webapp/me')
    expect((opts.headers as Record<string, string>).Authorization).toBe('tma rawinit')
  })

  it('returns undefined on 204 No Content', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 204, text: async () => '', json: async () => undefined,
    } as unknown as Response)
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.renameDialog('d1', 'title')
    expect(result).toBeUndefined()
  })
})

describe('apiFetch · error policy', () => {
  it('does not retry on 4xx and surfaces server detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'forbidden' }, 403))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.getMe()).rejects.toThrow('forbidden')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('throws immediately on network error when retries are disabled', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.sendReaction({ reaction: 'like', model: 'gpt-4o' })).rejects.toThrow()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('retries a retryable network error then succeeds', async () => {
    vi.useFakeTimers()
    const user = makeUser()
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(jsonResponse(user))
    vi.stubGlobal('fetch', fetchMock)

    const promise = api.getMe()
    await vi.runAllTimersAsync()
    await expect(promise).resolves.toEqual(user)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
