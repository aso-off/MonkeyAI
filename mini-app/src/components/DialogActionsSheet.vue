<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="sheet-backdrop" @click.self="$emit('close')">
        <div class="sheet">
          <div class="sheet-handle"></div>
          <div class="sheet-group">
            <button v-ripple class="sheet-item" @click="$emit('rename')">
              <img :src="renameSvg" alt="" draggable="false" />
              <span>{{ $t('rename') }}</span>
            </button>
            <div class="sheet-divider"></div>
            <button v-ripple class="sheet-item sheet-item--danger" @click="$emit('delete')">
              <img :src="deleteSvg" alt="" draggable="false" />
              <span>{{ $t('delete_dialog') }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import renameSvg from '@/components/img/rename.svg';
import deleteSvg from '@/components/img/delete.svg';

defineProps<{ open: boolean }>();
defineEmits<{ close: []; rename: []; delete: [] }>();
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
  padding: 8px 12px calc(env(safe-area-inset-bottom) + 20px);
}
.sheet-handle {
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--icons-storke-color);
  opacity: 0.4;
  margin: 4px auto 14px;
}
.sheet-group {
  width: 100%;
  border-radius: 16px;
  background: var(--second-bg-color);
  overflow: hidden;
}
.sheet-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 58px;
  padding: 16px 18px;
  box-sizing: border-box;
  border: none;
  outline: none;
  font-size: 16px;
  color: var(--text-color);
  background: transparent;
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
