<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useBackButton } from '@/composables/useBackButton';
import { useTheme } from '@/composables/useTheme';
import { useUserStore } from '@/store/user';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { settingsButton } from '@tma.js/sdk-vue';
import AppLoading from '@/pages/AppLoading.vue';
import { wsClient } from '@/services/api';

useBackButton();
useTheme();

const router = useRouter();

onMounted(() => {
  settingsButton.show.ifAvailable();
  settingsButton.onClick.ifAvailable(() => {
    router.push('/settings');
  });
});

const store = useUserStore();
const { t } = useI18n();

const showLoading = ref(true);

// ── Visibility listener (set up once) ───────────────────────────────────────
let visibilityListenerAdded = false;

function setupVisibilityListener() {
  if (visibilityListenerAdded) return;
  visibilityListenerAdded = true;
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      // Foregrounded — re-establish WebSocket if it dropped while backgrounded.
      wsClient.connect().catch(() => {});
    }
  });
}

// ── Called by AppLoading when it finishes ────────────────────────────────────
function onLoadingDone() {
  showLoading.value = false;
  setupVisibilityListener();
  // Open WS early so it's ready before the user types the first message.
  wsClient.connect().catch(() => {});
}
</script>

<template>
  <!-- One-time loading screen (first render only, resets on full page reload). -->
  <Transition name="loading-fade">
    <AppLoading v-if="showLoading" @done="onLoadingDone" />
  </Transition>

  <template v-if="!showLoading">
    <!-- User loaded but not whitelisted -->
    <div v-if="store.user && !store.user.is_whitelisted" class="nw-screen">
      <div class="nw-card">
        <div class="nw-title">{{ t('not_whitelisted_title') }}</div>
      </div>
    </div>
    <!-- Normal flow (user must be loaded to prevent null-access in child routes) -->
    <!-- KeepAlive keeps MainPage alive during navigation so chat/generation state is preserved -->
    <RouterView v-else-if="store.user" v-slot="{ Component }">
      <KeepAlive include="MainPage,SettingsPage">
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </template>
</template>

<style scoped>
/* Loading screen fade-out — kept very short so it's imperceptible */
.loading-fade-leave-active {
  transition: opacity 80ms ease;
  pointer-events: none;
}
.loading-fade-leave-to {
  opacity: 0;
}

.nw-screen {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background-color: var(--backgorund-color);
}

.nw-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px 28px;
  border-radius: 20px;
  background-color: var(--second-bg-color);
  max-width: 300px;
  text-align: center;
}

.nw-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-color);
}

.nw-subtitle {
  font-size: 14px;
  color: var(--icons-storke-color);
  line-height: 1.4;
}
</style>