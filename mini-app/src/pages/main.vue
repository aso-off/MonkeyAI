<template>
  <div id="root" class="swipe-y-off">
    <div class="swipe-y-on scroll-area" ref="rootEl" @scroll="onScroll">
      <div class="home">
        <!-- Шапка: аватар + имя → настройки (без фона) -->
        <div v-ripple class="home__header interactive" @click="router.push('/settings')">
          <div class="home__avatar">
            <div v-if="!avatarLoaded" class="home__avatar-skel"></div>
            <img v-if="photoUrl" :src="photoUrl" alt="" draggable="false" @load="avatarLoaded = true" />
          </div>
          <div class="home__name-row">
            <div class="home__name">{{ fullName }}</div>
            <img
              v-if="isPremium"
              class="home__premium"
              :src="premiumBadge"
              alt=""
              draggable="false"
            />
          </div>
        </div>

        <!-- Кнопка Изображения -->
        <div class="home__card">
          <div v-ripple class="home__row interactive" @click="router.push('/images')">
            <div class="home__row-iconbox" style="background-color: rgb(51, 144, 236)">
              <img :src="imageSvg" alt="" draggable="false" />
            </div>
            <span class="home__row-text">{{ $t('images') }}</span>
          </div>
        </div>

        <!-- Список: pinned + даты в одном TransitionGroup — FLIP, строки не пересоздаются -->
        <template v-if="dialogs.loading && dialogs.list.length === 0 && dialogs.pinned.length === 0">
          <div class="home__skel">
            <div v-for="n in skeletonCount" :key="n" class="rec-skeleton-row">
              <div class="rec-skeleton-line"></div>
              <div class="rec-skeleton-line rec-skeleton-line--sub"></div>
            </div>
          </div>
        </template>

        <div v-else-if="showEmpty" class="home__empty">
          {{ searchQuery.trim() ? $t('no_search_results') : $t('no_chats') }}
        </div>

        <TransitionGroup v-else name="rec" tag="div" class="home__flat">
          <div v-for="row in flatRows" :key="row.key" class="flat-item">
            <div v-if="row.kind === 'header'" class="home__section-title">{{ row.label }}</div>
            <div
              v-else
              v-ripple
              class="rec-row interactive"
              :class="{ 'round-top': row.roundTop, 'round-bottom': row.roundBottom }"
              @click="onRowClick(row.d.dialog_id)"
              @touchstart.passive="onPressStart(row.d.dialog_id)"
              @touchend="onPressEnd"
              @touchmove.passive="onPressEnd"
            >
              <div class="rec-main">
                <input
                  v-if="editingId === row.d.dialog_id"
                  v-model="editingTitle"
                  class="rec-edit"
                  enterkeyhint="done"
                  maxlength="40"
                  @click.stop
                  @keyup.enter="commitRename"
                  @blur="commitRename"
                />
                <div v-else class="rec-title">{{ row.d.title || $t('new_chat') }}</div>
                <div class="rec-date">{{ formatDate(row.d.last_activity) }}</div>
              </div>
              <span v-ripple class="rec-menu" @pointerdown.stop @click.stop="onMenu(row.d.dialog_id)">
                <img class="icon-muted" :src="editSvg" alt="" draggable="false" />
              </span>
            </div>
          </div>
        </TransitionGroup>

        <div class="home__bottom-spacer"></div>
      </div>
    </div>

    <!-- Нижняя панель (футер) -->
    <div class="home__bar">
      <div class="home__search">
        <img class="home__search-icon icon-muted" :src="searchSvg" alt="" draggable="false" />
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
      <div class="home__bar-actions" :class="{ collapsed: searchActive }">
        <span v-ripple class="home__bar-btn interactive" @click="router.push('/settings')">
          <img class="icon-muted" :src="settingsSvg" alt="" draggable="false" />
        </span>
        <span v-ripple class="home__bar-btn interactive" @click="newChat">
          <img class="icon-muted" :src="newChatSvg" alt="" draggable="false" />
        </span>
      </div>
    </div>

    <DialogActionsSheet
      :open="sheetId !== null"
      :pinned="sheetPinned"
      @close="sheetId = null"
      @rename="startRename"
      @pin="onPin"
      @unpin="onUnpin"
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
import { useI18n } from 'vue-i18n';
import { initData } from '@tma.js/sdk-vue';
import { useUserStore, IMAGE_MODELS } from '@/store/user';
import { useDialogsStore } from '@/store/dialogs';
import { wsClient, type DialogListItem } from '@/services/api';
import DialogActionsSheet from '@/components/DialogActionsSheet.vue';
import ConfirmModal from '@/components/ConfirmModal.vue';
import imageSvg from '@/components/img/Image.svg';
import searchSvg from '@/components/img/search.svg';
import settingsSvg from '@/components/img/settings.svg';
import newChatSvg from '@/components/img/new_chat.svg';
import editSvg from '@/components/img/editdialog.svg';
import premiumBadge from '@/components/img/premium_badge.svg';

