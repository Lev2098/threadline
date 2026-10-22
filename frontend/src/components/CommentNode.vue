<script setup lang="ts">
import { computed } from 'vue'
import type { Comment } from '@/api/types'
import { formatDate, t } from '@/composables/i18n'
import { plainText, safeHtml } from '@/composables/markup'
import { threadUrl } from '@/composables/router'
import { avatarStyle, compact, initials, openComposer, toast } from '@/composables/ui'
import AttachmentThumb from './AttachmentThumb.vue'

export interface TreeNode {
  comment: Comment
  children: TreeNode[]
  fresh?: boolean
}

const props = defineProps<{ node: TreeNode; parent?: Comment | null; level?: number; flat?: boolean }>()
const level = computed(() => props.level ?? 0)
/**
 * Indentation stops after a few levels (3 on phones, 8 on wider screens):
 * deeper replies line up under their parent and rely on the quote for context,
 * so a 50-level thread never squeezes cards to a few pixels.
 */
const MAX_INDENT_WIDE = 8
const MAX_INDENT_COMPACT = 3
const flatChildren = computed(() => level.value + 1 > (compact.value ? MAX_INDENT_COMPACT : MAX_INDENT_WIDE))
const c = computed(() => props.node.comment)
const permalink = computed(() => `${threadUrl(c.value.root_id)}#c${c.value.id}`)

async function copyPermalink(event: MouseEvent): Promise<void> {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return // open in new tab as usual
  event.preventDefault()
  const url = new URL(permalink.value, location.origin).href
  try {
    await navigator.clipboard.writeText(url)
    toast(t.value.linkCopied)
  } catch {
    location.href = url
  }
}

const quote = computed(() => (props.parent && level.value > 1 ? plainText(props.parent.html) : ''))
</script>

<template>
  <article
    :id="`c${c.id}`"
    class="node"
    :class="{ fresh: node.fresh, nested: level > 0 && !flat, flat }"
    :style="{ '--level': level }"
  >
    <div class="card">
      <header class="meta">
        <span class="avatar" :style="avatarStyle(c.username)" aria-hidden="true">{{ initials(c.username) }}</span>
        <strong class="author">{{ c.username }}</strong>
        <time :datetime="c.created_at">{{ formatDate(c.created_at) }}</time>
        <a class="perma" :href="permalink" :title="t.permalink" :aria-label="t.permalink" @click="copyPermalink">#</a>
        <a v-if="c.home_page" class="home" :href="c.home_page" target="_blank" rel="nofollow noopener noreferrer" :title="t.homepage">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11.5 12 5l8 6.5M6.5 10v9h11v-9" /></svg>
          <span class="sr-only">{{ t.homepage }}</span>
        </a>
        <button type="button" class="reply" @click="openComposer(c)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></svg>
          {{ t.reply }}
        </button>
      </header>

      <blockquote v-if="quote" class="quote" :aria-label="t.quoteLabel">{{ quote }}</blockquote>
      <div class="prose body" v-html="safeHtml(c.html)" />
      <AttachmentThumb v-if="c.attachment" :attachment="c.attachment" />
    </div>

    <div v-if="node.children.length" class="children" :class="{ flat: flatChildren }">
      <CommentNode
        v-for="child in node.children"
        :key="child.comment.id"
        :node="child"
        :parent="c"
        :level="level + 1"
        :flat="flatChildren"
      />
    </div>
  </article>
</template>

