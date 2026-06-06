import type { Directive } from 'vue'

// задержка — чтобы не было волны при скролле
const RIPPLE_DELAY = 70

interface RippleEl extends HTMLElement {
  _rippleWrapper?: HTMLSpanElement
  _rippleDown?: (e: PointerEvent) => void
  _rippleCancel?: (e: PointerEvent) => void
  _rippleTimers?: Map<number, ReturnType<typeof setTimeout>>
}

function spawnWave(wrapper: HTMLSpanElement, x: number, y: number): void {
  const wave = document.createElement('span')
  wave.className = 'tg-ripple__wave'
  wave.style.left = `${x}px`
  wave.style.top = `${y}px`
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
      const { left, top } = el.getBoundingClientRect()
      const x = e.clientX - left
      const y = e.clientY - top
      timers.set(
        e.pointerId,
        setTimeout(() => {
          spawnWave(wrapper, x, y)
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
