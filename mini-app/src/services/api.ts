/**
 * Monkey AI — API client for the Telegram Mini App.
 */

import { initData } from '@tma.js/sdk-vue';

export const BASE_URL = (import.meta.env.VITE_API_URL as string) || 'https://direct-api.si881.ru';

/** Default for most API calls (slow mobile / Cloudflare tunnels need more headroom). */
const DEFAULT_TIMEOUT_MS = 30_000;

function getAuthHeader(): string {
  const raw = initData.raw();
  if (!raw) {
    throw new Error(
      'Telegram initData is not available. The app must run inside Telegram.',
    );
  }
  return `tma ${raw}`;
}

function buildHeaders(extra?: HeadersInit, hasBody = false): Record<string, string> {
  return {
    ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
    Authorization: getAuthHeader(),
    ...(extra as Record<string, string> | undefined),
  };
}

function isRetryableError(e: unknown): boolean {
  if (e instanceof DOMException && e.name === 'AbortError') return true;
  if (e instanceof TypeError) return true; // Failed to fetch, net::ERR_*
  const msg = e instanceof Error ? e.message : String(e);
  return /failed to fetch|network|load failed|aborted|ping failed|http2|err_/i.test(msg);
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
  retries = 0,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${BASE_URL}${path}`, {
        ...options,
        cache: 'no-store',
        signal: controller.signal,
        headers: buildHeaders(options.headers, !!options.body),
      });
      if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
          const body = await response.json();
          if (body?.detail) detail = body.detail;
        } catch {
        }
        throw new Error(detail);
      }
      if (response.status === 204) return undefined as T;
      const text = await response.text();
      return (text ? JSON.parse(text) : undefined) as T;
    } catch (e) {
      lastError = e;
      const msg = e instanceof Error ? e.message : String(e);
      if (/^HTTP (4\d\d)/.test(msg)) throw e;
      if (attempt < retries && isRetryableError(e)) {
        // ERR_CONNECTION_CLOSED on Android: HTTP/2 session reused after WS close.
        // Give the WebView extra time to drop the stale connection before retrying.
        await new Promise(r => setTimeout(r, 3_000 * (attempt + 1)));
        continue;
      }
      throw e;
    } finally {
      clearTimeout(timeoutId);
    }
  }
  throw lastError;
}

export interface TelegramUser {
  id: number;
  chat_id: number;
  username: string | null;
  first_name: string;
  last_name: string | null;
  language: string;
  is_admin: boolean;
  is_whitelisted: boolean;
  first_seen: string;
  last_interaction: string;
  current_dialog_id: string | null;
  current_chat_mode: string;
  mini_app_chat_mode: string;
  current_model: string;
  theme: string;
  n_used_tokens: Record<string, unknown>;
  n_generated_images: number;
  n_transcribed_seconds: number;
}

export interface ChatBody {
  message: string;
  dialog_id?: string;
  chat_mode?: string;
  model: string;
  image_b64?: string;
  image_url?: string;
  skip_moderation?: boolean;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface ChatCompleteResponse {
  answer: string;
  id?: string;
  usage?: Usage;
  n_first_removed: number;
  is_flagged: boolean;
  dialog_id?: string;
}

/** Каноническое сообщение диалога (плоский список, как у OpenAI). */
export interface DialogMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string | Array<{ type: string; text?: string; image_url?: { url: string } }>;
  parent_id?: string | null;
  model?: string | null;
  usage?: Usage;
  reaction?: 'like' | 'dislike' | null;
  created_at?: string;
}

export interface DialogBootstrapResult {
  dialog_id: string | null;  // null → активного диалога нет (черновик)
  messages: DialogMessage[];
  /** Cursor for the next "Load more" call. 0 = no older messages. */
  next_before_index: number;
}

export interface DialogListItem {
  dialog_id: string;
  title: string | null;
  last_activity: string;
  start_time: string;
  pinned: boolean;
}

export interface DialogListResult {
  dialogs: DialogListItem[];
  next_before: string | null;
  has_more: boolean;
}

export interface ImageItem {
  id: number;
  url: string;
  prompt: string;
  dialog_id: string;
  created_at: string;
}

export interface ImagesResult {
  images: ImageItem[];
  next_before: string | null;
  has_more: boolean;
}

export const api = {
  getMe(): Promise<TelegramUser> {
    return apiFetch<TelegramUser>('/webapp/me', {}, 12_000, 3);
  },

  updateMe(data: {
    language?: string;
    model?: string;
    theme?: string;
    mini_app_chat_mode?: string;
  }): Promise<void> {
    return apiFetch<void>(
      '/webapp/me',
      { method: 'PATCH', body: JSON.stringify(data) },
      15_000,
      2,
    );
  },

  newDialog(): Promise<{ dialog_id: string }> {
    return apiFetch<{ dialog_id: string }>(
      '/webapp/dialogs/new',
      { method: 'POST' },
      DEFAULT_TIMEOUT_MS,
      1,
    );
  },

  /** One request: ensure dialog + load messages (fewer HTTP/2 round-trips). */
  bootstrapDialog(): Promise<DialogBootstrapResult> {
    return apiFetch<DialogBootstrapResult>(
      '/webapp/dialogs/bootstrap',
      { method: 'POST' },
      20_000,
      1,
    );
  },

  /** Load an older page of messages for lazy-loading (cursor-based pagination). */
  getMessagesPage(
    dialogId: string,
    beforeIndex: number,
    limit = 20,
  ): Promise<{ messages: DialogMessage[]; next_before_index: number; has_more: boolean }> {
    const params = new URLSearchParams({
      dialog_id: dialogId,
      before_index: String(beforeIndex),
      limit: String(limit),
    });
    return apiFetch(
      `/webapp/dialogs/messages/page?${params}`,
      {},
      15_000,
      1,
    );
  },

  /** Record a like / dislike reaction for analytics. Fire-and-forget from the UI. */
  sendReaction(payload: {
    reaction: 'like' | 'dislike';
    model: string;
    dialog_id?: string | null;
    message_id?: string | null;
  }): Promise<void> {
    return apiFetch<void>(
      '/webapp/reactions',
      { method: 'POST', body: JSON.stringify(payload) },
      10_000,
      0,
    );
  },

  /** List mini-app dialogs (Recents), newest activity first. */
  listDialogs(before?: string | null, limit = 10): Promise<DialogListResult> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (before) params.set('before', before);
    return apiFetch(`/webapp/dialogs?${params}`, {}, 15_000, 1);
  },

  /** Search dialogs by title. `includeUntitled` also matches default-named (NULL-title) chats. */
  searchDialogs(q: string, limit = 50, includeUntitled = false): Promise<DialogListResult> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (includeUntitled) params.set('include_untitled', '1');
    return apiFetch(`/webapp/dialogs/search?${params}`, {}, 15_000, 1);
  },

  renameDialog(dialogId: string, title: string): Promise<void> {
    return apiFetch<void>(
      `/webapp/dialogs/${dialogId}`,
      { method: 'PATCH', body: JSON.stringify({ title }) },
      10_000,
      0,
    );
  },

  deleteDialog(dialogId: string): Promise<void> {
    return apiFetch<void>(`/webapp/dialogs/${dialogId}`, { method: 'DELETE' }, 10_000, 0);
  },

  /** Pinned dialogs (most recently pinned first). */
  listPinned(): Promise<DialogListResult> {
    return apiFetch(`/webapp/dialogs/pinned`, {}, 15_000, 1);
  },

  pinDialog(dialogId: string, pinned: boolean): Promise<void> {
    return apiFetch<void>(
      `/webapp/dialogs/${dialogId}/pin`,
      { method: 'PATCH', body: JSON.stringify({ pinned }) },
      10_000,
      0,
    );
  },

  /** Пометить диалог активным — reload мини-аппа вернёт именно его. */
  activateDialog(dialogId: string): Promise<void> {
    return apiFetch<void>(
      `/webapp/dialogs/${dialogId}/activate`,
      { method: 'POST' },
      8_000,
      0,
    );
  },

  /** List the user's generated images (gallery). */
  listImages(before?: string | null, limit = 30): Promise<ImagesResult> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (before) params.set('before', before);
    return apiFetch(`/webapp/images?${params}`, {}, 15_000, 1);
  },

  /** Загрузить vision-фото на ImgBB. onProgress: 0..1 (XHR upload). */
  uploadImage(imageB64: string, onProgress?: (ratio: number) => void): Promise<{ url: string }> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE_URL}/webapp/upload-image`);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.setRequestHeader('Authorization', getAuthHeader());
      xhr.timeout = 45_000;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error('bad response'));
          }
        } else {
          let detail = `HTTP ${xhr.status}`;
          try { detail = JSON.parse(xhr.responseText)?.detail || detail; } catch { /* ignore */ }
          reject(new Error(detail));
        }
      };
      xhr.onerror = () => reject(new Error('network error'));
      xhr.ontimeout = () => reject(new Error('timeout'));
      xhr.send(JSON.stringify({ image_b64: imageB64 }));
    });
  },

};

