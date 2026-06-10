<template>
  <Teleport to="body">
    <Transition name="cm-fade">
      <div v-if="open" class="cm-backdrop" @click.self="$emit('cancel')">
        <div class="cm-card">
          <div class="cm-head">
            <div class="cm-title">{{ title }}</div>
            <div class="cm-text">{{ text }}</div>
          </div>
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
  z-index: 1001;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}
.cm-card {
  width: 100%;
  max-width: 300px;
  border-radius: 16px;
  background: var(--second-bg-color);
  overflow: hidden;
}
.cm-head {
  padding: 20px 20px 16px;
  text-align: center;
}
.cm-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 6px;
}
.cm-text {
  font-size: 14px;
  color: var(--icons-storke-color);
  line-height: 1.4;
}
.cm-actions {
  display: flex;
  border-top: 2px solid var(--backgorund-color);
}
.cm-btn {
  flex: 1;
  padding: 14px 8px;
  border: none;
  outline: none;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-color);
  background: transparent;
  position: relative;
  overflow: hidden;
  -webkit-tap-highlight-color: transparent;
}
.cm-btn + .cm-btn {
  border-left: 2px solid var(--backgorund-color);
}
.cm-btn--danger {
  color: #fa2e52;
  font-weight: 600;
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
