import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/services/api', () => ({
  api: {
    listDialogs: vi.fn(),
    listPinned: vi.fn(),
    searchDialogs: vi.fn(),
    renameDialog: vi.fn(),
    deleteDialog: vi.fn(),
    pinDialog: vi.fn(),
  },
}))

import { api, type DialogListItem } from '@/services/api'
import { useDialogsStore } from '@/store/dialogs'
import { outbox } from '@/services/outbox'

const mockApi = vi.mocked(api)

function item(id: string, over: Partial<DialogListItem> = {}): DialogListItem {
  return { dialog_id: id, title: null, last_activity: '2026-01-01', start_time: '2026-01-01', pinned: false, ...over }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('dialogs store · loadInitial', () => {
  it('fills list, pinned and pagination', async () => {
    mockApi.listDialogs.mockResolvedValue({ dialogs: [item('a')], next_before: 'cur', has_more: true })
    mockApi.listPinned.mockResolvedValue({ dialogs: [item('p', { pinned: true })], next_before: null, has_more: false })
    const s = useDialogsStore()
    await s.loadInitial()
    expect(s.list).toHaveLength(1)
    expect(s.pinned).toHaveLength(1)
    expect(s.nextBefore).toBe('cur')
    expect(s.hasMore).toBe(true)
    expect(s.loaded).toBe(true)
  })

  it('does not reload when already loaded', async () => {
    const s = useDialogsStore()
    s.loaded = true
    await s.loadInitial()
    expect(mockApi.listDialogs).not.toHaveBeenCalled()
  })
})

describe('dialogs store · loadMore', () => {
  it('appends and respects hasMore guard', async () => {
    const s = useDialogsStore()
    s.list = [item('a')]
    s.hasMore = true
    mockApi.listDialogs.mockResolvedValue({ dialogs: [item('b')], next_before: null, has_more: false })
    await s.loadMore()
    expect(s.list.map(d => d.dialog_id)).toEqual(['a', 'b'])
    expect(s.hasMore).toBe(false)

    await s.loadMore()
    expect(mockApi.listDialogs).toHaveBeenCalledTimes(1)
  })
})

describe('dialogs store · mutations', () => {
  it('rename updates all lists', async () => {
    const s = useDialogsStore()
    s.list = [item('a')]
    s.pinned = [item('a', { pinned: true })]
    mockApi.renameDialog.mockResolvedValue(undefined)
    await s.rename('a', 'New')
    expect(s.list[0].title).toBe('New')
    expect(s.pinned[0].title).toBe('New')
  })

  it('remove drops the dialog everywhere', async () => {
    const s = useDialogsStore()
    s.list = [item('a'), item('b')]
    s.pinned = [item('a')]
    mockApi.deleteDialog.mockResolvedValue(undefined)
    await s.remove('a')
    expect(s.list.map(d => d.dialog_id)).toEqual(['b'])
    expect(s.pinned).toHaveLength(0)
  })

  it('remove purges queued offline messages for that dialog', async () => {
    outbox.clear()
    outbox.enqueue({ id: 'q1', kind: 'chat', body: { message: 'hi', model: 'gpt-4o', dialog_id: 'a' }, createdAt: 1 })
    outbox.enqueue({ id: 'q2', kind: 'chat', body: { message: 'yo', model: 'gpt-4o', dialog_id: 'b' }, createdAt: 2 })
    const s = useDialogsStore()
    mockApi.deleteDialog.mockResolvedValue(undefined)
    await s.remove('a')
    expect(outbox.has('q1')).toBe(false)
    expect(outbox.has('q2')).toBe(true)
    outbox.clear()
  })

  it('pin moves dialog from list to pinned', async () => {
    const s = useDialogsStore()
    s.list = [item('a')]
    mockApi.pinDialog.mockResolvedValue(undefined)
    await s.pin('a')
    expect(s.list).toHaveLength(0)
    expect(s.pinned[0].dialog_id).toBe('a')
    expect(s.pinned[0].pinned).toBe(true)
  })

  it('unpin moves dialog back to list', async () => {
    const s = useDialogsStore()
    s.pinned = [item('a', { pinned: true })]
    mockApi.pinDialog.mockResolvedValue(undefined)
    await s.unpin('a')
    expect(s.pinned).toHaveLength(0)
    expect(s.list[0].dialog_id).toBe('a')
    expect(s.list[0].pinned).toBe(false)
  })

  it('touch bumps a dialog to the top of the list', () => {
    const s = useDialogsStore()
    s.list = [item('a'), item('b')]
    s.touch('b')
    expect(s.list[0].dialog_id).toBe('b')
  })

  it('prepend adds a new dialog once', () => {
    const s = useDialogsStore()
    s.prepend('new')
    s.prepend('new')
    expect(s.list.filter(d => d.dialog_id === 'new')).toHaveLength(1)
  })

  it('applyTitle updates matching dialogs', () => {
    const s = useDialogsStore()
    s.list = [item('a')]
    s.applyTitle('a', 'Title')
    expect(s.list[0].title).toBe('Title')
  })
})
