import { defineStore } from 'pinia'
import { api } from '@/services/api'
import type { DialogMessage, TelegramUser } from '@/services/api'

export const AVAILABLE_TEXT_MODELS = ['gpt-5.4-nano', 'gpt-4o', 'gpt-5.4-mini'] as const
export const IMAGE_MODELS = ['gpt-image-1.5'] as const
export const ALL_MINI_APP_MODELS = [...AVAILABLE_TEXT_MODELS, ...IMAGE_MODELS] as const

const DEFAULT_MODEL = 'gpt-5.4-nano'

export interface ChatMessage {
  text: string
  type: 'user' | 'bot'
  contentType?: 'text' | 'image'
  imageUrl?: string | null
  imageW?: number | null
  imageH?: number | null
  id?: string
  reaction?: 'like' | 'dislike' | null
}

export function dialogMessagesToChat(messages: DialogMessage[]): ChatMessage[] {
  return messages.map((m): ChatMessage => {
    const text = Array.isArray(m.content)
      ? (m.content.find(p => p.type === 'text')?.text ?? '')
      : String(m.content ?? '')
    if (m.role === 'user') {
      const imageUrl = Array.isArray(m.content)
        ? (m.content.find(p => p.type === 'image_url')?.image_url?.url ?? null)
        : null
      return imageUrl
        ? {
            type: 'user',
            contentType: 'image',
            text,
            imageUrl,
            imageW: m.image_meta?.w ?? null,
            imageH: m.image_meta?.h ?? null,
            id: m.id,
          }
        : { type: 'user', text, id: m.id }
    }
    const isImageUrl = text.startsWith('http') || text.startsWith('data:image/')
    return isImageUrl
      ? { type: 'bot', contentType: 'image', imageUrl: text, text: '', id: m.id, reaction: m.reaction }
      : { type: 'bot', contentType: 'text', text, id: m.id, reaction: m.reaction }
  })
}

interface UserState {
  user: TelegramUser | null
  currentModel: string
  currentTheme: string
  dialogId: string | null
  isInitialized: boolean
  chatHistory: ChatMessage[]
  chatHistoryLoaded: boolean
  chatHistoryPrefetchOk: boolean
  /** Cursor for the next "Load more" call. 0 = no older messages. */
  chatHistoryNextCursor: number
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    user: null,
    currentModel: DEFAULT_MODEL,
    currentTheme: 'system',
    dialogId: null,
    isInitialized: false,
    chatHistory: [],
    chatHistoryLoaded: false,
    chatHistoryPrefetchOk: false,
    chatHistoryNextCursor: 0,
  }),

  getters: {
    userId: (state) => state.user?.id ?? null,
    isReady: (state) => state.isInitialized && state.user !== null,
  },

  actions: {
    async init() {
      try {
        this.user = await api.getMe()
        const dbModel = this.user.current_model
        this.currentModel = (ALL_MINI_APP_MODELS as readonly string[]).includes(dbModel)
          ? dbModel
          : DEFAULT_MODEL
        const dbTheme = this.user.theme
        this.currentTheme = ['system', 'light', 'dark'].includes(dbTheme) ? dbTheme : 'system'
      } catch (e) {
        console.error('[UserStore] Failed to fetch user from API:', e)
      } finally {
        this.isInitialized = true
      }
    },

    async prefetchChatHistory() {
      this.chatHistoryPrefetchOk = false
      if (!this.user?.is_whitelisted) {
        this.chatHistoryLoaded = true
        return
      }

      try {
        const { dialog_id, messages, next_before_index } = await api.bootstrapDialog()
        this.dialogId = dialog_id
        this.chatHistory = dialogMessagesToChat(messages ?? [])
        this.chatHistoryNextCursor = next_before_index
        this.chatHistoryPrefetchOk = true
      } catch (e) {
        console.error('[UserStore] Failed to prefetch chat history:', e)
      } finally {
        this.chatHistoryLoaded = true
      }
    },

    setChatHistory(messages: ChatMessage[]) {
      this.chatHistory = [...messages]
    },

    async setModel(modelId: string) {
      const prev = this.currentModel
      const prevUserModel = this.user?.current_model
      this.currentModel = modelId
      if (this.user) this.user.current_model = modelId
      try {
        await api.updateMe({ model: modelId })
      } catch (e) {
        this.currentModel = prev
        if (this.user && prevUserModel !== undefined) this.user.current_model = prevUserModel
        // AbortError is normal (navigation/tab close) — don't log it.
        if (!(e instanceof DOMException && e.name === 'AbortError')) {
          console.error('[UserStore] Failed to sync model to DB:', e)
        }
        throw e
      }
    },

    async setTheme(theme: string) {
      const prev = this.currentTheme
      this.currentTheme = theme
      if (this.user) this.user.theme = theme
      try {
        await api.updateMe({ theme })
      } catch (e) {
        // Rollback on error
        this.currentTheme = prev
        if (this.user) this.user.theme = prev
        console.error('[UserStore] Failed to sync theme to DB:', e)
        throw e
      }
    },

    setDialogId(id: string | null) {
      this.dialogId = id
    },
  },
})
