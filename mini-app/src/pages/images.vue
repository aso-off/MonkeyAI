<template>
  <div id="root" class="swipe-y-off">
    <div class="swipe-y-on scroll-area" ref="rootEl" @scroll="onScroll">
      <div class="img-page">
        <!-- Заголовок -->
        <div class="img-head">{{ $t('images') }}</div>

        <!-- Ввод промпта — по центру -->
        <div class="img-hero">
          <form class="img-form" @submit.prevent="submitImage">
            <input
              v-model="prompt"
              class="img-input"
              :placeholder="$t('describe_image')"
              enterkeyhint="send"
            />
            <button class="img-send" type="submit" :disabled="!prompt.trim()" aria-label="send">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 19V5M5 12L12 5L19 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </form>
        </div>

        <!-- Галерея снизу -->
        <template v-if="images.loading && images.list.length === 0">
          <div class="img-grid">
            <div v-for="n in 6" :key="n" class="img-skeleton"></div>
          </div>
        </template>

        <div v-else-if="images.list.length === 0" class="img-empty">{{ $t('no_images') }}</div>

        <div v-else class="img-grid">
          <div
            v-for="it in images.list"
            :key="it.id"
            class="img-cell"
            @click="viewer = it.url"
          >
            <img :src="it.url" :alt="it.prompt" loading="lazy" />
          </div>
        </div>
      </div>
    </div>

    <!-- Фуллскрин -->
    <Transition name="viewer">
      <div v-if="viewer" class="viewer" @click.self="viewer = null">
        <img class="viewer-img" :src="viewer" alt="" />
        <button v-if="canExport" v-ripple class="viewer-save" @click="saveImage(viewer)">
          {{ $t('save') }}
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { retrieveLaunchParams } from '@tma.js/sdk-vue';
import { api } from '@/services/api';
import { useUserStore } from '@/store/user';
import { useImagesStore } from '@/store/images';

defineOptions({ name: 'ImagesPage' });

const router = useRouter();
const store = useUserStore();
const images = useImagesStore();

const rootEl = ref<HTMLElement | null>(null);
const prompt = ref('');
const viewer = ref<string | null>(null);

/** Save доступен только там, где есть системный диалог «куда сохранить» / шеринг. */
const canExport = computed(() => {
  try {
    const p = retrieveLaunchParams().tgWebAppPlatform ?? '';
    return p === 'ios' || p === 'macos' || p === 'tdesktop';
  } catch {
    return false;
  }
});

function onScroll() {
  const el = rootEl.value;
  if (!el) return;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 300) {
    images.loadMore().catch(() => {});
  }
}

async function submitImage() {
  const text = prompt.value.trim();
  if (!text) return;
  prompt.value = '';
  try {
    await store.setModel('gpt-image-1.5');
    const { dialog_id } = await api.newDialog();
    router.push({ name: 'chat', params: { dialogId: dialog_id }, query: { gen: text } });
  } catch (e) {
    console.error('[submitImage]', e);
  }
}

interface FsWritable { write(data: Blob): Promise<void>; close(): Promise<void>; }
interface FsHandle { createWritable(): Promise<FsWritable>; }
type ShowSaveFilePicker = (opts: {
  suggestedName?: string;
  types?: { description: string; accept: Record<string, string[]> }[];
}) => Promise<FsHandle>;

/**
 * Системное сохранение — только диалог «куда сохранить»:
 *   1. showSaveFilePicker — нативное «Сохранить как» (ПК / tdesktop)
 *   2. navigator.share({files}) — системный share-лист (iOS / macOS)
 * Без молчаливого auto-download.
 */
async function saveImage(url: string) {
  let blob: Blob;
  try {
    blob = await (await fetch(url)).blob();
  } catch {
    return;
  }
  const filename = `monkey-ai-${Date.now()}.webp`;

  const filePicker = (window as Window & { showSaveFilePicker?: ShowSaveFilePicker }).showSaveFilePicker;
  if (typeof filePicker === 'function') {
    try {
      const handle = await filePicker({
        suggestedName: filename,
        types: [{ description: 'Image', accept: { 'image/webp': ['.webp'] } }],
      });
      const w = await handle.createWritable();
      await w.write(blob);
      await w.close();
    } catch (err: unknown) {
      if ((err as Error)?.name === 'AbortError') return;
    }
    return;
  }

  if (typeof navigator.share === 'function') {
    try {
      await navigator.share({ files: [new File([blob], filename, { type: blob.type })] });
    } catch {
      /* отменено пользователем / не поддержано */
    }
  }
}

onMounted(() => {
  images.loadInitial().catch(() => {});
});
</script>

<style scoped>
.scroll-area {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior-y: contain;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.scroll-area::-webkit-scrollbar {
  display: none;
}
.img-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  padding: calc(env(safe-area-inset-top) + 8px) 14px 24px;
}
.img-head {
  text-align: center;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
  padding: 10px 0 4px;
}
.img-hero {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 32vh;
  padding: 12px 0 22px;
}
.img-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.img-cell {
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background: var(--second-bg-color);
}
.img-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.img-skeleton {
  aspect-ratio: 1;
  border-radius: 12px;
  background: #6b6f7438;
}
.img-empty {
  text-align: center;
  color: var(--icons-storke-color);
  padding: 64px 0;
}

.img-form {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 560px;
}
.img-input {
  flex: 1;
  min-width: 0;
  height: 48px;
  padding: 0 16px;
  border: none;
  outline: none;
  border-radius: 24px;
  background: var(--second-bg-color);
  color: var(--text-color);
  font-size: 16px;
}
.img-send {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--tg-theme-button-color, #3390ec);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: none;
  transition: opacity 0.15s ease;
}
.img-send:disabled {
  opacity: 0.4;
}

.viewer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.92);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 24px;
}
.viewer-img {
  max-width: 100%;
  max-height: 80%;
  object-fit: contain;
  border-radius: 12px;
}
.viewer-save {
  padding: 13px 36px;
  border-radius: 24px;
  border: none;
  background: var(--tg-theme-button-color, #3390ec);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  position: relative;
  overflow: hidden;
}
.viewer-enter-active,
.viewer-leave-active {
  transition: opacity 200ms ease;
}
.viewer-enter-from,
.viewer-leave-to {
  opacity: 0;
}
</style>
