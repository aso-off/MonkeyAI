<template>
  <div id="root">
    <div
      class="wrapper legal-page-wrapper"
      style="padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); transition: padding 100ms;"
    >
      <div class="legal-content">
        <h1 class="legal-title">{{ $t('privacy_policy') }}</h1>

        <div class="legal-section">
          <p class="legal-section-heading">{{ $t('page_in_development') }}</p>
          <p class="legal-section-body">
            {{ $t('page_in_development_desc') }}
            <span class="legal-support-link" @click="openSupport">@MonkeyAI_Support</span>
          </p>
        </div>
      </div>
    </div>
    <div id="veepn-guard-alert"></div>
    <div id="veepn-breach-alert"></div>
  </div>
</template>

<script setup lang="ts">
import { openTelegramLink } from '@tma.js/sdk-vue';

defineOptions({ name: 'SettingsPrivacy' });

function openSupport() {
  openTelegramLink('https://t.me/MonkeyAI_Support');
}
</script>

<style scoped>
.legal-page-wrapper {
  height: var(--tg-viewport-stable-height, 100vh);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.legal-page-wrapper::-webkit-scrollbar {
  display: none;
}

.legal-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px 16px 32px;
}

.legal-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-color);
  line-height: 1.2;
  margin: 0;
}

.legal-section {
  background-color: var(--second-bg-color);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legal-section-heading {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.legal-section-body {
  font-size: 15px;
  font-weight: 400;
  color: var(--icons-storke-color);
  line-height: 1.5;
  margin: 0;
}

.legal-support-link {
  color: var(--tg-theme-link-color, #007aff);
  cursor: pointer;
}
</style>
