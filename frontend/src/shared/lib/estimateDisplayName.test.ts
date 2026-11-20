import { expect, it } from 'vitest';
import { estimateDisplayName } from './estimateDisplayName';

it('localizes the automatic suffix only at display time', () => {
  const stored = 'Obra - Padrão SINAPI - Budget';
  expect(estimateDisplayName(stored)).toBe('Obra - Padrão SINAPI - Orçamento-base');
  expect(stored).toBe('Obra - Padrão SINAPI - Budget');
  expect(estimateDisplayName('Budget personalizado')).toBe('Budget personalizado');
});