// ---------------------------------------------------------------------------
// WebSocket client for the Telegram Mini App
// ---------------------------------------------------------------------------

function _wsUrl(): string {
  // https://api.si881.ru  →  wss://api.si881.ru/webapp/ws
  return BASE_URL.replace(/^http/, 'ws') + '/webapp/ws';
}

type _WsMsgHandler = (msg: Record<string, unknown>) => void;

export class WsClient {
  private _ws: WebSocket | null = null;
  private _authResolve: ((ok: boolean) => void) | null = null;
  private _connectPromise: Promise<boolean> | null = null;
  /** id-based handlers: req_id → handler (originating device — promise resolution) */
  private _handlers = new Map<string, _WsMsgHandler>();
  /** type-based handlers: msg.type → handler (multi-device broadcasts from other devices) */
  private _typeHandlers = new Map<string, _WsMsgHandler>();
  /** Pending auto-reconnect timer. */
  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  /** Client-side keepalive ping interval (25 s — prevents Cloudflare idle timeout). */
  private _keepaliveTimer: ReturnType<typeof setInterval> | null = null;
  /** Timestamp of the last message received from the server (used for zombie detection). */
  private _lastServerMsgAt = Date.now();

  /** Milliseconds since the last message was received from the server. */
  get msSinceLastServerMsg(): number { return Date.now() - this._lastServerMsgAt; }

