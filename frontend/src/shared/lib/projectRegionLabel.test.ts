import { expect, it } from 'vitest';
import { projectRegionLabel } from './projectRegionLabel';

it('localizes country names without changing custom region data', () => {
  for (const value of ['Brazil', 'Brasil', 'BR']) expect(projectRegionLabel(value)).toBe('Brasil');
  expect(projectRegionLabel('US')).toBe('Estados Unidos');
  expect(projectRegionLabel('DACH')).toBe('DACH');
  expect(projectRegionLabel('São Paulo - interior')).toBe('São Paulo - interior');
});