<style scoped>
.card {
  position: relative;
  padding: 0.9rem 1.1rem 1rem;
  border-radius: var(--radius-m);
  background: var(--surface);
  border: 1px solid var(--line);
  transition: border-color 0.25s, box-shadow 0.25s;
}
.card:hover {
  border-color: color-mix(in srgb, var(--signal) 35%, var(--line));
}
.meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem 0.7rem;
  margin: -0.15rem 0 0.55rem;
  padding: 0.35rem 0.4rem 0.35rem 0.35rem;
  border-radius: 999px;
  background: var(--surface-2);
}
@media (max-width: 640px) {
  .meta {
    border-radius: 12px;
  }
  .card {
    padding: 0.75rem 0.8rem 0.85rem;
  }
}
.avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  box-shadow: inset 0 0 0 2px rgb(255 255 255 / 35%);
}
.author {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 650;
}
time {
  color: var(--muted);
  font-size: var(--step--1);
  font-variant-numeric: tabular-nums;
}
.home {
  display: inline-grid;
  color: var(--muted);
}
.home svg,
.reply svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.home:hover {
  color: var(--signal);
}
.perma {
  color: var(--muted);
  font-weight: 700;
  text-decoration: none;
  padding: 0 0.2rem;
  border-radius: 6px;
  transition: color 0.2s, background-color 0.2s;
}
.perma:hover {
  color: var(--signal);
  background: var(--signal-soft);
}
/* target of a permalink: one soft flash */
.node.flash > .card {
  animation: flash 2.2s ease-out;
}
@keyframes flash {
  0%,
  30% {
    border-color: var(--signal);
    box-shadow: 0 0 0 6px var(--signal-soft);
  }
}
.reply {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 0;
  border-radius: 999px;
  background: transparent;
  padding: 0.3rem 0.7rem;
  color: var(--signal);
  font-size: var(--step--1);
  font-weight: 600;
}
.reply:hover {
  background: var(--signal-soft);
}
.reply svg {
  transition: transform 0.25s var(--ease-out);
}
.reply:hover svg {
  transform: translateX(-2px) rotate(-8deg);
}
.avatar {
  transition: transform 0.3s var(--ease-out), filter 0.3s;
}
.card:hover .avatar {
  transform: rotate(-6deg) scale(1.06);
  filter: saturate(1.25);
}
.quote {
  margin: 0 0 0.5rem;
  padding: 0.1rem 0 0.1rem 0.75rem;
  border-left: 2px solid var(--signal-2);
  color: var(--muted);
  font-size: 0.92em;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* ---------- the thread rails ----------
 * Each reply draws its own pieces: an elbow from the rail into its card and,
 * unless it is the last sibling, the rail segment continuing past it. So the
 * rail always ends exactly at the last reply instead of overshooting. */
.node {
  position: relative;
  min-width: 0; /* long nowrap quotes must not widen the grid track */
  --rail-color: color-mix(in srgb, var(--signal) 50%, transparent);
}
.children {
  margin-left: max(0.6rem, calc(1.6rem - var(--level) * 0.2rem));
  padding-left: max(0.8rem, calc(1.6rem - var(--level) * 0.2rem));
  padding-top: 0.75rem;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.75rem;
}
.children.flat {
  margin-left: 0;
  padding-left: 0;
}
@media (max-width: 640px) {
  .children {
    margin-left: 0.35rem;
    padding-left: 0.7rem;
  }
  .children.flat {
    margin-left: 0;
    padding-left: 0;
  }
  .nested {
    --indent: 0.7rem;
  }
}
.nested {
  /* this reply's indent = its parent's .children padding */
  --indent: max(0.8rem, calc(1.6rem - (var(--level) - 1) * 0.2rem));
}
.nested > .card::before {
  content: '';
  position: absolute;
  left: calc(-1 * var(--indent) - 1px);
  top: -0.75rem;
  width: var(--indent);
  height: 2.1rem;
  border-left: 2px solid var(--rail-color);
  border-bottom: 2px solid var(--rail-color);
  border-bottom-left-radius: 14px;
}
.nested:not(:last-child)::after {
  content: '';
  position: absolute;
  left: calc(-1 * var(--indent) - 1px);
  top: 0;
  bottom: -0.75rem;
  width: 2px;
  background: var(--rail-color);
}

/* ---------- live arrival: the one orchestrated moment ---------- */
.fresh > .card {
  animation: arrive 0.7s var(--ease-out) both, glow 2.4s 0.5s ease-out;
}
.fresh > .card::before {
  clip-path: inset(0 100% 0 0);
  animation: draw 0.6s var(--ease-out) forwards;
}
@keyframes arrive {
  from {
    opacity: 0;
    transform: translateY(-6px) scale(0.985);
  }
}
@keyframes glow {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--mint) 60%, transparent);
    border-color: var(--mint);
  }
  100% {
    box-shadow: 0 0 0 14px transparent;
  }
}
@keyframes draw {
  to {
    clip-path: inset(0 0 0 0);
  }
}
</style>
