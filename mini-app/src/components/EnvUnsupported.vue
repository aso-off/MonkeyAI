<script setup lang="ts">
import { retrieveLaunchParams, isColorDark, isRGB } from '@tma.js/sdk-vue';
import Placeholder from '@/components/Placeholder.vue';

// Mirrors useMemo logic in EnvUnsupported.tsx
let platform = 'android';
let isDark = false;
try {
  const lp = retrieveLaunchParams();
  const bgColor = lp.tgWebAppThemeParams?.bg_color;
  platform = lp.tgWebAppPlatform ?? 'android';
  isDark = bgColor && isRGB(bgColor) ? isColorDark(bgColor) : false;
} catch {
  // not in Telegram — defaults above
}

const isIOS = ['macos', 'ios'].includes(platform);
</script>

<template>
  <div
    class="app-root"
    :class="[isDark ? 'app-root--dark' : 'app-root--light', isIOS ? 'app-root--ios' : 'app-root--base']"
  >
    <Placeholder
      header="Oops"
      description="You are using too old Telegram client to run this application"
    >
      <img
        alt="Telegram sticker"
        src="https://xelene.me/telegram.gif"
      />
    </Placeholder>
  </div>
</template>

<style scoped>
.app-root {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  min-height: 100dvh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-root--light {
  background: #efeff3;
  color: #000;
}

.app-root--dark {
  background: #17212b;
  color: #f5f5f5;
}

.app-root--ios :deep(.placeholder__header) {
  font-size: 22px;
}
</style>