/** Display-only country labels; custom market regions stay as stored. */
export function projectRegionLabel(region: string): string {
  const value = region.trim();
  const code = /^(brazil|brasil|br)$/i.test(value) ? 'BR' : /^[A-Z]{2}$/.test(value) ? value : null;
  if (!code) return region;
  try {
    return new Intl.DisplayNames(['pt-BR'], { type: 'region' }).of(code) ?? region;
  } catch {
    return code === 'BR' ? 'Brasil' : region;
  }
}