  constructor() {
    // Reconnect immediately when the device regains network access.
    window.addEventListener('online', () => {
      if (!this.connected) {
        if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); this._reconnectTimer = null; }
        this.connect().catch(() => {});
      }
    });

    // Reconnect when the Telegram mini app returns to the foreground.
    // Mobile browsers/Telegram may silently kill the WebSocket while the app
    // is in the background; visibilitychange is the most reliable trigger to
    // restore it without waiting for the next user interaction.
    // A 300 ms delay lets any in-flight TCP close reach the server before we
    // open a new connection (same rationale as the onclose 500 ms delay).
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && !this.connected) {
        if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); this._reconnectTimer = null; }
        this._reconnectTimer = setTimeout(() => {
          this._reconnectTimer = null;
          if (!this.connected) this.connect().catch(() => {});
        }, 300);
      }
    });

    // Belt-and-suspenders watchdog: reconnect every 30 s if somehow still
    // disconnected (handles edge cases where onclose did not fire).
    setInterval(() => {
      if (!this.connected && !this._reconnectTimer) {
        this.connect().catch(() => {});
      }
    }, 30_000);
  }

  get connected(): boolean {
    return this._ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Register a global handler for a message type (broadcasts from other devices).
   * Pass null to remove the handler.
   */
  setTypeHandler(type: string, handler: _WsMsgHandler | null): void {
    if (handler) this._typeHandlers.set(type, handler);
    else this._typeHandlers.delete(type);
  }

  /**
   * Open the WebSocket and perform the Telegram initData auth handshake.
   * Safe to call multiple times — deduplicates concurrent calls.
   */
  async connect(): Promise<boolean> {
    if (this.connected) return true;
    if (this._connectPromise) return this._connectPromise;

    this._connectPromise = new Promise<boolean>((resolve) => {
      this._authResolve = resolve;

      let ws: WebSocket;
      try {
        ws = new WebSocket(_wsUrl());
      } catch {
        resolve(false);
        this._connectPromise = null;
        return;
      }
      this._ws = ws;

      ws.onopen = () => {
        // initData.raw() returns the Telegram WebApp initData string.
        // Wrap in try/catch for dev/mock environments where it may throw.
        let raw = '';
        try { raw = initData.raw() || ''; } catch { /* dev/mock env */ }
        ws.send(JSON.stringify({ type: 'auth', init_data: raw }));
      };

      ws.onmessage = (e: MessageEvent) => {
        let msg: Record<string, unknown>;
        try { msg = JSON.parse(e.data as string) as Record<string, unknown>; }
        catch { return; }
        this._route(msg);
      };

      ws.onclose = () => {
        this._authResolve?.(false);
        this._authResolve = null;
        this._connectPromise = null;
        this._ws = null;
        // Stop keepalive pings.
        if (this._keepaliveTimer) { clearInterval(this._keepaliveTimer); this._keepaliveTimer = null; }
        // Reject all pending per-request handlers.
        for (const handler of this._handlers.values()) {
          handler({ type: 'connection_lost' });
        }
        this._handlers.clear();
        // Notify global connection_lost handler (e.g. to reset streaming state in UI).
        this._typeHandlers.get('connection_lost')?.({ type: 'connection_lost' });
        // Auto-reconnect after a short delay.
        // 500 ms gives the server time to process the TCP close before we open a new
        // connection — prevents a brief "devices=2" state from the same client.
        if (!this._reconnectTimer) {
          this._reconnectTimer = setTimeout(() => {
            this._reconnectTimer = null;
            this.connect().catch(() => {});
          }, 500);
        }
      };

      ws.onerror = () => {};
    });

    const result = await this._connectPromise;
    this._connectPromise = null;
    return result;
  }

  private _route(msg: Record<string, unknown>): void {
    this._lastServerMsgAt = Date.now();
    const type = msg.type as string;
    // Internal protocol frames
    if (type === 'auth_ok') {
      this._authResolve?.(true);
      this._authResolve = null;
      // Start client-side keepalive: send ping every 25 s so Cloudflare never
      // drops the TCP connection due to inactivity (idle timeout = 100 s).
      if (this._keepaliveTimer) clearInterval(this._keepaliveTimer);
      this._keepaliveTimer = setInterval(() => {
        if (this._ws?.readyState === WebSocket.OPEN) {
          this._ws.send('{"type":"ping"}');
        }
      }, 25_000);
      return;
    }
    if (type === 'auth_error')      { this._authResolve?.(false); this._authResolve = null; return; }
    if (type === 'ping')            { this._ws?.send('{"type":"pong"}'); return; }
    if (type === 'connection_ack')  { this._typeHandlers.get('connection_ack')?.(msg); return; }
    // Smart routing:
    //   Frame has a matching id-handler  → originating device (resolve the promise)
    //   No matching id-handler           → broadcast to another device (use type-handler)
    const id = msg.id as string | undefined;
    if (id && this._handlers.has(id)) {
      this._handlers.get(id)!(msg);
    } else {
      this._typeHandlers.get(type)?.(msg);
    }
  }

  /**
   * Send a chat request and resolve with the full response once generation is done.
   * Shows a spinner on the calling device until chat_done is received.
   */
  async chatStream(
    body: ChatBody,
    onDelta?: (text: string) => void,
  ): Promise<ChatCompleteResponse> {
    const ok = await this.connect();
    if (!ok) throw new Error('network error');
    const id = crypto.randomUUID();
    return new Promise<ChatCompleteResponse>((resolve, reject) => {
      this._handlers.set(id, (msg) => {
        const t = msg.type as string;
        if (t === 'chat_delta') {
          onDelta?.((msg.text as string) ?? '');
        } else if (t === 'chat_done') {
          this._handlers.delete(id);
          const m = (msg.message ?? null) as DialogMessage | null;
          resolve({
            answer:          typeof m?.content === 'string' ? m.content : '',
            id:              m?.id,
            usage:           m?.usage,
            n_first_removed: (msg.n_first_removed as number)  ?? 0,
            is_flagged:      (msg.is_flagged      as boolean) ?? false,
            dialog_id:        msg.dialog_id as string | undefined,
          });
        } else if (t === 'chat_error') {
          this._handlers.delete(id);
          reject(new Error((msg.error as string) || 'chat error'));
        } else if (t === 'connection_lost') {
          this._handlers.delete(id);
          reject(Object.assign(new Error('network error'), { reqId: id }));
        }
      });
      this._ws!.send(JSON.stringify({
        type:      'chat',
        id,
        message:   body.message,
        model:     body.model,
        dialog_id: body.dialog_id ?? null,
        chat_mode: body.chat_mode ?? 'mini_app_assistant',
        image_url: body.image_url ?? null,
      }));
    });
  }

  /**
   * Generate an image via WebSocket.
   * onProgress is called with 'moderating' then 'generating'.
   * Resolves with base64-encoded WebP data + dialog_id.
   */
  async generateImage(
    message:    string,
    dialogId:   string | null | undefined,
    onProgress: (step: string) => void,
  ): Promise<{ url: string; dialog_id?: string; id?: string }> {
    const ok = await this.connect();
    if (!ok) throw new Error('network error');
    const id = crypto.randomUUID();
    return new Promise<{ url: string; dialog_id?: string; id?: string }>((resolve, reject) => {
      this._handlers.set(id, (msg) => {
        const t = msg.type as string;
        if (t === 'image_progress') {
          onProgress(msg.step as string);
        } else if (t === 'image_done') {
          this._handlers.delete(id);
          resolve({
            url: msg.url as string,
            dialog_id: msg.dialog_id as string | undefined,
            id: (msg.message as DialogMessage | undefined)?.id,
          });
        } else if (t === 'image_error') {
          this._handlers.delete(id);
          reject(new Error((msg.error as string) || 'image generation failed'));
        } else if (t === 'connection_lost') {
          this._handlers.delete(id);
          reject(Object.assign(new Error('network error'), { reqId: id }));
        }
      });
      this._ws!.send(JSON.stringify({
        type:      'image',
        id,
        message,
        dialog_id: dialogId ?? null,
      }));
    });
  }
}

export const wsClient = new WsClient();
