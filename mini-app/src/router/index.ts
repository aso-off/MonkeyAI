import { createRouter, createWebHistory } from 'vue-router'
import Main from '../pages/main.vue'

const routes = [
  {
    path: '/',
    name: 'index',
    component: Main
  },
  {
    path: '/chat/:dialogId?',
    name: 'chat',
    component: () => import('@/pages/chat.vue')
  },
  {
    path: '/images',
    name: 'images',
    component: () => import('@/pages/images.vue')
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/pages/settings.vue')
  },
  {
    path: '/settings/language',
    name: 'language',
    component: () => import('@/pages/settings_lang.vue')
  },
  {
    path: '/settings/theme',
    name: 'theme',
    component: () => import('@/pages/settings_theme.vue')
  },
  {
    path: '/settings/privacy',
    name: 'privacy',
    component: () => import('@/pages/settings_privacy.vue')
  },
  {
    path: '/settings/terms',
    name: 'terms',
    component: () => import('@/pages/settings_terms.vue')
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
