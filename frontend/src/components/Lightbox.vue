<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { t } from '@/composables/i18n'
import { enterModal, lightbox, prefersReducedMotion } from '@/composables/ui'

const frame = ref<HTMLElement>()
const closeBtn = ref<HTMLButtonElement>()
const text = ref<string | null>(null)
const textFailed = ref(false)
let leaveModal: (() => void) | null = null

/**
 * FLIP zoom: the frame starts exactly where the thumbnail is and grows into
 * place, so the image visibly "lifts off" the page instead of popping in.
 */
async function animateIn(): Promise<void> {
  await nextTick()
  const el = frame.value
  const origin = lightbox.origin
  closeBtn.value?.focus()
  if (!el || !origin || prefersReducedMotion) return
  const target = el.getBoundingClientRect()
  const dx = origin.left + origin.width / 2 - (target.left + target.width / 2)
  const dy = origin.top + origin.height / 2 - (target.top + target.height / 2)
  const scale = Math.max(origin.width / target.width, 0.15)
  el.animate(
    [
      { transform: `translate(${dx}px, ${dy}px) scale(${scale})`, opacity: 0.4, borderRadius: '24px' },
      { transform: 'none', opacity: 1, borderRadius: '18px' },
    ],
    { duration: 420, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' },
  )
}

async function loadText(url: string): Promise<void> {
  text.value = null
  textFailed.value = false
  try {
    const response = await fetch(url)
    if (!response.ok) throw new Error(String(response.status))
    // Rendered via text interpolation, never as HTML.
    text.value = await response.text()
  } catch {
    textFailed.value = true
  }
}

function close(): void {
  lightbox.attachment = null
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') close()
  if (event.key === 'Tab') {
    // Only two controls: keep focus cycling between them.
    const items = [closeBtn.value, frame.value?.querySelector<HTMLElement>('a')].filter(Boolean) as HTMLElement[]
    const index = items.indexOf(document.activeElement as HTMLElement)
    event.preventDefault()
    items[(index + (event.shiftKey ? items.length - 1 : 1)) % items.length]?.focus()
  }
}

watch(
  () => lightbox.attachment,
  (attachment) => {
    if (attachment) {
      leaveModal = enterModal()
      document.addEventListener('keydown', onKey)
      if (attachment.kind === 'text') loadText(attachment.url)
      animateIn()
    } else {
      document.removeEventListener('keydown', onKey)
      leaveModal?.()
      leaveModal = null
    }
  },
)
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="lightbox.attachment" class="lightbox" role="dialog" aria-modal="true" :aria-label="lightbox.attachment.name" @click.self="close">
        <figure ref="frame" class="frame" :class="lightbox.attachment.kind">
          <img
            v-if="lightbox.attachment.kind === 'image'"
            :src="lightbox.attachment.url"
            :alt="lightbox.attachment.name"
            :width="lightbox.attachment.width ?? undefined"
            :height="lightbox.attachment.height ?? undefined"
          />
          <pre v-else-if="text !== null" class="text">{{ text }}</pre>
          <p v-else class="text muted">{{ textFailed ? t.loadError : t.loading }}</p>
          <figcaption>
            <span>{{ lightbox.attachment.name }}</span>
            <a :href="lightbox.attachment.url" target="_blank" rel="noopener" download :aria-label="t.download" :title="t.download">↓</a>
          </figcaption>
        </figure>
        <button ref="closeBtn" type="button" class="close" :aria-label="t.close" @click="close">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 4rem 1rem 2rem;
  background: radial-gradient(circle at 50% 40%, rgb(60 40 160 / 55%), rgb(10 9 28 / 88%));
  backdrop-filter: blur(10px);
}
.frame {
  margin: 0;
  max-width: min(92vw, 900px);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: 0 40px 120px -20px rgb(0 0 0 / 60%);
  overflow: hidden;
  transform-origin: center;
}
.frame.image img {
  display: block;
  /* Stored images are at most 320×240; scale up crisply for viewing. */
  width: min(80vw, 640px);
  height: auto;
  max-height: 70vh;
  object-fit: contain;
  image-rendering: auto;
  background: var(--surface-2);
}
.text {
  margin: 0;
  width: min(86vw, 760px);
  max-height: 70vh;
  overflow: auto;
  padding: 1.25rem 1.5rem;
  font-family: var(--font-code);
  font-size: 0.88rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.muted {
  color: var(--muted);
}
figcaption {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.7rem 1rem;
  border-top: 1px solid var(--line);
  font-size: var(--step--1);
  color: var(--ink-2);
}
figcaption a {
  font-weight: 700;
  text-decoration: none;
}
.close {
  position: fixed;
  top: 1rem;
  right: 1rem;
  display: grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  border: 0;
  border-radius: 50%;
  background: rgb(255 255 255 / 14%);
  color: #fff;
}
.close:hover {
  background: rgb(255 255 255 / 26%);
}
.close svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
