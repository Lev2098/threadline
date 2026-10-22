/**
 * Small, purposeful motion. Everything here is skipped under
 * prefers-reduced-motion (checked at call time, so a change applies at once).
 */
import { ref } from 'vue'

const reducedQuery = matchMedia('(prefers-reduced-motion: reduce)')
export const reducedMotion = (): boolean => reducedQuery.matches

/** Animated count-up for headline numbers; resolves instantly with reduced motion. */
export function useCountUp(duration = 900) {
  const value = ref(0)
  let frame = 0
  function to(target: number): void {
    cancelAnimationFrame(frame)
    const from = value.value
    if (reducedMotion() || Math.abs(target - from) < 2) {
      value.value = target
      return
    }
    const start = performance.now()
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 4)
      value.value = Math.round(from + (target - from) * eased)
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
  }
  return { value, to }
}

const COLORS = ['var(--signal)', 'var(--signal-2)', 'var(--mint)', '#ffb84d']

/** Burst of dots from a point: the "published" moment. Pure DOM + CSS, ~30 nodes, removed after. */
export function burst(x: number, y: number, count = 28): void {
  if (reducedMotion()) return
  const layer = document.createElement('div')
  layer.className = 'fx-burst'
  layer.setAttribute('aria-hidden', 'true')
  for (let i = 0; i < count; i++) {
    const dot = document.createElement('i')
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4
    const distance = 60 + Math.random() * 90
    dot.style.setProperty('--dx', `${Math.cos(angle) * distance}px`)
    dot.style.setProperty('--dy', `${Math.sin(angle) * distance - 40}px`)
    dot.style.setProperty('--s', `${0.5 + Math.random() * 0.9}`)
    dot.style.background = COLORS[i % COLORS.length]
    dot.style.left = `${x}px`
    dot.style.top = `${y}px`
    dot.style.borderRadius = i % 3 === 0 ? '2px' : '50%'
    layer.appendChild(dot)
  }
  document.body.appendChild(layer)
  window.setTimeout(() => layer.remove(), 1100)
}

type ViewTransitionDoc = Document & { startViewTransition?: (cb: () => void) => unknown }

/** Runs a DOM change as a circular reveal from (x, y) where supported; otherwise just runs it. */
export function revealFrom(x: number, y: number, change: () => void): void {
  const doc = document as ViewTransitionDoc
  if (!doc.startViewTransition || reducedMotion()) {
    change()
    return
  }
  const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
  document.documentElement.style.setProperty('--vt-x', `${x}px`)
  document.documentElement.style.setProperty('--vt-y', `${y}px`)
  document.documentElement.style.setProperty('--vt-r', `${radius}px`)
  doc.startViewTransition(change)
}

/** Pointer-following highlight: sets --mx/--my on the element (fine pointers only). */
export function spotlight(event: PointerEvent): void {
  if (event.pointerType !== 'mouse') return
  const el = event.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${event.clientX - rect.left}px`)
  el.style.setProperty('--my', `${event.clientY - rect.top}px`)
}
