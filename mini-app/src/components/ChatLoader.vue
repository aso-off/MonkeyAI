<template>
  <div v-if="variant === 'image'" class="image-skeleton">
    <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5" />
      <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" stroke-width="1.5" />
      <path d="M3 16l5-5 4 4 2-2 4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </div>

  <div v-else ref="dotsEl" class="ai-thinking">
    <span></span><span></span><span></span>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps<{ variant: "image" | "thinking" }>();

const dotsEl = ref<HTMLElement | null>(null);
// setInterval надёжнее CSS-анимации: Telegram Desktop WebView паузит CSS infinite
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  if (props.variant !== "thinking") return;
  let tick = 0;
  timer = setInterval(() => {
    const dots = dotsEl.value?.querySelectorAll<HTMLElement>("span");
    if (!dots?.length) return;
    dots.forEach((dot, i) => {
      const t = ((tick - i * 4) % 30 + 30) % 30;
      const y = t < 18 ? -7 * Math.sin((t / 18) * Math.PI) : 0;
      dot.style.transform = `translateY(${y.toFixed(1)}px)`;
    });
    tick++;
  }, 40);
});

onBeforeUnmount(() => {
  if (timer !== null) clearInterval(timer);
});
</script>

<style>
.image-skeleton {
  width: 240px;
  height: 240px;
  border-radius: 8px;
  background: #e5e5ea;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #aeaeb2;
  flex-shrink: 0;
}

body.dark .image-skeleton {
  background: #3a3a3c;
  color: #636366;
}

.ai-thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 2px;
  min-height: 28px;
}

.ai-thinking span {
  display: block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  will-change: transform;
}

.ai-thinking span:nth-child(1) { background-color: #c0c0c0; }
.ai-thinking span:nth-child(2) { background-color: #808080; }
.ai-thinking span:nth-child(3) { background-color: #303030; }

body.dark .ai-thinking span:nth-child(1) { background-color: #555; }
body.dark .ai-thinking span:nth-child(2) { background-color: #aaa; }
body.dark .ai-thinking span:nth-child(3) { background-color: #eee; }
</style>