defineOptions({ name: 'MainPage' });

const router = useRouter();
const store = useUserStore();
const dialogs = useDialogsStore();
const { t, locale } = useI18n();

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

const avatarLoaded = ref(false);

// скелетонов столько, чтобы заполнить экран
const skeletonCount = Math.min(
  20,
  Math.max(8, Math.ceil((typeof window !== 'undefined' ? window.innerHeight : 800) / 62)),
);

const photoUrl = computed<string | null>(() => {
  try {
    return initData.user()?.photo_url ?? null;
  } catch {
    return null;
  }
});

const isPremium = computed<boolean>(() => {
  try {
    return initData.user()?.is_premium ?? false;
  } catch {
    return false;
  }
});

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const lc = locale.value;
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString(lc, { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (diffDays < 7) {
    const wd = d.toLocaleDateString(lc, { weekday: 'long' });
    return wd.charAt(0).toUpperCase() + wd.slice(1);
  }
  return d.toLocaleDateString(lc, { month: 'short', day: '2-digit' });
}

// Один плоский список (заголовки + строки) — единый TransitionGroup, FLIP между секциями.
type FlatRow =
  | { kind: 'header'; key: string; label: string }
  | { kind: 'dialog'; key: string; d: DialogListItem; roundTop: boolean; roundBottom: boolean };

const flatRows = computed<FlatRow[]>(() => {
  const rows: FlatRow[] = [];
  const pushSection = (key: string, label: string, items: DialogListItem[]) => {
    if (!items.length) return;
    if (label) rows.push({ kind: 'header', key: `hdr-${key}`, label });
    items.forEach((d, i) =>
      rows.push({
        kind: 'dialog',
        key: d.dialog_id,
        d,
        roundTop: i === 0,
        roundBottom: i === items.length - 1,
      }),
    );
  };
  if (searchQuery.value.trim()) {
    pushSection('search', '', dialogs.searchResults);
    return rows;
  }
  pushSection('pinned', t('pinned_dialogs'), dialogs.pinned);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startYesterday = startToday - 86_400_000;
  const startWeek = startToday - 6 * 86_400_000;
  const buckets: Record<string, DialogListItem[]> = { today: [], yesterday: [], week: [], earlier: [] };
  for (const d of dialogs.list) {
    const ts = new Date(d.last_activity).getTime();
    if (ts >= startToday) buckets.today.push(d);
    else if (ts >= startYesterday) buckets.yesterday.push(d);
    else if (ts >= startWeek) buckets.week.push(d);
    else buckets.earlier.push(d);
  }
  pushSection('today', t('group_today'), buckets.today);
  pushSection('yesterday', t('group_yesterday'), buckets.yesterday);
  pushSection('week', t('group_week'), buckets.week);
  pushSection('earlier', t('group_earlier'), buckets.earlier);
  return rows;
});

const showEmpty = computed(() => {
  if (searchQuery.value.trim()) return !dialogs.searching && dialogs.searchResults.length === 0;
  return dialogs.list.length === 0 && dialogs.pinned.length === 0;
});

function openChat(id: string) {
  router.push({ name: 'chat', params: { dialogId: id } });
}

function newChat() {
  // новый чат — текстовый: сбрасываем залипшую image-модель (оптимистично, не блокируем)
  if ((IMAGE_MODELS as readonly string[]).includes(store.currentModel)) {
    store.setModel('gpt-5.4-nano').catch(() => {});
  }
  // черновик: диалог создастся в БД только с первым сообщением
  router.push({ name: 'chat', params: { dialogId: 'new' } });
}

/* === Action-sheet / rename / delete / pin === */
const sheetId = ref<string | null>(null);
const confirmId = ref<string | null>(null);
const editingId = ref<string | null>(null);
const editingTitle = ref('');
let pressTimer: ReturnType<typeof setTimeout> | null = null;

const sheetPinned = computed(
  () =>
    [...dialogs.pinned, ...dialogs.list, ...dialogs.searchResults].find(
      (x) => x.dialog_id === sheetId.value,
    )?.pinned ?? false,
);

function onPin() {
  const id = sheetId.value;
  sheetId.value = null;
  if (id) dialogs.pin(id).catch((e) => console.error('[pin]', e));
}

function onUnpin() {
  const id = sheetId.value;
  sheetId.value = null;
  if (id) dialogs.unpin(id).catch((e) => console.error('[unpin]', e));
}

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
  // безымянный чат — подставляем отображаемое имя (и выделяем), чтобы не начинать с 0
  const d = [...dialogs.pinned, ...dialogs.list, ...dialogs.searchResults].find(
    (x) => x.dialog_id === id,
  );
  editingTitle.value = d?.title || t('new_chat');
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
  // sheet остаётся открытым под confirm
  confirmId.value = sheetId.value;
}

