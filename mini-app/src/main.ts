import './assets/index.css';

import { createApp } from 'vue';
import { createI18n } from 'vue-i18n';
import { createPinia } from 'pinia';
import { retrieveLaunchParams, initData } from '@tma.js/sdk-vue';

import App from './App.vue';
import EnvUnsupported from './components/EnvUnsupported.vue';
import router from './router';
import { errorHandler } from './errorHandler';
import { init } from './init';

// Import locales
import en from './locales/en.json';
import ru from './locales/ru.json';
import de from './locales/de.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import pl from './locales/pl.json';
import pt from './locales/pt.json';
import tr from './locales/tr.json';

// Mock the environment in case, we are outside Telegram (DEV only — tree-shaken in production).
import './mockEnv';

/** Same CIS-language set as the bot's resolve_lang(): maps CIS langs → 'ru'. */
const _CIS_LANGS = new Set(['ru', 'be', 'uk', 'kk', 'ky', 'uz', 'tg', 'tk', 'hy', 'az', 'mo']);
const _SUPPORTED_LANGS = new Set(['ru', 'en', 'de', 'es', 'fr', 'pl', 'pt', 'tr']);

function resolveLocale(tgLang: string | undefined): string {
  if (tgLang) {
    const base = tgLang.split('-')[0].toLowerCase();
    if (_CIS_LANGS.has(base)) return 'ru';
    if (_SUPPORTED_LANGS.has(base)) return base;
  }
  return 'en';
}

// Wrap in an async function to avoid top-level await in the ES module.
// Telegram's Android/iOS WebView may not support top-level await even when
// the user's Chrome browser does — they use different WebView engines.
async function main() {
  try {
    // retrieveLaunchParams() throws if there are no valid TG launch params
    // (e.g. app opened in a regular browser).
    const launchParams = retrieveLaunchParams();
    const { tgWebAppPlatform: platform } = launchParams;
    const debug = (launchParams.tgWebAppStartParam || '').includes('debug') || import.meta.env.DEV;

    // init() throws if the Telegram client is too old to support the SDK.
    // Both this and the retrieveLaunchParams() throw are caught below.
    await init({
      debug,
      eruda: debug && ['ios', 'android'].includes(platform),
      mockForMacOS: platform === 'macos',
    });

    // initData.restore() has been called inside init(), so initData.user() is now safe.
    // Resolve the initial locale from the Telegram client language immediately —
    // this ensures "Access Restricted" (and any other pre-API screens) are shown
    // in the correct language before the DB round-trip completes.
    let initialLocale: string = 'en';
    try {
      const tgLang = initData.user()?.language_code;
      initialLocale = resolveLocale(tgLang);
    } catch {
      // keep 'en'
    }

    const i18n = createI18n({
      legacy: false,
      locale: initialLocale,
      fallbackLocale: 'en',
      messages: { en, ru, de, es, fr, pl, pt, tr }
    });

    const app = createApp(App);
    app.config.errorHandler = errorHandler;

    const pinia = createPinia();
    app.use(pinia);
    app.use(router);
    app.use(i18n);

    app.mount('#app');
  } catch {
    // App opened outside Telegram or Telegram client is too old —
    // show a friendly "Oops" screen instead of a blank page.
    // Pattern mirrors the official React TMA template (EnvUnsupported).
    createApp(EnvUnsupported).mount('#app');
  }
}

main();


