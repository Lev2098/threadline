import { computed, ref } from 'vue'

/**
 * Two routes are enough here, so no router library:
 *   /          the discussions table
 *   /t/:id     one thread (server-rendered for crawlers, same URL in the SPA)
 */
export type Route = { name: 'home' } | { name: 'thread'; id: number }

function parse(pathname: string): Route {
  const match = /^\/t\/(\d+)\/?$/.exec(pathname)
  return match ? { name: 'thread', id: Number(match[1]) } : { name: 'home' }
}

export const path = ref(location.pathname)
export const route = computed(() => parse(path.value))

export function navigate(url: string): void {
  const target = new URL(url, location.origin)
  history.pushState(null, '', target.pathname + target.search + target.hash)
  path.value = target.pathname
  if (!target.hash) window.scrollTo({ top: 0 })
}

window.addEventListener('popstate', () => (path.value = location.pathname))

/** Use on <a href> inside the app: SPA navigation, but still a real link for crawlers and new tabs. */
export function onLinkClick(event: MouseEvent, url: string): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return
  }
  event.preventDefault()
  navigate(url)
}

export function threadUrl(id: number): string {
  return `/t/${id}`
}

/* ---------- data embedded by the server-rendered page ---------- */
let initial: unknown = undefined
try {
  const el = document.getElementById('tl-initial')
  initial = el ? JSON.parse(el.textContent || 'null') : null
} catch {
  initial = null
}

/** Returns the server-embedded data once (first render only), then null. */
export function takeInitial<T>(view: string): T | null {
  const data = initial as { view?: string } | null
  initial = null
  return data && data.view === view ? (data as T) : null
}
