import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/services/api', () => ({
  api: {
    listImages: vi.fn(),
  },
}))

import { api, type ImageItem } from '@/services/api'
import { useImagesStore } from '@/store/images'

const mockApi = vi.mocked(api)

function img(id: number): ImageItem {
  return { id, url: `https://img/${id}.png`, prompt: 'p', dialog_id: 'd', created_at: '2026-01-01' }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('images store', () => {
  it('loadInitial fills the gallery', async () => {
    mockApi.listImages.mockResolvedValue({ images: [img(1)], next_before: 'c', has_more: true })
    const s = useImagesStore()
    await s.loadInitial()
    expect(s.list).toHaveLength(1)
    expect(s.nextBefore).toBe('c')
    expect(s.hasMore).toBe(true)
    expect(s.loaded).toBe(true)
  })

  it('loadInitial is a no-op when already loaded', async () => {
    const s = useImagesStore()
    s.loaded = true
    await s.loadInitial()
    expect(mockApi.listImages).not.toHaveBeenCalled()
  })

  it('loadMore appends and respects hasMore guard', async () => {
    const s = useImagesStore()
    s.list = [img(1)]
    s.hasMore = true
    mockApi.listImages.mockResolvedValue({ images: [img(2)], next_before: null, has_more: false })
    await s.loadMore()
    expect(s.list.map(i => i.id)).toEqual([1, 2])
    expect(s.hasMore).toBe(false)

    await s.loadMore()
    expect(mockApi.listImages).toHaveBeenCalledTimes(1)
  })

  it('prepend adds image to the top', () => {
    const s = useImagesStore()
    s.list = [img(1)]
    s.prepend(img(2))
    expect(s.list[0].id).toBe(2)
  })
})
