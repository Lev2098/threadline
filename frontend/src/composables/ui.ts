import { reactive, ref } from 'vue'
import type { Attachment, Comment } from '@/api/types'

/* ---------- theme ---------- */
export type Theme = 'light' | 'dark'

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem('threadline.theme')
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* ignore */
  }
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const theme = ref<Theme>(initialTheme())
document.documentElement.dataset.theme = theme.value

export function toggleTheme(): void {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = theme.value
  try {
    localStorage.setItem('threadline.theme', theme.value)
  } catch {
    /* ignore */
  }
}

/* ---------- composer ---------- */
export const composer = reactive<{ open: boolean; parent: Comment | null }>({ open: false, parent: null })

export function openComposer(parent: Comment | null = null): void {
  composer.parent = parent
  composer.open = true
}

/* ---------- lightbox ---------- */
export const lightbox = reactive<{ attachment: Attachment | null; origin: DOMRect | null }>({
  attachment: null,
  origin: null,
})

export function openLightbox(attachment: Attachment, origin: HTMLElement): void {
  lightbox.origin = origin.getBoundingClientRect()
  lightbox.attachment = attachment
}

/* ---------- toasts ---------- */
export const toasts = ref<{ id: number; text: string; tone: 'ok' | 'error' }[]>([])
let toastId = 0

export function toast(text: string, tone: 'ok' | 'error' = 'ok'): void {
  const id = ++toastId
  toasts.value.push({ id, text, tone })
  window.setTimeout(() => (toasts.value = toasts.value.filter((x) => x.id !== id)), 3600)
}

/* ---------- avatars ---------- */
/** Deterministic two-hue gradient per username: the same author always looks the same. */
export function avatarStyle(name: string): Record<string, string> {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  const h1 = 230 + (hash % 90) // violet → indigo → magenta band, on-palette
  const h2 = (h1 + 40 + ((hash >> 8) % 60)) % 360
  return { background: `linear-gradient(135deg, hsl(${h1} 78% 62%), hsl(${h2} 82% 58%))` }
}

export function initials(name: string): string {
  const letters = name.replace(/[^A-Za-z]/g, '')
  return (letters.slice(0, 2) || name.slice(0, 2)).toUpperCase()
}

export const prefersReducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches

/* ---------- viewport ---------- */
const compactQuery = matchMedia('(max-width: 640px)')
/** Phones: thread indentation stops early so deep replies stay readable. */
export const compact = ref(compactQuery.matches)
compactQuery.addEventListener('change', (e) => (compact.value = e.matches))

/* ---------- modal dialogs ---------- */
/**
 * Makes the page behind a dialog inert (no Tab, no screen reader, no scroll)
 * and returns a function that undoes it and puts focus back where it was.
 */
export function enterModal(): () => void {
  const opener = document.activeElement as HTMLElement | null
  const app = document.getElementById('app')
  app?.setAttribute('inert', '')
  const overflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  return () => {
    app?.removeAttribute('inert')
    document.body.style.overflow = overflow
    if (opener?.isConnected) opener.focus()
  }
}

export const isMac = /Mac|iPhone|iPad/.test(navigator.platform)
