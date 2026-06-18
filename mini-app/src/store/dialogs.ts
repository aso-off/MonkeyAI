import { defineStore } from 'pinia'
import { api, type DialogListItem } from '@/services/api'
import { outbox } from '@/services/outbox'

export const useDialogsStore = defineStore('dialogs', {
  state: () => ({
    list: [] as DialogListItem[],
    pinned: [] as DialogListItem[],
    searchResults: [] as DialogListItem[],
    searching: false,
    searchSeq: 0,
    nextBefore: null as string | null,
    hasMore: false,
    loading: false,
    loaded: false,
  }),
  actions: {
    async loadInitial() {
      if (this.loading || this.loaded) return
      this.loading = true
      try {
        const [r, p] = await Promise.all([api.listDialogs(null, 10), api.listPinned()])
        this.list = r.dialogs
        this.pinned = p.dialogs
        this.nextBefore = r.next_before
        this.hasMore = r.has_more
        this.loaded = true
      } finally {
        this.loading = false
      }
    },

    async loadMore() {
      if (this.loading || !this.hasMore) return
      this.loading = true
      try {
        const r = await api.listDialogs(this.nextBefore, 20)
        this.list.push(...r.dialogs)
        this.nextBefore = r.next_before
        this.hasMore = r.has_more
      } finally {
        this.loading = false
      }
    },

    /** Поиск держим отдельно, чтобы при стирании recents показывались мгновенно. */
    async runSearch(q: string, includeUntitled: boolean) {
      const seq = ++this.searchSeq
      this.searching = true
      try {
        const r = await api.searchDialogs(q, 50, includeUntitled)
        if (seq !== this.searchSeq) return
        this.searchResults = r.dialogs
      } finally {
        if (seq === this.searchSeq) this.searching = false
      }
    },

    /** Ввод начался - «Ничего не найдено» не показываем, пока ответ не пришёл. */
    markSearching() {
      this.searchSeq++
      this.searching = true
    },

    clearSearch() {
      this.searchSeq++
      this.searchResults = []
      this.searching = false
    },

    async rename(dialogId: string, title: string) {
      await api.renameDialog(dialogId, title)
      for (const arr of [this.list, this.pinned, this.searchResults]) {
        const d = arr.find((x) => x.dialog_id === dialogId)
        if (d) d.title = title
      }
    },

    async remove(dialogId: string) {
      await api.deleteDialog(dialogId)
      this.list = this.list.filter((x) => x.dialog_id !== dialogId)
      this.pinned = this.pinned.filter((x) => x.dialog_id !== dialogId)
      this.searchResults = this.searchResults.filter((x) => x.dialog_id !== dialogId)
      for (const item of outbox.all()) {
        if (item.body.dialog_id === dialogId) outbox.remove(item.id)
      }
    },

    /** Pin/unpin бампит last_activity - диалог встаёт наверх свежим (как у Grok). */
    async pin(dialogId: string) {
      await api.pinDialog(dialogId, true)
      const now = new Date().toISOString()
      const idx = this.list.findIndex((x) => x.dialog_id === dialogId)
      const d =
        idx !== -1
          ? this.list.splice(idx, 1)[0]
          : this.pinned.find((x) => x.dialog_id === dialogId) ??
            this.searchResults.find((x) => x.dialog_id === dialogId)
      if (!d) return
      d.pinned = true
      d.last_activity = now
      if (!this.pinned.some((x) => x.dialog_id === dialogId)) this.pinned.unshift(d)
      this.syncSearchItem(dialogId, true, now)
    },

    async unpin(dialogId: string) {
      await api.pinDialog(dialogId, false)
      const now = new Date().toISOString()
      const idx = this.pinned.findIndex((x) => x.dialog_id === dialogId)
      if (idx === -1) return
      const d = this.pinned.splice(idx, 1)[0]
      d.pinned = false
      d.last_activity = now
      if (!this.list.some((x) => x.dialog_id === dialogId)) this.list.unshift(d)
      this.syncSearchItem(dialogId, false, now)
    },

    syncSearchItem(dialogId: string, pinned: boolean, now: string) {
      const s = this.searchResults.find((x) => x.dialog_id === dialogId)
      if (s) {
        s.pinned = pinned
        s.last_activity = now
      }
    },

    /** Сообщение отправлено - обновляем время и поднимаем диалог наверх (живое «Сегодня»). */
    touch(dialogId: string) {
      const now = new Date().toISOString()
      const p = this.pinned.find((x) => x.dialog_id === dialogId)
      if (p) {
        p.last_activity = now
        return
      }
      const idx = this.list.findIndex((x) => x.dialog_id === dialogId)
      if (idx !== -1) {
        const d = this.list.splice(idx, 1)[0]
        d.last_activity = now
        this.list.unshift(d)
      }
    },

    /** Optimistically add a freshly created dialog to the top of Recents. */
    prepend(dialogId: string) {
      if (this.list.some((x) => x.dialog_id === dialogId)) return
      const now = new Date().toISOString()
      this.list.unshift({
        dialog_id: dialogId,
        title: null,
        last_activity: now,
        start_time: now,
        pinned: false,
      })
    },

    /** Live title update from WS `dialog_title`. */
    applyTitle(dialogId: string, title: string) {
      for (const arr of [this.list, this.pinned, this.searchResults]) {
        const d = arr.find((x) => x.dialog_id === dialogId)
        if (d) d.title = title
      }
    },
  },
})