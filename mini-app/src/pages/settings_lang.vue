<template>
  <div id="root" class="swipe-y-off">
    <div class="swipe-y-on scroll-area">
    <div class="wrapper">
      <div class="settingschange-wrapper">
        <div class="settingschange-container">

          <div class="settingschange-title">{{ $t('system_language') }}</div>
          <div class="settingschange-select">
            <!-- Auto: follow Telegram language -->
            <span
              v-ripple
              class="settingschange-select-button"
              :class="{ active: selectedLang === 'system' }"
              @click="updateLanguage('system')"
            >
              <div class="settingschange-select-label">
                <span class="settingschange-select-main">{{ $t('system_lang') }}</span>
              </div>
              <svg class="radio-btn" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke-width="2" :stroke="selectedLang === 'system' ? 'var(--tg-theme-button-color)' : 'var(--tg-theme-hint-color)'" />
                <circle v-if="selectedLang === 'system'" cx="12" cy="12" r="6" fill="var(--tg-theme-button-color)" />
              </svg>
            </span>
            <template v-for="lang in LANGUAGES" :key="lang.code">
              <span
                v-ripple
                class="settingschange-select-button"
                :class="{ active: selectedLang === lang.code }"
                @click="updateLanguage(lang.code)"
              >
                <div class="settingschange-select-label">
                  <span class="settingschange-select-main">{{ lang.native }}</span>
                  <span class="settingschange-select-native">{{ $t(lang.i18nKey) }}</span>
                </div>
                <svg class="radio-btn" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="10" stroke-width="2" :stroke="selectedLang === lang.code ? 'var(--tg-theme-button-color)' : 'var(--tg-theme-hint-color)'" />
                  <circle v-if="selectedLang === lang.code" cx="12" cy="12" r="6" fill="var(--tg-theme-button-color)" />
                </svg>
              </span>
            </template>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { initData } from '@tma.js/sdk-vue';
import { api } from '@/services/api';
import { useUserStore } from '@/store/user';

defineOptions({ name: 'SettingsLang' });

// Language list in display order
const LANGUAGES = [
  { code: 'en', native: 'English',   i18nKey: 'lang_en' },
  { code: 'ru', native: 'Русский',  i18nKey: 'lang_ru' },
  { code: 'de', native: 'Deutsch',   i18nKey: 'lang_de' },
  { code: 'fr', native: 'Français',  i18nKey: 'lang_fr' },
  { code: 'es', native: 'Español',   i18nKey: 'lang_es' },
  { code: 'pt', native: 'Português', i18nKey: 'lang_pt' },
  { code: 'tr', native: 'Türkçe',   i18nKey: 'lang_tr' },
  { code: 'pl', native: 'Polski',    i18nKey: 'lang_pl' },
] as const;

const _CIS_LANGS = new Set(['ru', 'be', 'uk', 'kk', 'ky', 'uz', 'tg', 'tk', 'hy', 'az', 'mo']);
const _SUPPORTED_LANGS = new Set(['ru', 'en', 'de', 'es', 'fr', 'pl', 'pt', 'tr']);

const { locale } = useI18n();
const store = useUserStore();

// Track raw DB value: 'ru' | 'en' | 'de' | ... | 'system'
const selectedLang = ref<string>(store.user?.language ?? 'system');

/** Resolve effective i18n locale for a raw lang value (mirrors main.ts resolveLocale). */
function resolveLocale(lang: string): string {
  if (lang === 'system') {
    try {
      const tgLang = initData.user()?.language_code;
      if (tgLang) {
        const base = tgLang.split('-')[0].toLowerCase();
        if (_CIS_LANGS.has(base)) return 'ru';
        if (_SUPPORTED_LANGS.has(base)) return base;
      }
    } catch {
      // fall through
    }
    return 'en';
  }
  return _SUPPORTED_LANGS.has(lang) ? lang : 'en';
}

const updateLanguage = async (lang: string): Promise<void> => {
  if (selectedLang.value === lang) return;
  const prev = selectedLang.value;
  const prevLocale = locale.value;
  const prevUserLang = store.user?.language;
  selectedLang.value = lang;
  locale.value = resolveLocale(lang);
  if (store.user) store.user.language = lang;
  try {
    await api.updateMe({ language: lang });
  } catch (e) {
    selectedLang.value = prev;
    locale.value = prevLocale;
    if (store.user && prevUserLang !== undefined) store.user.language = prevUserLang;
    console.error('[SettingsLang] Failed to sync language to DB:', e);
  }
};
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

.wrapper {
  min-height: 100%;
  padding-bottom: 24px;
}

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
  background-color: var(--second-bg-color);
}

.settingschange-select-button.saving {
  opacity: 0.6;
  pointer-events: none;
}

.radio-btn {
  flex-shrink: 0;
}

.settingschange-select-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.settingschange-select-main {
  font-size: 17px;
  font-weight: 400;
  color: var(--text-color);
  line-height: 22px;
}

.settingschange-select-native {
  font-size: 12px;
  color: var(--icons-storke-color);
  line-height: 16px;
}
</style>

