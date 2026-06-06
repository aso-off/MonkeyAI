import type { Directive } from 'vue'

// задержка — чтобы не было волны при скролле
const RIPPLE_DELAY = 70

interface RippleEl extends HTMLElement {
  _rippleWrapper?: HTMLSpanElement
  _rippleDown?: (e: PointerEvent) => void
  _rippleCancel?: (e: PointerEvent) => void
  _rippleTimers?: Map<number, ReturnType<typeof setTimeout>>
}

function spawnWave(wrapper: HTMLSpanElement, x: number, y: number, radius: number): void {
  const wave = document.createElement('span')
  wave.className = 'tg-ripple__wave'
  const size = radius * 2
  wave.style.width = `${size}px`
  wave.style.height = `${size}px`
  wave.style.left = `${x - radius}px`
  wave.style.top = `${y - radius}px`
  wave.addEventListener('animationend', () => wave.remove())
  wrapper.appendChild(wave)
}

export const ripple: Directive<RippleEl> = {
  mounted(el) {
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative'

    const wrapper = document.createElement('span')
    wrapper.className = 'tg-ripple'
    wrapper.setAttribute('aria-hidden', 'true')
    el.appendChild(wrapper)

    const timers = new Map<number, ReturnType<typeof setTimeout>>()

    const onDown = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const radius = Math.max(
        Math.hypot(x, y),
        Math.hypot(rect.width - x, y),
        Math.hypot(x, rect.height - y),
        Math.hypot(rect.width - x, rect.height - y),
      )
      timers.set(
        e.pointerId,
        setTimeout(() => {
          spawnWave(wrapper, x, y, radius)
          timers.delete(e.pointerId)
        }, RIPPLE_DELAY),
      )
    }

    const onCancel = (e: PointerEvent) => {
      const t = timers.get(e.pointerId)
      if (t) {
        clearTimeout(t)
        timers.delete(e.pointerId)
      }
    }

    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointercancel', onCancel)

    el._rippleWrapper = wrapper
    el._rippleDown = onDown
    el._rippleCancel = onCancel
    el._rippleTimers = timers
  },

  unmounted(el) {
    if (el._rippleDown) el.removeEventListener('pointerdown', el._rippleDown)
    if (el._rippleCancel) el.removeEventListener('pointercancel', el._rippleCancel)
    el._rippleTimers?.forEach((t) => clearTimeout(t))
    el._rippleWrapper?.remove()
  },
}