async function confirmDelete() {
  const id = confirmId.value;
  confirmId.value = null;
  sheetId.value = null;
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
  // подгружаем старые только когда не идёт активный поиск (пустой фокус — можно)
  if (!el || searchQuery.value.trim()) return;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 300) {
    dialogs.loadMore().catch(() => {});
  }
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer);
  const q = searchQuery.value.trim();
  if (!q) {
    dialogs.clearSearch();
    return;
  }
  dialogs.markSearching();
  // "Новый чат" / "New Chat" ищем и среди безымянных диалогов (title IS NULL)
  const includeUntitled = t('new_chat').toLowerCase().includes(q.toLowerCase());
  searchTimer = setTimeout(() => {
    dialogs.runSearch(q, includeUntitled).catch((e) => console.error('[search]', e));
  }, 300);
}

function onSearchBlur() {
  if (!searchQuery.value.trim()) {
    searchActive.value = false;
    dialogs.clearSearch();
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
  overscroll-behavior-y: contain;
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
  padding: env(safe-area-inset-top) 14px 0;
}

/* Шапка — без фона */
.home__header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 8px;
  border-radius: 14px;
  margin-top: 10px;
  overflow: hidden;
}
.home__avatar {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  flex-shrink: 0;
  overflow: hidden;
  background-color: var(--third-bg-color);
}
.home__avatar img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-user-drag: none;
  -webkit-touch-callout: none;
}
.home__avatar-skel {
  position: absolute;
  inset: 0;
  background: #6b6f7438;
}
@keyframes avatar-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.home__name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.home__name {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
}
.home__premium {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  pointer-events: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-user-drag: none;
  -webkit-touch-callout: none;
}

/* Карточка-контейнер как в настройках */
.home__card {
  width: 100%;
  border-radius: 16px;
  background-color: var(--second-bg-color);
  overflow: hidden;
}
.home__row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 54px;
  padding: 12px 16px;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}
