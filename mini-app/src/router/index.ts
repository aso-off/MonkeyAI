import { createRouter, createWebHistory } from 'vue-router'
import Main from '../pages/main.vue'
import Chat from '@/pages/chat.vue'
import Images from '@/pages/images.vue'
import Settings from '@/pages/settings.vue'
import SettingsTheme from '@/pages/settings_theme.vue'
import SettingsLang from '@/pages/settings_lang.vue'
import SettingsPrivacy from '@/pages/settings_privacy.vue'
import SettingsTerms from '@/pages/settings_terms.vue'

const routes = [
  {
    path: '/',
    name: 'index',
    component: Main
  },
  {
    path: '/chat/:dialogId?',
    name: 'chat',
    component: Chat
  },
  {
    path: '/images',
    name: 'images',
    component: Images
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
  },
  {
    path: '/settings/privacy',
    name: 'privacy',
    component: SettingsPrivacy
  },
  {
    path: '/settings/terms',
    name: 'terms',
    component: SettingsTerms
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router