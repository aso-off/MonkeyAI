import { defineStore } from 'pinia'
import { api, type DialogListItem } from '@/services/api'

export const useDialogsStore = defineStore('dialogs', {
  state: () => ({
    list: [] as DialogListItem[],
    pinned: [] as DialogListItem[],
    nextBefore: null as string | null,
    hasMore: false,
    loading: false,
    loaded: false,
  }),
  actions: {
    async loadInitial(force = false) {
      if (this.loading || (this.loaded && !force)) return
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

    async rename(dialogId: string, title: string) {
      await api.renameDialog(dialogId, title)
      for (const arr of [this.list, this.pinned]) {
        const d = arr.find((x) => x.dialog_id === dialogId)
        if (d) d.title = title
      }
    },

    async remove(dialogId: string) {
      await api.deleteDialog(dialogId)
      this.list = this.list.filter((x) => x.dialog_id !== dialogId)
      this.pinned = this.pinned.filter((x) => x.dialog_id !== dialogId)
    },

    async pin(dialogId: string) {
      await api.pinDialog(dialogId, true)
      const idx = this.list.findIndex((x) => x.dialog_id === dialogId)
      const d = idx !== -1 ? this.list.splice(idx, 1)[0] : this.pinned.find((x) => x.dialog_id === dialogId)
      if (!d) return
      d.pinned = true
      if (!this.pinned.some((x) => x.dialog_id === dialogId)) this.pinned.unshift(d)
    },

    async unpin(dialogId: string) {
      await api.pinDialog(dialogId, false)
      const idx = this.pinned.findIndex((x) => x.dialog_id === dialogId)
      if (idx === -1) return
      const d = this.pinned.splice(idx, 1)[0]
      d.pinned = false
      // вернуть в общий список на место по времени
      const at = this.list.findIndex((x) => x.last_activity < d.last_activity)
      if (at === -1) this.list.push(d)
      else this.list.splice(at, 0, d)
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
      for (const arr of [this.list, this.pinned]) {
        const d = arr.find((x) => x.dialog_id === dialogId)
        if (d) d.title = title
      }
    },
  },
})
