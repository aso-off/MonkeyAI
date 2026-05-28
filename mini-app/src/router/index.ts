import { createRouter, createWebHistory } from 'vue-router'
import Main from '../pages/main.vue'
import Settings from '@/pages/settings.vue'
import SettingsTheme from '@/pages/settings_theme.vue'
import SettingsLang from '@/pages/settings_lang.vue'

const routes = [
  {
    path: '/',
    name: 'index',
    component: Main
  },
  {
    path: '/settings',
    name: 'settings',
    component: Settings
  },
  {
    path: '/settings/language',
    name: 'language',
    component: SettingsLang
  },
  {
    path: '/settings/theme',
    name: 'theme',
    component: SettingsTheme
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
