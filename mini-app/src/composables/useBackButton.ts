import { backButton } from '@tma.js/sdk-vue';
import { watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

/** Map each route to its explicit parent — works correctly even after a hard reload. */
const PARENT_ROUTE: Record<string, string> = {
  chat: 'index',
  images: 'index',
  settings: 'index',
  language: 'settings',
  theme: 'settings',
  privacy: 'settings',
  terms: 'settings',
};

/** Поддерево настроек — заходы изнутри него не перетирают origin. */
const SETTINGS_SUBTREE = new Set(['settings', 'language', 'theme', 'privacy', 'terms']);

/** Полный путь, откуда вошли в настройки — чтобы «назад» вернул в тот же чат (с dialogId), а не в меню. */
let settingsOrigin: string | null = null;
let guardRegistered = false;

export function useBackButton() {
  let offClick: () => void = () => {};
  const route = useRoute();
  const router = useRouter();

  if (!guardRegistered) {
    guardRegistered = true;
    router.beforeEach((to, from) => {
      if (
        to.name === 'settings' &&
        from.name &&
        !SETTINGS_SUBTREE.has(from.name as string)
      ) {
        settingsOrigin = from.fullPath;
      }
    });
  }

  watch(() => route.name, () => {
    if (route.name === 'index') {
      backButton.hide();
      offClick();
    } else {
      if (!backButton.isVisible()) {
        backButton.show();
      }
      offClick();
      offClick = backButton.onClick(onBackButtonClick);
    }
  }, { immediate: true });

  async function onBackButtonClick(): Promise<void> {
    // из настроек — возвращаемся туда, откуда вошли (чат с dialogId или меню)
    if (route.name === 'settings' && settingsOrigin) {
      const target = settingsOrigin;
      settingsOrigin = null;
      await router.push(target);
      return;
    }
    const parent = PARENT_ROUTE[route.name as string];
    await router.push({ name: parent ?? 'index' });
  }
}