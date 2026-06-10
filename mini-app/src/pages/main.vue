<template>
  <div id="root" class="swipe-y-off">
    <div class="swipe-y-on scroll-area" ref="rootEl" @scroll="onScroll">
      <div class="home">
        <!-- Шапка: аватар + имя → настройки -->
        <div v-ripple class="home__header interactive" @click="router.push('/settings')">
          <div class="home__avatar">{{ initial }}</div>
          <div class="home__name">{{ fullName }}</div>
        </div>

        <!-- Кнопка Изображения -->
        <div v-ripple class="home__images interactive" @click="router.push('/images')">
          <img class="home__images-icon" :src="imageSvg" alt="" draggable="false" />
          <span class="home__images-text">{{ $t('images') }}</span>
        </div>

        <!-- Recents -->
        <div class="home__section-title">{{ $t('recents') }}</div>

        <template v-if="dialogs.loading && dialogs.list.length === 0">
          <div v-for="n in 6" :key="n" class="rec-skeleton"></div>
        </template>

        <div v-else-if="dialogs.list.length === 0" class="home__empty">{{ $t('no_chats') }}</div>

        <TransitionGroup v-else name="rec" tag="div" class="home__list">
          <div
            v-for="d in dialogs.list"
            :key="d.dialog_id"
            v-ripple
            class="rec-row interactive"
            @click="onRowClick(d.dialog_id)"
            @touchstart.passive="onPressStart(d.dialog_id)"
            @touchend="onPressEnd"
            @touchmove.passive="onPressEnd"
          >
            <div class="rec-main">
              <input
                v-if="editingId === d.dialog_id"
                v-model="editingTitle"
                class="rec-edit"
                enterkeyhint="done"
                maxlength="40"
                @click.stop
                @keyup.enter="commitRename"
                @blur="commitRename"
              />
              <div v-else class="rec-title">{{ d.title || $t('new_chat') }}</div>
              <div class="rec-date">{{ formatDate(d.start_time) }}</div>
            </div>
            <button v-ripple class="rec-menu" @click.stop="onMenu(d.dialog_id)">
              <img :src="editSvg" alt="" draggable="false" />
            </button>
          </div>
        </TransitionGroup>

        <div class="home__bottom-spacer"></div>
      </div>
    </div>

    <!-- Нижняя панель -->
    <div class="home__bar">
      <div class="home__search" :class="{ active: searchActive }">
        <img class="home__search-icon" :src="searchSvg" alt="" draggable="false" />
        <input
          ref="searchInput"
          v-model="searchQuery"
          class="home__search-input"
          :placeholder="$t('search')"
          @focus="searchActive = true"
          @blur="onSearchBlur"
          @input="onSearchInput"
        />
      </div>
      <button v-ripple class="home__bar-btn" :class="{ hidden: searchActive }" @click="router.push('/settings')">
        <img :src="settingsSvg" alt="" draggable="false" />
      </button>
      <button v-ripple class="home__bar-btn" :class="{ hidden: searchActive }" @click="newChat">
        <img :src="newChatSvg" alt="" draggable="false" />
      </button>
    </div>

    <DialogActionsSheet
      :open="sheetId !== null"
      @close="sheetId = null"
      @rename="startRename"
      @delete="startDelete"
    />
    <ConfirmModal
      :open="confirmId !== null"
      :title="$t('delete_dialog')"
      :text="$t('delete_dialog_confirm')"
      :confirm-text="$t('delete')"
      @cancel="confirmId = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/store/user';
import { useDialogsStore } from '@/store/dialogs';
import { api, wsClient } from '@/services/api';
import DialogActionsSheet from '@/components/DialogActionsSheet.vue';
import ConfirmModal from '@/components/ConfirmModal.vue';
import imageSvg from '@/components/img/Image.svg';
import searchSvg from '@/components/img/search.svg';
import settingsSvg from '@/components/img/settings.svg';
import newChatSvg from '@/components/img/new_chat.svg';
import editSvg from '@/components/img/editdialog.svg';

defineOptions({ name: 'MainPage' });

const router = useRouter();
const store = useUserStore();
const dialogs = useDialogsStore();

const rootEl = ref<HTMLElement | null>(null);
const searchInput = ref<HTMLInputElement | null>(null);
const searchActive = ref(false);
const searchQuery = ref('');
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const fullName = computed(() => {
  const u = store.user;
  if (!u) return '';
  return [u.first_name, u.last_name].filter(Boolean).join(' ');
});

const initial = computed(() => (store.user?.first_name?.[0] ?? '?').toUpperCase());

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (diffDays < 7) return d.toLocaleDateString(undefined, { weekday: 'long' });
  return d.toLocaleDateString();
}

function openChat(id: string) {
  router.push({ name: 'chat', params: { dialogId: id } });
}

async function newChat() {
  try {
    const { dialog_id } = await api.newDialog();
    router.push({ name: 'chat', params: { dialogId: dialog_id } });
  } catch (e) {
    console.error('[newChat]', e);
  }
}

/* === Action-sheet / rename / delete === */
const sheetId = ref<string | null>(null);
const confirmId = ref<string | null>(null);
const editingId = ref<string | null>(null);
const editingTitle = ref('');
let pressTimer: ReturnType<typeof setTimeout> | null = null;

