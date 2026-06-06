import type { Directive } from 'vue'

const WAVE_BASE = 20
const EXPAND_DURATION = 400
const FADE_DURATION = 800
const RELEASE_RATE = 2
// запас, чтобы волна перекрывала края кнопки без зазоров
const RADIUS_BUFFER = 12
// множитель радиуса — больше круг = площе (ровнее) дуга
const RADIUS_SCALE = 1.5

interface WaveHandle {
  wave: HTMLSpanElement
  expand: Animation
  released: boolean
}

interface RippleEl extends HTMLElement {
  _rippleWrapper?: HTMLSpanElement
  _rippleDown?: (e: PointerEvent) => void
  _rippleUp?: () => void
  _rippleWaves?: Set<WaveHandle>
}

function spawnWave(wrapper: HTMLSpanElement, x: number, y: number, scale: number, waves: Set<WaveHandle>): void {
  const wave = document.createElement('span')
  wave.className = 'tg-ripple__wave'
  wave.style.left = `${x - WAVE_BASE / 2}px`
  wave.style.top = `${y - WAVE_BASE / 2}px`
  wrapper.appendChild(wave)

  const expand = wave.animate(
    [
      { transform: 'scale(0)', opacity: 1, offset: 0 },
      { transform: `scale(${scale})`, opacity: 1, offset: 1 },
    ],
    { duration: EXPAND_DURATION, easing: 'ease-out', fill: 'forwards' },
  )
  waves.add({ wave, expand, released: false })
}

function releaseWave(h: WaveHandle, waves: Set<WaveHandle>): void {
  if (h.released) return
  h.released = true
  // быстрый клик — досхлопнуть расширение, затем гасить
  h.expand.playbackRate = RELEASE_RATE

  const remove = () => {
    h.wave.remove()
    waves.delete(h)
  }
  const fade = () => {
    const f = h.wave.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: FADE_DURATION,
      easing: 'ease-out',
      fill: 'forwards',
    })
    f.onfinish = remove
    f.oncancel = remove
  }
  h.expand.finished.then(fade).catch(remove)
}

export const ripple: Directive<RippleEl> = {
  mounted(el) {
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative'
    // отдельный контекст наложения — волна уходит под контент (z-index: -1)
    el.style.isolation = 'isolate'

    const wrapper = document.createElement('span')
    wrapper.className = 'tg-ripple'
    wrapper.setAttribute('aria-hidden', 'true')
    el.appendChild(wrapper)

    const waves = new Set<WaveHandle>()

    const onDown = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      // радиус до самого дальнего угла, увеличенный — круг расходится во все стороны,
      // дуга площе (ровнее) на низкой кнопке
      const radius =
        (Math.max(
          Math.hypot(x, y),
          Math.hypot(rect.width - x, y),
          Math.hypot(x, rect.height - y),
          Math.hypot(rect.width - x, rect.height - y),
        ) +
          RADIUS_BUFFER) *
        RADIUS_SCALE
      // новое нажатие гасит предыдущие волны — без стакания
      waves.forEach((h) => releaseWave(h, waves))
      spawnWave(wrapper, x, y, (radius * 2) / WAVE_BASE, waves)
    }

    // отпускание / клик / уход — гасим волну
    const onUp = () => {
      waves.forEach((h) => releaseWave(h, waves))
    }

    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointercancel', onUp)
    el.addEventListener('pointerleave', onUp)

    el._rippleWrapper = wrapper
    el._rippleDown = onDown
    el._rippleUp = onUp
    el._rippleWaves = waves
  },

  unmounted(el) {
    if (el._rippleDown) el.removeEventListener('pointerdown', el._rippleDown)
    if (el._rippleUp) {
      el.removeEventListener('pointerup', el._rippleUp)
      el.removeEventListener('pointercancel', el._rippleUp)
      el.removeEventListener('pointerleave', el._rippleUp)
    }
    el._rippleWaves?.forEach((h) => {
      h.expand.cancel()
      h.wave.remove()
    })
    el._rippleWrapper?.remove()
  },
}
