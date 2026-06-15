<template>
  <LegalDocument doc="terms" title-key="terms_of_service" />
</template>

<script setup lang="ts">
import LegalDocument from '@/components/LegalDocument.vue';

defineOptions({ name: 'SettingsTerms' });
</script>