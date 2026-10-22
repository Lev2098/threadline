/**
 * Client-side mirror of the server validator (comments/domain/markup.py).
 * Gives instant feedback while typing; the server stays the source of truth.
 */
import DOMPurify from 'dompurify'

export type MarkupIssue =
  | { kind: 'tag'; tag: string }
  | { kind: 'unclosed'; tag: string }
  | { kind: 'mismatch'; expected: string; got: string }
  | { kind: 'orphan'; tag: string }
  | { kind: 'href' }

const ALLOWED = new Set(['a', 'code', 'i', 'strong'])
const TAG_RE = /<(\/?)([A-Za-z][A-Za-z0-9]*)\b([^<>]*?)(\/?)\s*>/g
const HREF_RE = /href\s*=\s*(?:"([^"]*)"|'([^']*)')/i
const SAFE_HREF = /^(?:https?:\/\/|mailto:)[^\s"'<>`]+$/i

export function checkMarkup(source: string): MarkupIssue | null {
  const stack: string[] = []
  for (const match of source.matchAll(TAG_RE)) {
    const [, closing, rawName, attrs, selfClosing] = match
    const name = rawName.toLowerCase()
    if (!ALLOWED.has(name) || selfClosing) return { kind: 'tag', tag: name }
    if (closing) {
      if (!stack.length) return { kind: 'orphan', tag: name }
      const top = stack.pop()!
      if (top !== name) return { kind: 'mismatch', expected: top, got: name }
      continue
    }
    if (name === 'a') {
      const href = HREF_RE.exec(attrs)
      if (!href || !SAFE_HREF.test((href[1] ?? href[2] ?? '').trim())) return { kind: 'href' }
    }
    stack.push(name)
  }
  return stack.length ? { kind: 'unclosed', tag: stack[stack.length - 1] } : null
}

/**
 * Server HTML is already sanitized; this is a second, independent layer in
 * the browser with the same allow-list, so a server bug can't become XSS.
 */
export function safeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['a', 'code', 'i', 'strong'],
    ALLOWED_ATTR: ['href', 'title', 'rel', 'target'],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
  })
}

export function plainText(html: string): string {
  const doc = new DOMParser().parseFromString(safeHtml(html), 'text/html')
  return (doc.body.textContent ?? '').replace(/\s+/g, ' ').trim()
}
