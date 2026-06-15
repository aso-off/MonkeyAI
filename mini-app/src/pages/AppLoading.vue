<template>
  <div class="loading-screen">

    <!-- Top: localised welcome greeting + subtitle -->
    <div class="loading-top">
      <span class="loading-title">{{ welcomeText }}</span>
      <span class="loading-subtitle">{{ t('loading_subtitle') }}</span>
    </div>

    <!-- Centre: random TGS sticker -->
    <div class="loading-center">
      <div class="loading-sticker-area">
        <!-- Sticker: fades in once lottie is ready -->
        <div
          ref="stickerContainer"
          class="loading-sticker"
          :class="{ 'loading-sticker--visible': stickerLoaded }"
        />
      </div>
    </div>

    <!-- Bottom: step label + progress bar OR error state -->
    <div class="loading-bottom">
      <template v-if="!showError">
        <Transition name="step-fade" mode="out-in">
          <div class="loading-step" :key="stepText">{{ stepText }}</div>
        </Transition>
        <div class="loading-bar-row">
          <div class="loading-bar-track">
            <div class="loading-bar-fill" :style="{ width: progress + '%' }"></div>
          </div>
        </div>
        <div v-if="randomTip" class="loading-tip">{{ randomTip }}</div>
      </template>
      <template v-else>
        <div class="loading-error-text">{{ t('loading_error') }}</div>
        <button class="loading-retry-btn" @click="onRetry">{{ t('loading_retry') }}</button>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { miniApp, initData } from '@tma.js/sdk-vue';
import { useUserStore } from '@/store/user';
import { useDialogsStore } from '@/store/dialogs';
import { preloadMarkdown } from '@/utils/markdownReady';
import lottie, { type AnimationItem } from 'lottie-web';

defineOptions({ name: 'AppLoading' });

const emit = defineEmits<{ done: [] }>();

const { t, tm, locale } = useI18n();
const store = useUserStore();
const dialogs = useDialogsStore();

const progress = ref(0);
const stepText = ref('');
const showError = ref(false);
const stickerContainer = ref<HTMLDivElement | null>(null);
const stickerLoaded = ref(false);

// Welcome greeting — user's first name from TMA init data, fallback to "Monkey AI"
const _firstName = (() => {
  try { return initData.user()?.first_name ?? ''; } catch { return ''; }
})();
const welcomeText = computed(() =>
  _firstName ? t('loading_welcome', { name: _firstName }) : 'Monkey AI',
);

// Random tip — index fixed once so it stays stable even if locale changes mid-load
let _tipIndex = -1;
const randomTip = computed(() => {
  const tips = tm('loading_tips') as string[];
  if (!Array.isArray(tips) || tips.length === 0) return '';
  if (_tipIndex < 0) _tipIndex = Math.floor(Math.random() * tips.length);
  return (tips[_tipIndex] as string) ?? '';
});

// All TGS sticker URLs resolved at build time
const _stickerMap = import.meta.glob('../components/LoadingTgs/*.tgs', {
  query: '?url',
  import: 'default',
  eager: true,
}) as Record<string, string>;
const _stickerUrls = Object.values(_stickerMap);

let stickerAnim: AnimationItem | null = null;
let _mounted = true;
let _stickerTimer: ReturnType<typeof setTimeout> | null = null;

function _showSticker() {
  if (_stickerTimer !== null) { clearTimeout(_stickerTimer); _stickerTimer = null; }
  stickerLoaded.value = true;
}

async function loadRandomSticker() {
  if (_stickerUrls.length === 0) return;
  const url = _stickerUrls[Math.floor(Math.random() * _stickerUrls.length)];

  // Fallback: always remove skeleton after 3 s even if lottie never fires
  _stickerTimer = setTimeout(_showSticker, 3000);

  try {
    const res = await fetch(url);
    if (!_mounted) return;
    const ds = new DecompressionStream('gzip');
    const text = await new Response(res.body!.pipeThrough(ds)).text();
    if (!_mounted || !stickerContainer.value) return;
    const animData = JSON.parse(text);
    stickerAnim = lottie.loadAnimation({
      container: stickerContainer.value,
      renderer: 'svg',
      loop: true,
      autoplay: true,
      animationData: animData,
      rendererSettings: {
        preserveAspectRatio: 'xMidYMid meet',
        progressiveLoad: true,
      },
    });
    // DOMLoaded fires when lottie inserts the SVG into the DOM — more reliable than data_ready
    stickerAnim.addEventListener('DOMLoaded', _showSticker);
    stickerAnim.addEventListener('error', _showSticker);
  } catch (e) {
    _showSticker();
    console.error('TGS load failed', e);
  }
}

// Each call to runLoading() gets a unique id. When auto-restart fires, the
// previous run detects it's stale via this counter and exits cleanly.
let _runId = 0;
let _retryCount = 0;

/** Smoothly animate progress to `target` over `duration` ms with ease-in-out cubic. */
function animateTo(target: number, duration: number): Promise<void> {
  return new Promise(resolve => {
    const start = progress.value;
    const startTime = performance.now();
    function step(now: number) {
      const elapsed = now - startTime;
      const frac = Math.min(elapsed / duration, 1);
      // ease-in-out cubic — slow start, slow end, feels organic
      const eased = frac < 0.5
        ? 4 * frac * frac * frac
        : 1 - Math.pow(-2 * frac + 2, 3) / 2;
      progress.value = start + (target - start) * eased;
      if (frac < 1) {
        requestAnimationFrame(step);
      } else {
        progress.value = target;
        resolve();
      }
    }
    requestAnimationFrame(step);
  });
}

