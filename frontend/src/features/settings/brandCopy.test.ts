import { expect, it } from 'vitest';
import i18next from 'i18next';
import { BRAND } from '@/brand';
import ptBR from '@/app/locales/pt-BR';
import en from '@/app/locales/en';

it('provides Brazilian Portuguese for every English key in the reviewed areas', () => {
  const prefixes = ['dashboard.', 'settings.', 'boq.', 'sidebar.', 'menu_layout.'];
  const english = en.translation as Record<string, string>;
  const brazilian = ptBR.translation as Record<string, string>;
  const missing = Object.keys(english).filter((key) => prefixes.some((prefix) => key.startsWith(prefix)) && !(key in brazilian));
  expect(missing).toEqual([]);
  for (const key of Object.keys(english).filter((key) => prefixes.some((prefix) => key.startsWith(prefix)))) {
    expect(new Set(brazilian[key].match(/\{\{.*?\}\}/g) ?? []), key).toEqual(new Set(english[key].match(/\{\{.*?\}\}/g) ?? []));
  }
});

it('renders account copy with the configured brand in both shipped languages', async () => {
  const i18n = i18next.createInstance();
  await i18n.init({ lng: 'pt-BR', keySeparator: false, resources: { 'pt-BR': ptBR, en }, interpolation: { defaultVariables: { brandName: BRAND.name } } });
  for (const lng of ['pt-BR', 'en']) {
    const text = i18n.t('settings.sign_out_desc', { lng });
    expect(text).toContain(BRAND.name);
    expect(text).not.toMatch(/OpenConstructionERP|OpenEstimate|DataDrivenConstruction|\bDDC\b|\{\{brandName\}\}/);
  }
  expect(i18n.t('sidebar.tools_short', { lng: 'pt-BR' })).toBe('Sistema');
});