.home__row-iconbox {
  width: 30px;
  height: 30px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.home__row-iconbox img {
  width: 22px;
  height: 22px;
  filter: brightness(0) saturate(100%) invert(100%);
  pointer-events: none;
  user-select: none;
  -webkit-user-drag: none;
}
.home__row-text {
  font-size: 16px;
  color: var(--text-color);
}

.home__section-title {
  font-size: 13px;
  color: var(--icons-storke-color);
  text-transform: uppercase;
  padding: 18px 16px 10px;
}

.home__flat {
  position: relative;
  display: flex;
  flex-direction: column;
}
.flat-item {
  width: 100%;
}
.flat-item:first-child .home__section-title {
  padding-top: 8px;
}
.rec-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 60px;
  padding: 10px 16px;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  background: var(--second-bg-color);
  border-radius: 0;
  transition: border-radius 180ms ease;
}
/* разделитель — зазор с фоном страницы, без border (давал шов) */
.rec-row:not(.round-top) {
  margin-top: 2px;
}
.rec-row.round-top {
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
}
.rec-row.round-bottom {
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
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
.rec-date {
  font-size: 13px;
  color: var(--icons-storke-color);
  margin-top: 3px;
}
.rec-edit {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-color);
  font-size: 16px;
  padding: 0;
}
.rec-menu {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
  background: transparent;
}
.rec-menu img {
  width: 20px;
  height: 20px;
}

.home__skel {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rec-skeleton-row {
  min-height: 60px;
  padding: 12px 16px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 9px;
  background: var(--second-bg-color);
}
.rec-skeleton-row:first-child {
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
}
.rec-skeleton-row:last-child {
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
}
.rec-skeleton-line {
  height: 15px;
  width: 55%;
  border-radius: 6px;
  background: linear-gradient(100deg, #6b6f7430 30%, #6b6f7460 50%, #6b6f7430 70%);
  background-size: 200% 100%;
  animation: avatar-shimmer 1.2s ease-in-out infinite;
}
.rec-skeleton-line--sub {
  width: 32%;
  height: 12px;
}
/* FLIP: соседи плавно съезжают, уходящая строка — под ними (absolute + z-index -1) */
.rec-move {
  transition: transform 220ms ease;
}
.rec-enter-active {
  transition: opacity 180ms ease;
}
.rec-leave-active {
  position: absolute;
  left: 0;
  right: 0;
  z-index: -1;
  transition: opacity 150ms ease;
}
.rec-enter-from,
.rec-leave-to {
  opacity: 0;
}

.home__empty {
  text-align: center;
  color: var(--icons-storke-color);
  padding: 32px 0;
}
.home__bottom-spacer {
  height: 90px;
}

/* Иконки: единый #999999 (invert 60% от чёрного), кросс-тема */
.icon-muted {
  filter: brightness(0) saturate(100%) invert(60%);
  pointer-events: none;
  user-select: none;
  -webkit-user-drag: none;
}
/* Images — полный контраст, как иконка модели в выборе */
.icon-strong {
  filter: none;
  pointer-events: none;
  user-select: none;
  -webkit-user-drag: none;
}
body.dark .icon-strong {
  filter: brightness(0) saturate(100%) invert(100%);
}

/* Футер */
.home__bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px calc(env(safe-area-inset-bottom) + 12px);
  box-sizing: border-box;
  background: var(--backgorund-color);
}
.home__search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  height: 48px;
  padding: 0 14px;
  box-sizing: border-box;
  border-radius: 24px;
  background-color: var(--third-bg-color);
}
.home__search-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
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
.home__bar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 106px;
  opacity: 1;
  overflow: hidden;
  transition: max-width 260ms ease, opacity 200ms ease, transform 260ms ease;
}
.home__bar-actions.collapsed {
  max-width: 0;
  opacity: 0;
  transform: translateX(24px);
  pointer-events: none;
}
.home__bar-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background-color: var(--third-bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}
.home__bar-btn img {
  width: 22px;
  height: 22px;
}
</style>
