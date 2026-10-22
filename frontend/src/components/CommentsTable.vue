<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Comment, Ordering, SortField } from '@/api/types'
import { formatDate, t } from '@/composables/i18n'
import { plainText } from '@/composables/markup'
import { onLinkClick, threadUrl } from '@/composables/router'
import { spotlight } from '@/composables/fx'
import { avatarStyle, initials } from '@/composables/ui'
import ThreadPanel from './ThreadPanel.vue'

const props = defineProps<{ items: Comment[]; ordering: Ordering; fresh: Set<number> }>()
const emit = defineEmits<{ sort: [ordering: Ordering] }>()
const expanded = ref(new Set<number>())

const field = computed<SortField>(() => props.ordering.replace('-', '') as SortField)
const desc = computed(() => props.ordering.startsWith('-'))

function sortBy(next: SortField): void {
  // First click on a new column: A→Z for text, newest first for dates.
  if (field.value !== next) emit('sort', next === 'created_at' ? '-created_at' : next)
  else emit('sort', (desc.value ? next : `-${next}`) as Ordering)
}

function ariaSort(col: SortField): 'ascending' | 'descending' | 'none' {
  if (field.value !== col) return 'none'
  return desc.value ? 'descending' : 'ascending'
}

function toggle(id: number): void {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

const columns = computed(() => [
  { key: 'username' as const, label: t.value.colAuthor },
  { key: 'email' as const, label: t.value.colEmail },
  { key: 'created_at' as const, label: t.value.colDate },
])
</script>

<template>
  <div class="table-wrap" @pointermove="spotlight">
    <table class="roots">
      <thead>
        <tr>
          <th scope="col" :aria-sort="ariaSort('username')" class="c-author">
            <button type="button" :aria-label="t.sortBy(columns[0].label)" @click="sortBy('username')">
              {{ columns[0].label }}<i :class="{ active: field === 'username', desc }" aria-hidden="true" />
            </button>
          </th>
          <th scope="col" class="c-text">{{ t.colComment }}</th>
          <th scope="col" :aria-sort="ariaSort('email')" class="c-email">
            <button type="button" :aria-label="t.sortBy(columns[1].label)" @click="sortBy('email')">
              {{ columns[1].label }}<i :class="{ active: field === 'email', desc }" aria-hidden="true" />
            </button>
          </th>
          <th scope="col" :aria-sort="ariaSort('created_at')" class="c-date">
            <button type="button" :aria-label="t.sortBy(columns[2].label)" @click="sortBy('created_at')">
              {{ columns[2].label }}<i :class="{ active: field === 'created_at', desc }" aria-hidden="true" />
            </button>
          </th>
          <th scope="col" class="c-replies"><span class="sr-only">{{ t.colReplies }}</span></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(c, i) in items" :key="c.id">
          <tr
            class="row"
            :style="{ '--i': i }"
            :class="{ open: expanded.has(c.id), fresh: fresh.has(c.id) }"
            tabindex="0"
            :aria-expanded="expanded.has(c.id)"
            @click="toggle(c.id)"
            @keydown.enter.prevent="toggle(c.id)"
            @keydown.space.prevent="toggle(c.id)"
          >
            <td class="c-author">
              <div class="who">
                <span class="avatar" :style="avatarStyle(c.username)" aria-hidden="true">{{ initials(c.username) }}</span>
                <span class="name">{{ c.username }}</span>
              </div>
            </td>
            <td class="c-text"><span class="excerpt">{{ plainText(c.html) }}</span></td>
            <td class="c-email">{{ c.email }}</td>
            <td class="c-date"><time :datetime="c.created_at">{{ formatDate(c.created_at) }}</time></td>
            <td class="c-replies">
              <a
                class="open"
                :href="threadUrl(c.id)"
                :title="t.openThread"
                :aria-label="t.openThread"
                @click.stop="onLinkClick($event, threadUrl(c.id))"
                @keydown.enter.stop
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8" /></svg>
              </a>
              <span class="count" :class="{ zero: !c.replies_count }">{{ t.replies(c.replies_count) }}</span>
              <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
              <span class="sr-only">{{ expanded.has(c.id) ? t.hideThread : t.showThread }}</span>
            </td>
          </tr>
          <tr v-if="expanded.has(c.id)" class="thread-row">
            <td colspan="5"><ThreadPanel :root="c" /></td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  position: relative;
  /* pointer-following highlight, painted under the rows */
  background-image: radial-gradient(
    420px circle at var(--mx, -999px) var(--my, -999px),
    color-mix(in srgb, var(--signal) 9%, transparent),
    transparent 70%
  );
  border-radius: var(--radius-l);
  background-color: var(--surface);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-lift);
  overflow: hidden;
}
.roots {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
th {
  text-align: left;
  font-weight: 600;
  font-size: var(--step--1);
  color: var(--muted);
  padding: 0.9rem 1rem;
  border-bottom: 1px solid var(--line);
  background: var(--surface-2);
}
th button {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: 0;
  background: none;
  padding: 0;
  color: inherit;
  font-weight: inherit;
}
th button:hover {
  color: var(--ink);
}
th i {
  width: 0;
  height: 0;
  border: 4px solid transparent;
  border-bottom: 5px solid currentColor;
  border-top-width: 0;
  opacity: 0.25;
  transition: transform 0.25s var(--ease-out), opacity 0.2s;
}
th i.active {
  opacity: 1;
  color: var(--signal);
}
th i.active.desc {
  transform: rotate(180deg);
}
.c-author {
  width: 19%;
}
.c-text {
  width: auto;
}
.c-email {
  width: 17%;
}
.c-date {
  width: 9.5rem;
}
.c-replies {
  width: 10.5rem;
  text-align: right;
}
/* Tablet: the excerpt column gives way first; e-mail stays (it is sortable). */
@media (max-width: 1024px) and (min-width: 761px) {
  .c-text {
    display: none;
  }
  .c-author {
    width: 30%;
  }
  .c-date {
    width: 8.5rem;
  }
  .c-replies {
    width: 9rem;
  }
}
td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row {
  cursor: pointer;
  transition: background-color 0.2s;
  animation: row-enter 0.45s var(--ease-out) both;
  animation-delay: calc(min(var(--i), 12) * 22ms);
}
@keyframes row-enter {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}
.thread-row td > * {
  animation: thread-open 0.4s var(--ease-out) both;
}
@keyframes thread-open {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
}
.row:hover,
.row.open {
  background: color-mix(in srgb, var(--signal-soft) 55%, transparent);
}
.row:focus-visible {
  outline: 2px solid var(--signal);
  outline-offset: -2px;
}
.who {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.avatar {
  flex: none;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  color: #fff;
  font-size: 0.72rem;
  font-weight: 700;
  box-shadow: inset 0 0 0 2px rgb(255 255 255 / 35%);
}
.name {
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
}
.excerpt {
  color: var(--ink-2);
}
.c-email,
.c-date {
  color: var(--muted);
  font-size: 0.92rem;
}
time {
  font-variant-numeric: tabular-nums;
}
.count {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: var(--signal-soft);
  color: var(--signal);
  font-size: var(--step--1);
  font-weight: 600;
}
.count.zero {
  background: transparent;
  color: var(--muted);
  font-weight: 500;
}
.open {
  display: inline-grid;
  place-items: center;
  width: 1.8rem;
  height: 1.8rem;
  margin-right: 0.35rem;
  vertical-align: middle;
  border-radius: 999px;
  color: var(--muted);
  opacity: 0;
  transition: opacity 0.2s, color 0.2s, background-color 0.2s;
}
.open svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
}
.row:hover .open,
.row:focus-within .open,
.open:focus-visible {
  opacity: 1;
}
.open:hover {
  color: var(--signal);
  background: var(--signal-soft);
}
@media (hover: none) {
  .open {
    opacity: 1;
  }
}
.chev {
  width: 18px;
  height: 18px;
  margin-left: 0.4rem;
  vertical-align: middle;
  fill: none;
  stroke: var(--muted);
  stroke-width: 2;
  stroke-linecap: round;
  transition: transform 0.3s var(--ease-out);
}
.open .open {
  display: inline-grid;
  place-items: center;
  width: 1.8rem;
  height: 1.8rem;
  margin-right: 0.35rem;
  vertical-align: middle;
  border-radius: 999px;
  color: var(--muted);
  opacity: 0;
  transition: opacity 0.2s, color 0.2s, background-color 0.2s;
}
.open svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
}
.row:hover .open,
.row:focus-within .open,
.open:focus-visible {
  opacity: 1;
}
.open:hover {
  color: var(--signal);
  background: var(--signal-soft);
}
@media (hover: none) {
  .open {
    opacity: 1;
  }
}
.chev {
  transform: rotate(180deg);
  stroke: var(--signal);
}
.thread-row td {
  white-space: normal;
  padding: 0.5rem 1.25rem 1.25rem;
  background: color-mix(in srgb, var(--signal-soft) 30%, transparent);
  overflow: visible;
}
.fresh {
  animation: row-in 0.8s var(--ease-out) both, row-glow 2.6s 0.4s ease-out;
}
@keyframes row-in {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
}
@keyframes row-glow {
  0% {
    background: var(--mint-soft);
  }
}

/* phones: the table becomes a stack of cards, semantics preserved */
@media (max-width: 760px) {
  thead {
    display: block;
  }
  thead tr {
    display: flex;
    gap: 0.25rem;
    overflow-x: auto;
    background: var(--surface-2);
    border-bottom: 1px solid var(--line);
  }
  thead th {
    border: 0;
    flex: none;
    width: auto;
    white-space: nowrap;
    background: transparent;
  }

  thead th.c-text,
  thead th.c-replies {
    display: none;
  }
  table,
  tbody,
  tr,
  td {
    display: block;
    width: 100%;
  }
  .row {
    display: grid;
    grid-template-columns: 1fr auto;
    padding: 0.6rem 0.25rem;
    border-bottom: 1px solid var(--line);
  }
  .row td {
    border: 0;
    padding: 0.2rem 0.75rem;
    width: auto;
  }
  .row td.c-text {
    grid-column: 1 / -1;
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .row td.c-email {
    display: none;
  }
  .row td.c-replies {
    grid-column: 1 / -1;
    text-align: left;
  }
  .thread-row td {
    padding: 0.5rem 0.4rem 1rem;
  }
}
</style>
