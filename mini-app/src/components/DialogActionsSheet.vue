<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="sheet-backdrop" @click.self="$emit('close')">
        <div class="sheet">
          <div class="sheet-handle"></div>
          <button v-ripple class="sheet-item" @click="pinned ? $emit('unpin') : $emit('pin')">
            <img :src="keepSvg" alt="" draggable="false" />
            <span>{{ pinned ? $t('unpin') : $t('pin') }}</span>
          </button>
          <div class="sheet-divider"></div>
          <button v-ripple class="sheet-item" @click="$emit('rename')">
            <img :src="renameSvg" alt="" draggable="false" />
            <span>{{ $t('rename') }}</span>
          </button>
          <div class="sheet-divider"></div>
          <button v-ripple class="sheet-item sheet-item--danger" @click="$emit('delete')">
            <img :src="deleteSvg" alt="" draggable="false" />
            <span>{{ $t('delete_chat') }}</span>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import renameSvg from '@/components/img/rename.svg';
import deleteSvg from '@/components/img/delete.svg';
import keepSvg from '@/components/img/keep.svg';

defineProps<{ open: boolean; pinned: boolean }>();
defineEmits<{ close: []; rename: []; delete: []; pin: []; unpin: [] }>();
</script>

<style scoped>
.sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: var(--backgorund-color);
  border-radius: 18px 18px 0 0;
  padding-bottom: calc(env(safe-area-inset-bottom) + 10px);
  overflow: hidden;
}
.sheet-handle {
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--icons-storke-color);
  opacity: 0.4;
  margin: 10px auto 6px;
}
.sheet-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 58px;
  padding: 17px 20px;
  box-sizing: border-box;
  border: none;
  outline: none;
  font-size: 16px;
  color: var(--text-color);
  background: var(--second-bg-color);
  position: relative;
  overflow: hidden;
  -webkit-tap-highlight-color: transparent;
}
.sheet-item img {
  width: 22px;
  height: 22px;
  pointer-events: none;
  -webkit-user-drag: none;
}
.sheet-item:not(.sheet-item--danger) img {
  filter: brightness(0) saturate(100%) invert(60%);
}
.sheet-divider {
  height: 2px;
  background: var(--backgorund-color);
}
.sheet-item--danger {
  color: #fa2e52;
}
.sheet-item--danger img {
  filter: brightness(0) saturate(100%) invert(34%) sepia(82%) saturate(3000%) hue-rotate(331deg);
}
.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 200ms ease;
}
.sheet-enter-active .sheet,
.sheet-leave-active .sheet {
  transition: transform 240ms ease;
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .sheet,
.sheet-leave-to .sheet {
  transform: translateY(100%);
}
</style>
