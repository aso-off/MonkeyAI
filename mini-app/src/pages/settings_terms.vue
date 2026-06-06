<template>
  <div id="root">
    <div class="wrapper">
      <div class="settingschange-wrapper">
        <div class="settingschange-container">
          <div class="settingschange-title">{{ $t('terms_of_service') }}</div>
          <div class="settingschange-select legal-section">
            <div class="legal-section-heading">{{ $t('page_in_development') }}</div>
            <div class="legal-section-body">
              {{ $t('page_in_development_desc') }}
              <span class="legal-support-link" @click="openSupport">{{ SUPPORT_HANDLE }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { openTelegramLink } from '@tma.js/sdk-vue';
import { APP_LINKS, SUPPORT_HANDLE } from '@/config/app';

defineOptions({ name: 'SettingsTerms' });

function openSupport() {
  openTelegramLink(APP_LINKS.support);
}
</script>

<style scoped>
#root {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

#root::-webkit-scrollbar {
  display: none;
}

.wrapper {
  min-height: 100%;
  padding-bottom: 24px;
}

.legal-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px !important;
}

.legal-section-heading {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
}

.legal-section-body {
  font-size: 15px;
  font-weight: 400;
  color: var(--icons-storke-color);
  line-height: 1.5;
}

.legal-support-link {
  color: var(--tg-theme-link-color, #007aff);
  cursor: pointer;
}
</style>
