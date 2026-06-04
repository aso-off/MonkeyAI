import { backButton } from '@tma.js/sdk-vue';
import { watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

/** Map each route to its explicit parent — works correctly even after a hard reload. */
const PARENT_ROUTE: Record<string, string> = {
  settings: 'index',
  language: 'settings',
  theme: 'settings',
  privacy: 'settings',
  terms: 'settings',
};

export function useBackButton() {
  let offClick: () => void = () => {};
  const route = useRoute();
  const router = useRouter();

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
    const parent = PARENT_ROUTE[route.name as string];
    if (parent) {
      await router.push({ name: parent });
    } else {
      await router.push({ name: 'index' });
    }
  }
}
