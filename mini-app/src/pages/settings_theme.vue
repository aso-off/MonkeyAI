<template>
  <div id="root">
    <div
      class="wrapper"
      style="padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); transition: padding 100ms;"
    >
      <div class="settingschange-wrapper">
        <div class="settingschange-container">
          <div class="settingschange-title">{{ $t('theme') }}</div>
          <div class="settingschange-select">
            <span
              v-ripple
              class="settingschange-select-button"
              :class="{ active: currentTheme === 'system' }"
              @click="updateTheme('system')"
            >
              {{ $t('system') }}
              <svg class="radio-btn" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke-width="2" :stroke="currentTheme === 'system' ? 'var(--tg-theme-button-color)' : 'var(--tg-theme-hint-color)'" />
                <circle v-if="currentTheme === 'system'" cx="12" cy="12" r="6" fill="var(--tg-theme-button-color)" />
              </svg>
            </span>
            <div class="settingschange-divider"></div>
            <span
              v-ripple
              class="settingschange-select-button"
              :class="{ active: currentTheme === 'dark' }"
              @click="updateTheme('dark')"
            >
              {{ $t('dark') }}
              <svg class="radio-btn" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke-width="2" :stroke="currentTheme === 'dark' ? 'var(--tg-theme-button-color)' : 'var(--tg-theme-hint-color)'" />
                <circle v-if="currentTheme === 'dark'" cx="12" cy="12" r="6" fill="var(--tg-theme-button-color)" />
              </svg>
            </span>
            <div class="settingschange-divider"></div>
            <span
              v-ripple
              class="settingschange-select-button"
              :class="{ active: currentTheme === 'light' }"
              @click="updateTheme('light')"
            >
              {{ $t('light') }}
              <svg class="radio-btn" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke-width="2" :stroke="currentTheme === 'light' ? 'var(--tg-theme-button-color)' : 'var(--tg-theme-hint-color)'" />
                <circle v-if="currentTheme === 'light'" cx="12" cy="12" r="6" fill="var(--tg-theme-button-color)" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </div>
    <div id="veepn-breach-alert"></div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useUserStore } from '@/store/user';

defineOptions({ name: 'SettingsTheme' });

const store = useUserStore();
const currentTheme = ref<string>(store.currentTheme);

function updateTheme(theme: string): void {
  if (currentTheme.value === theme) return;
  currentTheme.value = theme;
  store.setTheme(theme).catch(() => {
    currentTheme.value = store.currentTheme;
  });
}
</script>

<style scoped>
.settingschange-select-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  box-sizing: border-box;
  padding: 10px 16px;
  min-height: 54px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  -webkit-tap-highlight-color: transparent;
  transition: background-color 0.15s ease;
}

.settingschange-select-button:active {
  background-color: var(--third-bg-color);
}

.settingschange-select-button.saving {
  opacity: 0.6;
  pointer-events: none;
}

.radio-btn {
  flex-shrink: 0;
}
</style>