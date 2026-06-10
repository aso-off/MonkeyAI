<template>
  <Teleport to="body">
    <Transition name="cm-fade">
      <div v-if="open" class="cm-backdrop" @click.self="$emit('cancel')">
        <div class="cm-card">
          <div class="cm-title">{{ title }}</div>
          <div class="cm-text">{{ text }}</div>
          <div class="cm-actions">
            <button v-ripple class="cm-btn" @click="$emit('cancel')">{{ $t('cancel') }}</button>
            <button v-ripple class="cm-btn cm-btn--danger" @click="$emit('confirm')">{{ confirmText }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{ open: boolean; title: string; text: string; confirmText: string }>();
defineEmits<{ cancel: []; confirm: [] }>();
</script>

<style scoped>
.cm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.cm-card {
  width: 100%;
  max-width: 320px;
  border-radius: 18px;
  background: var(--second-bg-color);
  padding: 22px 20px 14px;
}
.cm-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 8px;
}
.cm-text {
  font-size: 15px;
  color: var(--icons-storke-color);
  line-height: 1.4;
  margin-bottom: 18px;
}
.cm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.cm-btn {
  padding: 10px 16px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-color);
  background: transparent;
}
.cm-btn--danger {
  color: #fa2e52;
}
.cm-fade-enter-active,
.cm-fade-leave-active {
  transition: opacity 180ms ease;
}
.cm-fade-enter-from,
.cm-fade-leave-to {
  opacity: 0;
}
</style>
