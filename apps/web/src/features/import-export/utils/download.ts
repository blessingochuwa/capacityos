/** Triggers a browser file save for an already-fetched blob — the standard
 * client-side download pattern (temporary object URL + a synthetic
 * <a download> click), not a real navigation. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
