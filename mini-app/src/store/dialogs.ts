import { defineStore } from 'pinia'
import { api, type DialogListItem } from '@/services/api'

export const useDialogsStore = defineStore('dialogs', {
  state: () => ({
    list: [] as DialogListItem[],
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
        const r = await api.listDialogs(null, 10)
        this.list = r.dialogs
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
      const d = this.list.find((x) => x.dialog_id === dialogId)
      if (d) d.title = title
    },

    async remove(dialogId: string) {
      await api.deleteDialog(dialogId)
      this.list = this.list.filter((x) => x.dialog_id !== dialogId)
    },

    /** Live title update from WS `dialog_title`. */
    applyTitle(dialogId: string, title: string) {
      const d = this.list.find((x) => x.dialog_id === dialogId)
      if (d) d.title = title
    },
  },
})
