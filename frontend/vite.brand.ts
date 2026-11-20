import { BRAND } from './src/brand';

/** Resolve identity before HTML is served or emitted, including before React boots. */
export function renderBrandHtml(html: string, brand = BRAND): string {
  const values: Record<string, string> = {
    NAME: brand.name, DESCRIPTION: brand.description, LANGUAGE: brand.language,
    LOCALE: brand.locale, ICON: brand.symbol, COLOR: brand.themeColor,
  };
  const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]!);
  return html.replace(/__BRAND_(\w+)__/g, (_, key: string) => {
    if (!(key in values)) throw new Error(`Unknown brand placeholder: ${key}`);
    return escapeHtml(values[key]);
  });
}
