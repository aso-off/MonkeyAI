<template>
  <div id="root" class="swipe-y-off">
    <div class="swipe-y-on scroll-area" ref="rootEl" @scroll="onScroll">
      <div class="img-wrapper">
        <!-- Ввод -->
        <form class="img-form" @submit.prevent="submitImage">
          <input
            v-model="prompt"
            class="img-input"
            :placeholder="$t('describe_image')"
            enterkeyhint="send"
          />
          <button v-ripple class="img-send" type="submit" :disabled="!prompt.trim()">
            <img :src="newChatSvg" alt="" draggable="false" />
          </button>
        </form>

        <!-- Галерея -->
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
        <button v-ripple class="viewer-save" @click="saveImage(viewer)">{{ $t('save') }}</button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/services/api';
import { useUserStore } from '@/store/user';
import { useImagesStore } from '@/store/images';
import newChatSvg from '@/components/img/new_chat.svg';

defineOptions({ name: 'ImagesPage' });

const router = useRouter();
const store = useUserStore();
const images = useImagesStore();

const rootEl = ref<HTMLElement | null>(null);
const prompt = ref('');
const viewer = ref<string | null>(null);

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

async function saveImage(url: string) {
  try {
    const resp = await fetch(url);
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `monkey-ai-${Date.now()}.webp`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
  } catch {
    window.open(url, '_blank');
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
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.scroll-area::-webkit-scrollbar {
  display: none;
}
.img-wrapper {
  min-height: 100%;
  padding: calc(env(safe-area-inset-top) + 12px) 14px 24px;
}
.img-form {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.img-input {
  flex: 1;
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
  background: var(--second-bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.img-send:disabled {
  opacity: 0.4;
}
.img-send img {
  width: 22px;
  height: 22px;
  filter: brightness(0) saturate(100%) invert(100%);
  pointer-events: none;
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
  padding: 48px 0;
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
  padding: 12px 28px;
  border-radius: 24px;
  background: var(--second-bg-color);
  color: var(--text-color);
  font-size: 16px;
  font-weight: 600;
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
