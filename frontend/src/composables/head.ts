/** Keeps <title> and the description in sync during client-side navigation. */
export function setHead(title: string, description?: string): void {
  document.title = title
  if (description !== undefined) {
    document.querySelector('meta[name="description"]')?.setAttribute('content', description)
  }
}
