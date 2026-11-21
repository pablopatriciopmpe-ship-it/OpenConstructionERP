// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { SHOW_GUIDED_CASES } from '@/features/cases/casesConfig';

describe('Visible keys pt-BR regression test', () => {
  it('has guided cases enabled (SHOW_GUIDED_CASES === true)', () => {
    expect(SHOW_GUIDED_CASES).toBe(true);
  });

  it('tracks all pending visible translations in baseline-faltando-ptbr.json', () => {
    const baselinePath = path.resolve(__dirname, '../locales/baseline-faltando-ptbr.json');
    expect(fs.existsSync(baselinePath)).toBe(true);

    const content = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'));
    const modules = Object.keys(content);
    expect(modules.length).toBeGreaterThanOrEqual(40);

    let totalKeys = 0;
    for (const [mod, keys] of Object.entries(content)) {
      expect(typeof keys).toBe('object');
      const count = Object.keys(keys as Record<string, string>).length;
      expect(count).toBeGreaterThan(0);
      totalKeys += count;

      // Each tracked item must have a key and non-empty english text
      for (const [k, v] of Object.entries(keys as Record<string, string>)) {
        expect(k).toBeTruthy();
        expect(typeof v).toBe('string');
        expect(v.length).toBeGreaterThan(0);
      }
    }

    expect(totalKeys).toBe(1171);
  });

  it('ensures known visible keys (guides and playbooks) have either pt-BR translation or tracking', () => {
    const baselinePath = path.resolve(__dirname, '../locales/baseline-faltando-ptbr.json');
    const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'));
    const trackedKeys = new Set<string>();
    for (const keys of Object.values(baseline)) {
      for (const k of Object.keys(keys as Record<string, string>)) {
        trackedKeys.add(k);
      }
    }

    // Spot-check known guide keys
    const sampleGuideKeys = [
      'guide.tasks.title',
      'guide.tasks.intro',
      'guide.schedule.title',
      'guide.validation.title',
    ];

    for (const key of sampleGuideKeys) {
      expect(trackedKeys.has(key)).toBe(true);
    }
  });
});
