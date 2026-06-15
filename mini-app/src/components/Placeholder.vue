<script setup lang="ts">
defineProps<{
  header: string
  description: string
}>()
</script>

<template>
  <div class="placeholder">
    <div v-if="$slots.default" class="placeholder__media">
      <slot />
    </div>
    <p class="placeholder__header">{{ header }}</p>
    <p class="placeholder__description">{{ description }}</p>
  </div>
</template>

<style scoped>
.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 32px 40px;
  max-width: 360px;
  text-align: center;
  gap: 0;
}

.placeholder__media {
  display: contents;
}

:slotted(img) {
  display: block;
  width: 144px;
  height: 144px;
  border-radius: 28px;
}

.placeholder__header {
  margin: 24px 0 8px;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.placeholder__description {
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
  opacity: 0.55;
}
</style>