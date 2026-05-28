<template>
  <div id="root">
    <div
      class="wrapper"
      style="padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); transition: padding 100ms;"
    >
      <div class="settings__wrapper">
        <!-- Первый блок -->
        <div class="settings__container">
          <div class="settings__container-buttons">
            <span class="settings__container-button">
              <div class="settings__container-icon" style="background-color: rgb(252, 46, 82)">
                <img :src="profileSvg" alt="Profile" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('user_id') }}</div>
                </div>
                <div class="settings__container-text-value"> {{ userId }}</div>
              </div>
            </span>
          </div>
        </div>
        <!-- Второй блок -->
        <div class="settings__container">
          <div class="settings__container-buttons">
            <span class="settings__container-button interactive" @click="router.push('/settings/language')">
              <div class="settings__container-icon" style="background-color: rgb(183, 77, 235)">
                <img :src="languageSvg" alt="Language" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('system_language') }}</div>
                </div>
                <div class="settings__container-text-value">
                  <span class="settings__current-val">{{ currentLangLabel }}</span>
                  <svg class="settings-chevron" width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 8L14 12L10 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </span>
            <div class="settings__divider"></div>
            <span class="settings__container-button interactive" @click="router.push('/settings/theme')">
              <div class="settings__container-icon" style="background-color: rgb(0, 122, 255)">
                <img :src="themeSvg" alt="Theme" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('theme') }}</div>
                </div>
                <div class="settings__container-text-value">
                  <span class="settings__current-val">{{ currentThemeLabel }}</span>
                  <svg class="settings-chevron" width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 8L14 12L10 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </span>
          </div>
        </div>
        <!-- Третий блок -->
        <div class="settings__container">
          <div class="settings__container-buttons">
            <span class="settings__container-button interactive" @click="openSupport">
              <div class="settings__container-icon" style="background-color: rgb(255, 149, 0)">
                <img :src="helpSvg" alt="Help" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('contact_support') }}</div>
                </div>
                <div class="settings__container-text-value">
                  <svg class="settings-chevron" width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 8L14 12L10 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </span>
            <div class="settings__divider"></div>
            <span class="settings__container-button interactive" @click="shareApp">
              <div class="settings__container-icon" style="background-color: rgb(50, 173, 230)">
                <img :src="shareSvg" alt="Share" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('share_app') }}</div>
                </div>
                <div class="settings__container-text-value">
                  <svg class="settings-chevron" width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 8L14 12L10 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </span>
          </div>
        </div>
        <!-- Четвёртый блок -->
        <div class="settings__container">
          <div class="settings__container-buttons">
            <span class="settings__container-button interactive" @click="openReleases">
              <div class="settings__container-icon" style="background-color: rgb(167, 166, 166)">
                <img :src="versionSvg" alt="Version" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('version') }}</div>
                </div>
                <div class="settings__container-text-value">
                  <span class="settings__current-val">2.2.3</span>
                  <svg class="settings-chevron" width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 8L14 12L10 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </span>
            <div class="settings__divider"></div>
            <span class="settings__container-button interactive" @click="openAuthor">
              <div class="settings__container-icon" style="background-color: rgb(167, 166, 166);">
                <img :src="autor" alt="Author" />
              </div>
              <div class="settings__container-text">
                <div class="settings__container-text-title">
                  <div class="settings__container-title-text">{{ $t('author') }}</div>
                </div>
                <div class="settings__container-text-value">
                  <span class="settings__current-val">@aso_off</span>
                  <svg class="settings-chevron" width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 8L14 12L10 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </span>
          </div>
        </div>

      </div>
    </div>
    <div id="veepn-guard-alert"></div>
    <div id="veepn-breach-alert"></div>
  </div>
</template>


<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { openLink, openTelegramLink } from '@tma.js/sdk-vue';
import { useUserStore } from '@/store/user';
// Импорт изображений
import profileSvg from '@/components/img/profile.svg';
import languageSvg from '@/components/img/language.svg';
import themeSvg from '@/components/img/theme.svg';
import helpSvg from '@/components/img/help.svg';
import shareSvg from '@/components/img/Share.svg';
import versionSvg from '@/components/img/version.svg';
import autor from '@/components/img/autor.svg';

defineOptions({ name: 'SettingsPage' });

const store = useUserStore();
const { t } = useI18n();
const router = useRouter();

// Текущий выбор темы для отображения в списке настроек
const currentThemeLabel = computed(() => {
  const o = store.currentTheme as 'system' | 'light' | 'dark';
  if (o === 'dark') return t('dark');
  if (o === 'light') return t('light');
  return t('system');
});

const currentLangLabel = computed(() => {
  const lang = store.user?.language ?? 'system';
  const names: Record<string, string> = {
    en: 'English',
    ru: 'Русский',
    de: 'Deutsch',
    fr: 'Français',
    es: 'Español',
    pt: 'Português',
    tr: 'Türkçe',
    pl: 'Polski',
  };
  return names[lang] ?? t('system_lang');
});

// Реальный Telegram user ID из initData
const userId = computed(() => store.userId ?? '—');

// Шеринг через openTelegramLink — открывает t.me-ссылки внутри Telegram
const shareApp = () => {
  const botLink = 'https://t.me/Monkey_GPTbot';
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(botLink)}`;
  openTelegramLink(shareUrl);
};

const openSupport = () => {
  openTelegramLink('https://t.me/MonkeyAI_Support');
};

const openReleases = () => {
  openLink('https://github.com/aso-off/MonkeyAI/releases');
};

const openAuthor = () => {
  openTelegramLink('https://t.me/aso_off');
};
</script>

<style scoped>
img[src$=".svg"]:not(.line) {
  filter: brightness(0) saturate(100%) invert(100%);
}
.settings-chevron {
  color: #3D3D3F;
  flex-shrink: 0;
}
body.dark .settings-chevron {
  color: #c0c0c0;
}
.settings__current-val {
  font-size: 17px;
  color: var(--icons-storke-color);
  white-space: nowrap;
}
</style>
