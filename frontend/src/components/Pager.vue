<script setup lang="ts">
import { computed } from 'vue'
import { t } from '@/composables/i18n'

const props = defineProps<{ page: number; pages: number }>()
const emit = defineEmits<{ go: [page: number] }>()

/** 1 … 4 5 [6] 7 8 … 40 — never more than 9 buttons, whatever the page count. */
const items = computed<(number | '…')[]>(() => {
  const { page, pages } = props
  if (pages <= 9) return Array.from({ length: pages }, (_, i) => i + 1)
  const out: (number | '…')[] = [1]
  const from = Math.max(2, Math.min(page - 2, pages - 6))
  const to = Math.min(pages - 1, Math.max(page + 2, 7))
  // An ellipsis standing for exactly one page is replaced by that page.
  if (from === 3) out.push(2)
  else if (from > 3) out.push('…')
  for (let i = from; i <= to; i++) out.push(i)
  if (to === pages - 2) out.push(pages - 1)
  else if (to < pages - 2) out.push('…')
  out.push(pages)
  return out
})
</script>

<template>
  <nav v-if="pages > 1" class="pager" :aria-label="t.page">
    <button type="button" class="step" :disabled="page <= 1" @click="emit('go', page - 1)">{{ t.prev }}</button>
    <template v-for="(item, i) in items" :key="i">
      <span v-if="item === '…'" class="gap" aria-hidden="true">…</span>
      <button
        v-else
        type="button"
        class="num"
        :aria-current="item === page ? 'page' : undefined"
        :aria-label="`${t.page} ${item}`"
        @click="emit('go', item)"
      >
        {{ item }}
      </button>
    </template>
    <button type="button" class="step" :disabled="page >= pages" @click="emit('go', page + 1)">{{ t.next }}</button>
  </nav>
</template>

<style scoped>
.pager {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 0.35rem;
  margin: 1.75rem 0 0.5rem;
}
button {
  min-width: 2.4rem;
  height: 2.4rem;
  padding: 0 0.7rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
  transition: background-color 0.2s, color 0.2s;
}
button:hover:not(:disabled) {
  background: var(--signal-soft);
  color: var(--ink);
}
button[aria-current='page'] {
  background: var(--ink);
  color: var(--paper);
  font-weight: 700;
}
.step {
  border-color: var(--line);
}
.step:disabled {
  opacity: 0.4;
  cursor: default;
}
.gap {
  color: var(--muted);
  padding: 0 0.2rem;
}
</style>
