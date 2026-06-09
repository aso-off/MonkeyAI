<template>
  <div id="root">
    <div class="wrapper">
      <div class="settingschange-wrapper">
        <div class="settingschange-container">
          <div class="settingschange-title">{{ t(titleKey) }}</div>

          <div class="legal-meta">
            <div class="legal-updated">{{ updated }}</div>
            <p class="legal-intro">{{ intro }}</p>
          </div>

          <div
            v-for="(s, i) in sections"
            :key="i"
            class="settingschange-select legal-section"
          >
            <div class="legal-section-heading">{{ s.heading }}</div>

            <p v-if="s.intro" class="legal-section-body">{{ s.intro }}</p>

            <ul v-if="s.items && s.items.length" class="legal-list">
              <li
                v-for="(it, j) in s.items"
                :key="j"
                class="legal-section-body legal-list-item"
              >
                <strong v-if="it.b">{{ it.b }}</strong>{{ it.t }}
              </li>
            </ul>

            <p v-if="s.body" class="legal-section-body">
              <template v-for="(seg, k) in splitSupport(s.body)" :key="k"
                ><span
                  v-if="seg.link"
                  class="legal-support-link"
                  @click="openSupport"
                  >{{ seg.text }}</span
                ><template v-else>{{ seg.text }}</template></template
              >
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { openTelegramLink } from '@tma.js/sdk-vue';
import { APP_LINKS, SUPPORT_HANDLE, LEGAL_LAST_UPDATED } from '@/config/app';

interface Item {
  b: string;
  t: string;
}
interface Section {
  heading: string;
  intro: string;
  body: string;
  items: Item[];
}
interface Seg {
  text: string;
  link: boolean;
}

const props = defineProps<{
  doc: 'privacy' | 'terms';
  titleKey: 'privacy_policy' | 'terms_of_service';
}>();

const { t, tm } = useI18n();

const updated = computed(() =>
  (tm('legal.updated' as never) as unknown as string).replace('{date}', LEGAL_LAST_UPDATED),
);
const intro = computed(
  () => tm(`legal.${props.doc}.intro` as never) as unknown as string,
);
const sections = computed(
  () => tm(`legal.${props.doc}.sections` as never) as unknown as Section[],
);

function openSupport() {
  openTelegramLink(APP_LINKS.support);
}

function splitSupport(text: string): Seg[] {
  if (!text) return [];
  const parts = text.split('{support}');
  const segs: Seg[] = [];
  parts.forEach((p, i) => {
    if (p) segs.push({ text: p, link: false });
    if (i < parts.length - 1) segs.push({ text: SUPPORT_HANDLE, link: true });
  });
  return segs;
}
</script>

<style scoped>
#root {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

#root::-webkit-scrollbar {
  display: none;
}

.wrapper {
  min-height: 100%;
  padding-bottom: 24px;
}

.legal-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 6px 14px;
}

.legal-updated {
  font-size: 13px;
  color: var(--icons-storke-color);
}

.legal-intro {
  font-size: 15px;
  line-height: 1.5;
  color: var(--icons-storke-color);
  margin: 0;
}

.legal-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px !important;
  margin-bottom: 12px;
}

.legal-section-heading {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-color);
}

.legal-section-body {
  font-size: 15px;
  font-weight: 400;
  color: var(--icons-storke-color);
  line-height: 1.5;
  margin: 0;
}

.legal-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legal-list-item {
  padding-left: 4px;
}

.legal-list-item strong {
  color: var(--text-color);
  font-weight: 600;
}

.legal-support-link {
  color: var(--tg-theme-link-color, #007aff);
  cursor: pointer;
}
</style>
