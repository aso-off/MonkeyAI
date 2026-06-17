import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/services/api', () => ({
  api: {
    getMe: vi.fn(),
    updateMe: vi.fn(),
    bootstrapDialog: vi.fn(),
  },
}))

import { api, type DialogMessage, type TelegramUser } from '@/services/api'
import { dialogMessagesToChat, useUserStore } from '@/store/user'

const mockApi = vi.mocked(api)

function makeUser(over: Partial<TelegramUser> = {}): TelegramUser {
  return {
    id: 1, chat_id: 1, username: 'u', first_name: 'F', last_name: null,
    language: 'ru', is_admin: false, is_whitelisted: true,
    first_seen: '', last_interaction: '',
    current_dialog_id: null, current_chat_mode: 'x',
    mini_app_chat_mode: 'y', current_model: 'gpt-4o', theme: 'dark',
    n_used_tokens: {}, n_generated_images: 0, n_transcribed_seconds: 0,
    ...over,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('user store · init', () => {
  it('applies valid model and theme from API', async () => {
    mockApi.getMe.mockResolvedValue(makeUser({ current_model: 'gpt-4o', theme: 'dark' }))
    const s = useUserStore()
    await s.init()
    expect(s.currentModel).toBe('gpt-4o')
    expect(s.currentTheme).toBe('dark')
    expect(s.isInitialized).toBe(true)
    expect(s.isReady).toBe(true)
  })

  it('falls back to defaults for unknown model/theme', async () => {
    mockApi.getMe.mockResolvedValue(makeUser({ current_model: 'unknown', theme: 'weird' }))
    const s = useUserStore()
    await s.init()
    expect(s.currentModel).toBe('gpt-5.4-nano')
    expect(s.currentTheme).toBe('system')
  })

  it('marks initialized even when API fails', async () => {
    mockApi.getMe.mockRejectedValue(new Error('network'))
    const s = useUserStore()
    await s.init()
    expect(s.isInitialized).toBe(true)
    expect(s.user).toBeNull()
    expect(s.isReady).toBe(false)
  })
})

describe('user store · setModel', () => {
  it('keeps new model on success', async () => {
    mockApi.updateMe.mockResolvedValue(undefined)
    const s = useUserStore()
    await s.setModel('gpt-4o')
    expect(s.currentModel).toBe('gpt-4o')
  })

  it('rolls back on error and rethrows', async () => {
    mockApi.updateMe.mockRejectedValue(new Error('fail'))
    const s = useUserStore()
    s.currentModel = 'gpt-5.4-nano'
    await expect(s.setModel('gpt-4o')).rejects.toThrow('fail')
    expect(s.currentModel).toBe('gpt-5.4-nano')
  })
})

describe('user store · prefetchChatHistory', () => {
  it('skips for non-whitelisted users', async () => {
    mockApi.getMe.mockResolvedValue(makeUser({ is_whitelisted: false }))
    const s = useUserStore()
    await s.init()
    await s.prefetchChatHistory()
    expect(s.chatHistoryLoaded).toBe(true)
    expect(mockApi.bootstrapDialog).not.toHaveBeenCalled()
  })

  it('loads history for whitelisted users', async () => {
    mockApi.getMe.mockResolvedValue(makeUser({ is_whitelisted: true }))
    mockApi.bootstrapDialog.mockResolvedValue({
      dialog_id: 'd1',
      messages: [{ id: 'm1', role: 'user', content: 'hi' }],
      next_before_index: 0,
    })
    const s = useUserStore()
    await s.init()
    await s.prefetchChatHistory()
    expect(s.dialogId).toBe('d1')
    expect(s.chatHistory).toHaveLength(1)
    expect(s.chatHistoryPrefetchOk).toBe(true)
  })
})

describe('dialogMessagesToChat', () => {
  it('maps a plain user message', () => {
    const msgs: DialogMessage[] = [{ id: '1', role: 'user', content: 'hello' }]
    expect(dialogMessagesToChat(msgs)).toEqual([{ type: 'user', text: 'hello', id: '1' }])
  })

  it('maps a user message with an image', () => {
    const msgs: DialogMessage[] = [{
      id: '2', role: 'user',
      content: [
        { type: 'text', text: 'look' },
        { type: 'image_url', image_url: { url: 'https://img/x.png' } },
      ],
      image_meta: { w: 100, h: 200 },
    }]
    const [m] = dialogMessagesToChat(msgs)
    expect(m).toMatchObject({ type: 'user', contentType: 'image', text: 'look', imageUrl: 'https://img/x.png', imageW: 100, imageH: 200 })
  })

  it('maps a bot text message', () => {
    const msgs: DialogMessage[] = [{ id: '3', role: 'assistant', content: 'answer', reaction: 'like' }]
    expect(dialogMessagesToChat(msgs)).toEqual([
      { type: 'bot', contentType: 'text', text: 'answer', id: '3', reaction: 'like' },
    ])
  })

  it('maps a bot image message (url content)', () => {
    const msgs: DialogMessage[] = [{ id: '4', role: 'assistant', content: 'https://cdn/y.png' }]
    const [m] = dialogMessagesToChat(msgs)
    expect(m).toMatchObject({ type: 'bot', contentType: 'image', imageUrl: 'https://cdn/y.png', text: '' })
  })
})