function onRowClick(id: string) {
  if (editingId.value) return;
  openChat(id);
}

function onMenu(id: string) {
  sheetId.value = id;
}

function onPressStart(id: string) {
  if (pressTimer) clearTimeout(pressTimer);
  pressTimer = setTimeout(() => {
    sheetId.value = id;
  }, 450);
}

function onPressEnd() {
  if (pressTimer) {
    clearTimeout(pressTimer);
    pressTimer = null;
  }
}

function startRename() {
  const id = sheetId.value;
  sheetId.value = null;
  editingId.value = id;
  editingTitle.value = dialogs.list.find((x) => x.dialog_id === id)?.title ?? '';
  nextTick(() => {
    const el = document.querySelector('.rec-edit') as HTMLInputElement | null;
    el?.focus();
    el?.select();
  });
}

async function commitRename() {
  const id = editingId.value;
  editingId.value = null;
  const title = editingTitle.value.trim();
  if (id && title) {
    try {
      await dialogs.rename(id, title);
    } catch (e) {
      console.error('[rename]', e);
    }
  }
}

function startDelete() {
  confirmId.value = sheetId.value;
  sheetId.value = null;
}

async function confirmDelete() {
  const id = confirmId.value;
  confirmId.value = null;
  if (id) {
    try {
      await dialogs.remove(id);
    } catch (e) {
      console.error('[delete]', e);
    }
  }
}

function onScroll() {
  const el = rootEl.value;
  if (!el || searchActive.value) return;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 300) {
    dialogs.loadMore().catch(() => {});
  }
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer);
  const q = searchQuery.value.trim();
  if (!q) {
    dialogs.loadInitial(true).catch(() => {});
    return;
  }
  searchTimer = setTimeout(async () => {
    try {
      const r = await api.searchDialogs(q);
      dialogs.list = r.dialogs;
      dialogs.hasMore = false;
    } catch (e) {
      console.error('[search]', e);
    }
  }, 300);
}

function onSearchBlur() {
  if (!searchQuery.value.trim()) {
    searchActive.value = false;
    dialogs.loadInitial(true).catch(() => {});
  }
}

onMounted(() => {
  dialogs.loadInitial().catch(() => {});
  // Живое обновление заголовка из фоновой nano-генерации
  wsClient.setTypeHandler('dialog_title', (msg) => {
    const id = msg.dialog_id as string;
    const title = msg.title as string;
    if (id && title) dialogs.applyTitle(id, title);
  });
});
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

.home {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: env(safe-area-inset-top) 16px 0;
}

.home__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 16px;
  background-color: var(--second-bg-color);
  margin-top: 12px;
}
.home__avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background-color: #2e7d6b;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 600;
  flex-shrink: 0;
}
.home__name {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
}

.home__images {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background-color: var(--second-bg-color);
}
.home__images-icon {
  width: 22px;
  height: 22px;
}
.home__images-text {
  font-size: 16px;
  color: var(--text-color);
}

.home__section-title {
  font-size: 14px;
  color: var(--icons-storke-color);
  padding: 8px 4px 2px;
}

.home__list {
  display: flex;
  flex-direction: column;
}
.rec-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 8px;
  border-radius: 12px;
}
.rec-main {
  flex: 1;
  min-width: 0;
}
.rec-title {
  font-size: 16px;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rec-edit {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-color);
  font-size: 16px;
  border-bottom: 1px solid var(--icons-storke-color);
  padding: 0 0 2px;
}
.rec-date {
  font-size: 13px;
  color: var(--icons-storke-color);
  margin-top: 2px;
}
.rec-menu {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.rec-menu img {
  width: 20px;
  height: 20px;
}

.rec-skeleton {
  height: 44px;
  border-radius: 12px;
  background-color: #6b6f7438;
  margin: 6px 0;
}
.rec-enter-active,
.rec-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}
.rec-enter-from,
.rec-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

.home__empty {
  text-align: center;
  color: var(--icons-storke-color);
  padding: 32px 0;
}
.home__bottom-spacer {
  height: 80px;
}

img[src$='.svg'] {
  filter: brightness(0) saturate(100%) invert(100%);
  pointer-events: none;
  user-select: none;
}

.home__bar {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: calc(env(safe-area-inset-bottom) + 10px);
  display: flex;
  align-items: center;
  gap: 10px;
}
.home__search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 2;
  height: 48px;
  padding: 0 14px;
  border-radius: 24px;
  background-color: var(--second-bg-color);
  transition: flex 250ms ease;
}
.home__search.active {
  flex: 100;
}
.home__search-icon {
  width: 20px;
  height: 20px;
}
.home__search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-color);
  font-size: 16px;
}
.home__bar-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background-color: var(--second-bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 250ms ease, opacity 200ms ease, width 250ms ease, margin 250ms ease;
}
.home__bar-btn img {
  width: 22px;
  height: 22px;
}
.home__bar-btn.hidden {
  transform: translateX(80px);
  opacity: 0;
  width: 0;
  margin-left: -10px;
  pointer-events: none;
}
</style>
