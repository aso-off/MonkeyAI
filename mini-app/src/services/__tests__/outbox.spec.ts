import { beforeEach, describe, expect, it } from 'vitest'

import { Outbox, type OutboxItem } from '@/services/outbox'
import type { ChatBody } from '@/services/api'

const STORAGE_KEY = 'monkey:outbox:v1'

function item(id: string, over: Partial<OutboxItem> = {}): OutboxItem {
  const body: ChatBody = { message: `m-${id}`, model: 'gpt-4o' }
  return { id, kind: 'chat', body, createdAt: 1, ...over }
}

beforeEach(() => {
  localStorage.clear()
})

describe('Outbox · enqueue & dedup', () => {
  it('enqueues an item and reports size', () => {
    const o = new Outbox()
    o.enqueue(item('a'))
    expect(o.size).toBe(1)
    expect(o.has('a')).toBe(true)
  })

  it('ignores duplicate ids', () => {
    const o = new Outbox()
    o.enqueue(item('a'))
    o.enqueue(item('a'))
    expect(o.size).toBe(1)
  })
})

describe('Outbox · persistence', () => {
  it('persists to localStorage and reloads in a new instance', () => {
    const o1 = new Outbox()
    o1.enqueue(item('a'))
    o1.enqueue(item('b'))

    const raw = localStorage.getItem(STORAGE_KEY)
    expect(raw).toBeTruthy()

    const o2 = new Outbox()
    expect(o2.all().map((i) => i.id)).toEqual(['a', 'b'])
  })

  it('recovers from corrupt localStorage data', () => {
    localStorage.setItem(STORAGE_KEY, '{not-json')
    const o = new Outbox()
    expect(o.size).toBe(0)
  })

  it('ignores non-array persisted payloads', () => {
    localStorage.setItem(STORAGE_KEY, '{"foo":1}')
    const o = new Outbox()
    expect(o.size).toBe(0)
  })
})

describe('Outbox · remove & clear', () => {
  it('removes a single item', () => {
    const o = new Outbox()
    o.enqueue(item('a'))
    o.enqueue(item('b'))
    o.remove('a')
    expect(o.all().map((i) => i.id)).toEqual(['b'])
  })

  it('clear empties the queue', () => {
    const o = new Outbox()
    o.enqueue(item('a'))
    o.clear()
    expect(o.size).toBe(0)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('[]')
  })
})

describe('Outbox · markAttempt', () => {
  it('increments attempts and persists', () => {
    const o = new Outbox()
    o.enqueue(item('a'))
    expect(o.markAttempt('a')).toBe(1)
    expect(o.markAttempt('a')).toBe(2)
    const reloaded = new Outbox()
    expect(reloaded.all()[0].attempts).toBe(2)
  })

  it('returns 0 for an unknown id', () => {
    const o = new Outbox()
    expect(o.markAttempt('missing')).toBe(0)
  })
})

describe('Outbox · subscribe', () => {
  it('notifies subscribers on change and supports unsubscribe', () => {
    const o = new Outbox()
    const seen: number[] = []
    const unsub = o.subscribe((items) => seen.push(items.length))

    o.enqueue(item('a'))
    o.enqueue(item('b'))
    unsub()
    o.enqueue(item('c'))

    expect(seen).toEqual([1, 2])
    expect(o.size).toBe(3)
  })

  it('preserves FIFO order of queued items', () => {
    const o = new Outbox()
    o.enqueue(item('first'))
    o.enqueue(item('second'))
    o.enqueue(item('third'))
    expect(o.all().map((i) => i.id)).toEqual(['first', 'second', 'third'])
  })
})
