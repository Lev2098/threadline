<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import { ApiError, type Comment, type ThreadSlice } from '@/api/types'
import { setHead } from '@/composables/head'
import { formatDate, t } from '@/composables/i18n'
import { plainText } from '@/composables/markup'
import { onLinkClick, takeInitial } from '@/composables/router'
import ThreadPanel from './ThreadPanel.vue'

const props = defineProps<{ id: number }>()

const root = ref<Comment | null>(null)
const initialSlice = ref<ThreadSlice | null>(null)
const state = ref<'loading' | 'ready' | 'missing' | 'failed'>('loading')
const headline = computed(() => (root.value ? plainText(root.value.html) : ''))

async function load(): Promise<void> {
  const embedded = takeInitial<{ root: Comment; thread: ThreadSlice }>('thread')
  if (embedded && embedded.root.id === props.id) {
    root.value = embedded.root
    initialSlice.value = embedded.thread
    state.value = 'ready'
    return
  }
  state.value = 'loading'
  initialSlice.value = null
  try {
    // The thread endpoint returns replies only; the root comes from its first page.
    const [slice, rootComment] = await Promise.all([api.thread(props.id), api.comment(props.id)])
    root.value = rootComment
    initialSlice.value = slice
    state.value = 'ready'
  } catch (e) {
    state.value = e instanceof ApiError && e.status === 404 ? 'missing' : 'failed'
  }
}

/** Permalink to a reply (#c123): scroll to it and flash it once the tree is rendered. */
function revealHash(): void {
  const target = location.hash ? document.getElementById(location.hash.slice(1)) : null
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target.classList.add('flash')
  window.setTimeout(() => target.classList.remove('flash'), 2400)
}

watch(headline, (text) => {
  if (text) setHead(`${text.slice(0, 70)} — Threadline`, text.slice(0, 160))
})
watch(
  () => props.id,
  () => load(),
)
onMounted(load)
</script>

<template>
  <main class="thread-page">
    <a class="back" href="/" @click="onLinkClick($event, '/')">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
      {{ t.backToAll }}
    </a>

    <div v-if="state === 'loading'" class="skeleton" aria-hidden="true"><span v-for="i in 4" :key="i" /></div>
    <section v-else-if="state === 'missing'" class="empty">
      <h1>{{ t.threadMissing }}</h1>
      <a class="btn btn-primary" href="/" @click="onLinkClick($event, '/')">{{ t.backToAll }}</a>
    </section>
    <section v-else-if="state === 'failed'" class="empty">
      <p>{{ t.loadError }}</p>
      <button type="button" class="btn btn-primary" @click="load">{{ t.retry }}</button>
    </section>
    <template v-else-if="root">
      <header class="thread-head">
        <h1>{{ headline }}</h1>
        <p class="meta">{{ root.username }} · {{ formatDate(root.created_at) }} · {{ t.replies(root.replies_count) }}</p>
      </header>
      <ThreadPanel :key="root.id" :root="root" :initial="initialSlice" @loaded="nextTick(revealHash)" />
    </template>
  </main>
</template>

<style scoped>
.thread-page {
  max-width: 920px;
  margin: 0 auto;
  padding: 1.5rem clamp(1rem, 4vw, 2.5rem) 4rem;
}
.back {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 1.25rem;
  color: var(--ink-2);
  text-decoration: none;
  font-weight: 600;
}
.back svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  transition: transform 0.2s var(--ease-out);
}
.back:hover svg {
  transform: translateX(-3px);
}
.thread-head h1 {
  margin: 0 0 0.4rem;
  font-family: var(--font-display);
  font-size: clamp(1.4rem, 1rem + 2vw, 2.2rem);
  line-height: 1.15;
  letter-spacing: -0.02em;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta {
  margin: 0 0 1.5rem;
  color: var(--muted);
}
.empty {
  display: grid;
  justify-items: start;
  gap: 1rem;
  padding: 2rem 0;
}
.empty h1 {
  margin: 0;
  font-family: var(--font-display);
}
.skeleton {
  display: grid;
  gap: 0.75rem;
}
.skeleton span {
  height: 6rem;
  border-radius: var(--radius-m);
  background: linear-gradient(90deg, var(--surface) 0%, var(--surface-2) 50%, var(--surface) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}
</style>
