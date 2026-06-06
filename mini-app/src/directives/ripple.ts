import type { Directive } from 'vue'

const WAVE_BASE = 20

interface RippleEl extends HTMLElement {
  _rippleWrapper?: HTMLSpanElement
  _rippleDown?: (e: PointerEvent) => void
}

function spawnWave(wrapper: HTMLSpanElement, x: number, y: number, radius: number): void {
  const wave = document.createElement('span')
  wave.className = 'tg-ripple__wave'
  wave.style.left = `${x - WAVE_BASE / 2}px`
  wave.style.top = `${y - WAVE_BASE / 2}px`
  wrapper.appendChild(wave)

  const scale = (radius * 2) / WAVE_BASE
  const anim = wave.animate(
    [
      { transform: 'scale(0)', opacity: 1, offset: 0 },
      { opacity: 1, offset: 0.7 },
      { transform: `scale(${scale})`, opacity: 0, offset: 1 },
    ],
    { duration: 550, easing: 'ease-out', fill: 'forwards' },
  )
  anim.onfinish = () => wave.remove()
  anim.oncancel = () => wave.remove()
}

export const ripple: Directive<RippleEl> = {
  mounted(el) {
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative'

    const wrapper = document.createElement('span')
    wrapper.className = 'tg-ripple'
    wrapper.setAttribute('aria-hidden', 'true')
    el.appendChild(wrapper)

    const onDown = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      // радиус до самого дальнего угла — волна накрывает всю кнопку
      const radius = Math.max(
        Math.hypot(x, y),
        Math.hypot(rect.width - x, y),
        Math.hypot(x, rect.height - y),
        Math.hypot(rect.width - x, rect.height - y),
      )
      spawnWave(wrapper, x, y, radius)
    }

    el.addEventListener('pointerdown', onDown)
    el._rippleWrapper = wrapper
    el._rippleDown = onDown
  },

  unmounted(el) {
    if (el._rippleDown) el.removeEventListener('pointerdown', el._rippleDown)
    el._rippleWrapper?.remove()
  },
}
