import type { Directive } from 'vue'

const WAVE_BASE = 20
const HOLD_DURATION = 400
const RELEASE_RATE = 2

interface RippleEl extends HTMLElement {
  _rippleWrapper?: HTMLSpanElement
  _rippleDown?: (e: PointerEvent) => void
  _rippleUp?: () => void
  _rippleAnims?: Set<Animation>
}

function spawnWave(wrapper: HTMLSpanElement, x: number, y: number, scale: number, anims: Set<Animation>): void {
  const wave = document.createElement('span')
  wave.className = 'tg-ripple__wave'
  wave.style.left = `${x - WAVE_BASE / 2}px`
  wave.style.top = `${y - WAVE_BASE / 2}px`
  wrapper.appendChild(wave)

  const anim = wave.animate(
    [
      { transform: 'scale(0)', opacity: 1, offset: 0 },
      { transform: `scale(${scale})`, opacity: 1, offset: 0.65 },
      { transform: `scale(${scale})`, opacity: 0, offset: 1 },
    ],
    { duration: HOLD_DURATION, easing: 'ease-out', fill: 'forwards' },
  )
  anims.add(anim)
  const cleanup = () => {
    wave.remove()
    anims.delete(anim)
  }
  anim.onfinish = cleanup
  anim.oncancel = cleanup
}

export const ripple: Directive<RippleEl> = {
  mounted(el) {
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative'

    const wrapper = document.createElement('span')
    wrapper.className = 'tg-ripple'
    wrapper.setAttribute('aria-hidden', 'true')
    el.appendChild(wrapper)

    const anims = new Set<Animation>()

    const onDown = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      // радиус до самого дальнего угла — волна накрывает всю кнопку из любой точки
      const radius = Math.max(
        Math.hypot(x, y),
        Math.hypot(rect.width - x, y),
        Math.hypot(x, rect.height - y),
        Math.hypot(rect.width - x, rect.height - y),
      )
      spawnWave(wrapper, x, y, (radius * 2) / WAVE_BASE, anims)
    }

    // отпускание / клик / уход — доигрываем волну быстрее
    const onUp = () => {
      anims.forEach((a) => {
        a.playbackRate = RELEASE_RATE
      })
    }

    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointercancel', onUp)
    el.addEventListener('pointerleave', onUp)

    el._rippleWrapper = wrapper
    el._rippleDown = onDown
    el._rippleUp = onUp
    el._rippleAnims = anims
  },

  unmounted(el) {
    if (el._rippleDown) el.removeEventListener('pointerdown', el._rippleDown)
    if (el._rippleUp) {
      el.removeEventListener('pointerup', el._rippleUp)
      el.removeEventListener('pointercancel', el._rippleUp)
      el.removeEventListener('pointerleave', el._rippleUp)
    }
    el._rippleAnims?.forEach((a) => a.cancel())
    el._rippleWrapper?.remove()
  },
}
