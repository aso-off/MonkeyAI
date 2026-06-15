import { ref } from "vue";

export const markdownReady = ref(false);

let renderFn: ((s: string) => string) | null = null;
let loading: Promise<void> | null = null;

/** Грузит тяжёлый markdown-чанк один раз. Идемпотентно, не падает наружу. */
export function preloadMarkdown(): Promise<void> {
  if (loading) return loading;
  loading = import("@/utils/markdown")
    .then((m) => {
      renderFn = m.renderMarkdown;
      markdownReady.value = true;
    })
    .catch((e) => {
      console.error("[markdown] preload failed:", e);
    });
  return loading;
}

/** Рендер, если чанк уже загружен; иначе null (вызывающий покажет fallback). */
export function renderMarkdownSafe(text: string): string | null {
  return renderFn ? renderFn(text) : null;
}
