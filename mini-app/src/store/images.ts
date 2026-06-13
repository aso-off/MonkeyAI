import { defineStore } from 'pinia'
import { api, type ImageItem } from '@/services/api'

export const useImagesStore = defineStore('images', {
  state: () => ({
    list: [] as ImageItem[],
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
        const r = await api.listImages(null, 30)
        this.list = r.images
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
        const r = await api.listImages(this.nextBefore, 30)
        this.list.push(...r.images)
        this.nextBefore = r.next_before
        this.hasMore = r.has_more
      } finally {
        this.loading = false
      }
    },

    /** Add a freshly generated image to the top of the gallery. */
    prepend(img: ImageItem) {
      this.list.unshift(img)
    },
  },
})
