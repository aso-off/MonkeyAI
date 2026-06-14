/**
 * useTheme — управление темой приложения.
 *
 * Поддерживает три режима:
 *   'system'  — следует теме Telegram (определяется по bg_color из themeParams)
 *   'light'   — всегда светлая
 *   'dark'    — всегда тёмная
 *
 * Тема хранится в БД (users.theme). При входе читается из store.user.theme.
 * При изменении в настройках — store.setTheme() → PATCH /webapp/me.
 * localStorage НЕ используется.
 */

import { watch, onUnmounted } from 'vue'
import { themeParams } from '@tma.js/sdk-vue'
import { useUserStore } from '@/store/user'

export type ThemeOverride = 'system' | 'light' | 'dark'

let themeAnimTimer: ReturnType<typeof setTimeout> | null = null

function applyClass(scheme: 'light' | 'dark', animate = false): void {
  const isDark = scheme === 'dark'
  if (animate) {
    const root = document.documentElement
    root.classList.add('theme-anim')
    if (themeAnimTimer) clearTimeout(themeAnimTimer)
    themeAnimTimer = setTimeout(() => root.classList.remove('theme-anim'), 280)
  }
  document.body.classList.toggle('dark', isDark)
  // Mirror onto <html> so the root element gets a solid themed background (see :root.dark
  // in index.css). Prevents the native-background flash during Telegram resume/expand.
  document.documentElement.classList.toggle('dark', isDark)
  // Keep the browser/OS chrome colour in sync with the theme so the resume/expand
  // transition doesn't flash a fixed black bar on the light theme.
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', isDark ? '#1C1C1C' : '#F2F2F7')
}

/**
 * Определяет тему по bg_color из Telegram themeParams (luminance < 0.5 = dark).
 * Fallback: prefers-color-scheme media query.
 */
function getTgScheme(): 'light' | 'dark' {
  try {
    const state = themeParams.state()
    const hex = state?.bgColor ?? (state as Record<string, string>)?.bg_color
    if (hex) {
      const clean = hex.replace('#', '')
      const r = parseInt(clean.slice(0, 2), 16)
      const g = parseInt(clean.slice(2, 4), 16)
      const b = parseInt(clean.slice(4, 6), 16)
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
      return luminance < 0.5 ? 'dark' : 'light'
    }
  } catch {
    // themeParams not mounted yet (e.g. on desktop dev)
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function resolveScheme(override: ThemeOverride): 'light' | 'dark' {
  return override === 'system' ? getTgScheme() : override
}

/**
 * Call once in App.vue (setup).
 * Applies theme from store (DB) immediately.
 * Watches store.currentTheme to react to changes from settings page.
 * Subscribes to the SDK's isDark signal to react to system theme changes in real time.
 */
export function useTheme() {
  const store = useUserStore()

  // Apply immediately from whatever is in store (DB value after init, 'system' before)
  applyClass(resolveScheme(store.currentTheme as ThemeOverride))

  // React to Telegram theme change in real time via SDK signal (only matters when override is 'system').
  // themeParams.isDark is a @telegram-apps/signals Signal — call .sub() to subscribe.
  const onSdkThemeChanged = () => {
    if ((store.currentTheme as ThemeOverride) === 'system') {
      // isDark() reads the current value from the signal
      const dark = (themeParams.isDark as unknown as () => boolean | undefined)()
      if (dark !== undefined) {
        applyClass(dark ? 'dark' : 'light', true)
      } else {
        applyClass(getTgScheme(), true)
      }
    }
  }

  const isDarkSignal = themeParams.isDark as unknown as {
    sub: (cb: () => void) => void
    unsub: (cb: () => void) => void
  }
  isDarkSignal.sub(onSdkThemeChanged)

  onUnmounted(() => {
    isDarkSignal.unsub(onSdkThemeChanged)
  })

  // React to changes (settings page calls store.setTheme())
  watch(() => store.currentTheme, (t) => {
    applyClass(resolveScheme(t as ThemeOverride), true)
  })

  function setThemeOverride(override: ThemeOverride): void {
    store.setTheme(override)
  }

  function currentOverride(): ThemeOverride {
    return store.currentTheme as ThemeOverride
  }

  return { setThemeOverride, currentOverride }
}
