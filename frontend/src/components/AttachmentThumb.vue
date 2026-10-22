<script setup lang="ts">
import { ref } from 'vue'
import type { Attachment } from '@/api/types'
import { t } from '@/composables/i18n'
import { openLightbox } from '@/composables/ui'

const props = defineProps<{ attachment: Attachment }>()
const el = ref<HTMLElement>()

function open(): void {
  if (el.value) openLightbox(props.attachment, el.value)
}

function kb(size: number): string {
  return `${Math.max(1, Math.round(size / 1024))} ${t.value.kb}`
}
</script>

<template>
  <button ref="el" type="button" class="thumb" :class="attachment.kind" :title="t.openFile" @click="open">
    <span class="sr-only">{{ t.openFile }}: </span>
    <img
      v-if="attachment.kind === 'image'"
      :src="attachment.url"
      :alt="attachment.name"
      :width="attachment.width ?? undefined"
      :height="attachment.height ?? undefined"
      loading="lazy"
      decoding="async"
    />
    <template v-else>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
        <path d="M14 3v5h5M9 13h6M9 17h4" />
      </svg>
      <span class="name">{{ attachment.name }}</span>
      <span class="size">{{ kb(attachment.size) }}</span>
    </template>
  </button>
</template>

<style scoped>
.thumb {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.75rem;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-m);
  background: var(--surface-2);
  overflow: hidden;
  cursor: zoom-in;
  transition: transform 0.25s var(--ease-out), box-shadow 0.25s, border-color 0.2s;
}
.thumb:hover {
  transform: translateY(-2px) rotate(-0.4deg);
  box-shadow: var(--shadow-lift);
  border-color: var(--signal-2);
}
.thumb.image img {
  display: block;
  max-width: min(160px, 40vw);
  height: auto;
}
.thumb.text {
  padding: 0.55rem 0.9rem;
  max-width: 100%;
}
.thumb svg {
  flex: none;
  width: 22px;
  height: 22px;
  fill: none;
  stroke: var(--signal);
  stroke-width: 1.8;
  stroke-linejoin: round;
}
.name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.size {
  color: var(--muted);
  font-size: var(--step--1);
}
</style>
