// id == WS req-id запроса - для дедупликации повторной отправки
import type { ChatBody } from '@/services/api'

export interface OutboxItem {
  id: string
  kind: 'chat' | 'image'
  body: ChatBody
  localUrl?: string | null
  createdAt: number
  attempts?: number
}

const STORAGE_KEY = 'monkey:outbox:v1'

type Listener = (items: OutboxItem[]) => void

export class Outbox {
  private items: OutboxItem[] = []
  private listeners = new Set<Listener>()

  constructor() {
    this.load()
  }

  private load(): void {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const parsed = raw ? JSON.parse(raw) : []
      this.items = Array.isArray(parsed) ? parsed : []
    } catch {
      this.items = []
    }
  }

  private persist(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.items))
    } catch {
      // приватный режим / переполнение - очередь остаётся в памяти
    }
    const snapshot = this.all()
    for (const fn of this.listeners) fn(snapshot)
  }

  all(): OutboxItem[] {
    return [...this.items]
  }

  get size(): number {
    return this.items.length
  }

  has(id: string): boolean {
    return this.items.some((i) => i.id === id)
  }

  enqueue(item: OutboxItem): void {
    if (this.has(item.id)) return
    this.items.push(item)
    this.persist()
  }

  remove(id: string): void {
    const before = this.items.length
    this.items = this.items.filter((i) => i.id !== id)
    if (this.items.length !== before) this.persist()
  }

  markAttempt(id: string): number {
    const item = this.items.find((i) => i.id === id)
    if (!item) return 0
    item.attempts = (item.attempts ?? 0) + 1
    this.persist()
    return item.attempts
  }

  clear(): void {
    if (this.items.length === 0) return
    this.items = []
    this.persist()
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn)
    return () => {
      this.listeners.delete(fn)
    }
  }
}

export const outbox = new Outbox()