/** Pause for `ms` milliseconds. */
function pause(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

async function runLoading(): Promise<void> {
  const myId = ++_runId;
  progress.value = 0;
  showError.value = false;

  stepText.value = t('loading_init_tg');
  await animateTo(25, 500);
  if (myId !== _runId) return;
  await pause(200);

  stepText.value = t('loading_check_user');
  await animateTo(50, 500);
  if (myId !== _runId) return;
  await pause(200);

  stepText.value = t('loading_data');
  await animateTo(85, 800);
  if (myId !== _runId) return;

  try {
    await store.init();
    // init() swallows its own errors — check explicitly so we retry if getMe failed.
    if (!store.user) throw new Error('user not loaded');
    if (store.user.is_whitelisted) {
      await Promise.all([
        store.prefetchChatHistory(),
        dialogs.loadInitial().catch(() => {}),
        preloadMarkdown(), // стили/форматирование готовы до показа чата
      ]);
    }
  } catch {
    // API failed — retry up to 3 times with 3 s delay, then show error.
    if (myId !== _runId) return;
    _retryCount++;
    if (_retryCount >= 3) {
      showError.value = true;
      return;
    }
    await pause(3_000);
    if (myId === _runId) runLoading();
    return;
  }

  if (myId !== _runId) return;

  stepText.value = t('loading_ui');
  await animateTo(100, 500);
  await pause(200);

  // Apply saved language preference at the very last moment — loading screen is about
  // to fade out, so no language switch is visible during loading. Main app opens with
  // the correct saved locale from the first frame.
  const _CIS_LANGS = new Set(['ru', 'be', 'uk', 'kk', 'ky', 'uz', 'tg', 'tk', 'hy', 'az', 'mo']);
  const _SUPPORTED_LANGS = new Set(['ru', 'en', 'de', 'es', 'fr', 'pl', 'pt', 'tr']);
  const lang = store.user?.language;
  if (lang && _SUPPORTED_LANGS.has(lang)) {
    locale.value = lang;
  } else if (lang === 'system' || !lang) {
    try {
      const tgLang = initData.user()?.language_code;
      if (tgLang) {
        const base = tgLang.split('-')[0].toLowerCase();
        if (_CIS_LANGS.has(base)) locale.value = 'ru';
        else if (_SUPPORTED_LANGS.has(base)) locale.value = base;
        else locale.value = 'en';
      }
    } catch { /* keep current locale */ }
  }

  emit('done');
}

function onRetry() {
  _retryCount = 0;
  runLoading();
}

onMounted(() => {
  miniApp.ready?.();
  loadRandomSticker();
  runLoading();
});

onUnmounted(() => {
  _mounted = false;
  if (_stickerTimer !== null) { clearTimeout(_stickerTimer); _stickerTimer = null; }
  stickerAnim?.destroy();
  stickerAnim = null;
});
</script>

<style scoped>
.loading-screen {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: max(env(safe-area-inset-top), 40px) 28px max(env(safe-area-inset-bottom), 40px);
  background-color: var(--tg-theme-bg-color, #1c1c1e);
}

/* ── Top: App name ─────────────────────────────── */
.loading-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 20px;
}

.loading-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: var(--tg-theme-text-color, #ffffff);
}

.loading-subtitle {
  font-size: 14px;
  font-weight: 400;
  color: var(--tg-theme-hint-color, #8e8e93);
  text-align: center;
  letter-spacing: 0.1px;
}

/* ── Centre: TGS sticker ────────────────────────── */
.loading-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-sticker-area {
  position: relative;
  width: 220px;
  height: 220px;
}

/* Sticker — fade in when lottie is ready */
.loading-sticker {
  position: absolute;
  inset: 0;
  overflow: hidden;
  opacity: 0;
  transition: opacity 400ms ease;
}

.loading-sticker--visible {
  opacity: 1;
}

/* Force lottie SVG to fill the container */
.loading-sticker :deep(svg) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

/* ── Step text fade transition ──────────────────── */
.step-fade-leave-active {
  transition: opacity 100ms ease;
}
.step-fade-enter-active {
  transition: opacity 220ms ease;
}
.step-fade-enter-from,
.step-fade-leave-to {
  opacity: 0;
}

/* ── Bottom progress ──────────────────────────── */
.loading-bottom {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.loading-tip {
  font-size: 12px;
  color: var(--tg-theme-hint-color, #8e8e93);
  text-align: center;
  max-width: 260px;
  line-height: 1.35;
  opacity: 0.7;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-top: 4px;
}

.loading-step {
  font-size: 13px;
  color: var(--tg-theme-hint-color, #8e8e93);
  min-height: 18px;
  text-align: center;
}

.loading-bar-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-bar-track {
  width: 55%;
  height: 6px;
  border-radius: 3px;
  background-color: var(--tg-theme-secondary-bg-color, #2c2c2e);
  overflow: hidden;
}

.loading-bar-fill {
  height: 100%;
  border-radius: 3px;
  background-color: var(--tg-theme-button-color, #2979ff);
  /* No CSS transition — easing is handled by the rAF animateTo() */
}

.loading-error-text {
  text-align: center;
  font-size: 15px;
  color: var(--tg-theme-hint-color, #8e8e93);
  margin-bottom: 20px;
}

.loading-retry-btn {
  display: block;
  width: 80%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  background-color: var(--tg-theme-button-color, #2979ff);
  color: var(--tg-theme-button-text-color, #ffffff);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
</style>