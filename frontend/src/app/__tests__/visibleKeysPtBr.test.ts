// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  SHOW_GUIDED_CASES,
  SHOW_VIDEOS,
  SHOW_PROJECT_JOURNEY,
} from '@/features/cases/casesConfig';
import { PRODUCT_MODULE_IDS } from '@/modules/productManifest';

const SRC_ROOT = path.resolve(__dirname, '../..');
const PT_BR_PATH = path.resolve(__dirname, '../locales/pt-BR.ts');
const EN_PATH = path.resolve(__dirname, '../locales/en.ts');
const BASELINE_PATH = path.resolve(__dirname, '../locales/baseline-faltando-ptbr.json');

const VISIBLE_FEATURE_DIRS = [
  'ai-estimator',
  'allowances',
  'assemblies',
  'auth',
  'bim',
  'boq',
  'catalog',
  'changeorders',
  'cost-control',
  'costs',
  'cvr',
  'daily-diary',
  'dashboard',
  'documents',
  'drawing-compare',
  'dwg-takeoff',
  'eac',
  'estimate-checks',
  'fieldreports',
  'file-manager',
  'full-evm',
  'inspections',
  'labor-rates',
  'markups',
  'match-elements',
  'measurement-book',
  'meetings',
  'notifications',
  'offers',
  'onboarding',
  'photos',
  'postcalc',
  'preliminaries',
  'price-index',
  'progress',
  'projects',
  'punchlist',
  'quantities',
  'quote-capture',
  'reporting',
  'reports',
  'resources',
  'rfi',
  'saas',
  'schedule',
  'settings',
  'takeoff',
  'tasks',
  'teams',
  'users',
  'validation',
  'variations',
  'waste-factors',
] as const;

// Files belonging strictly to pruned/hidden features or non-rendered static catalogues.
const PRUNED_SOURCE_FILES = new Set([
  'features/dashboard/DashboardCasesCard.tsx',
  'features/dashboard/DashboardMarketCasesCard.tsx',
  'features/dashboard/widgetRegistry.ts',
  'features/videos/DashboardVideosStrip.tsx',
  'features/videos/PromoVideos.tsx',
  'features/settings/LearningTipsCard.tsx',
  'features/onboarding/modules.ts',
  'app/layout/ProjectJourney.tsx',
  'app/layout/projectJourneyData.ts',
  'app/layout/navCatalog.ts',
]);

const T_CALL_RE = /\bt\(\s*['"]([a-zA-Z0-9_.-]+)['"]/g;
const KEY_PROP_RE =
  /\b(?:titleKey|introKey|bodyKey|ctaKey|labelKey|descKey|helpKey|nameKey|descriptionKey|headingKey|subtitleKey|placeholderKey|emptyKey)\s*:\s*['"]([a-zA-Z0-9_.-]+)['"]/g;
const I18N_KEY_RE = /\bi18nKey\s*=\s*['"]([a-zA-Z0-9_.-]+)['"]/g;

function parseLocale(filePath: string): { entries: Map<string, string>; duplicates: string[] } {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const entries = new Map<string, string>();
  const duplicates: string[] = [];
  const lineRx = /^\s*"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$/gm;
  let m: RegExpExecArray | null;
  while ((m = lineRx.exec(raw)) !== null) {
    const [, key, val] = m;
    if (entries.has(key)) duplicates.push(key);
    entries.set(key, val);
  }
  return { entries, duplicates };
}

function parsePtBr() {
  return parseLocale(PT_BR_PATH);
}

function hasPtBrTranslation(
  entries: Map<string, string>,
  enEntries: Map<string, string>,
  key: string,
): boolean {
  const direct = entries.get(key);
  if (direct !== undefined && (direct.trim().length > 0 || enEntries.get(key) === '')) return true;
  const one = entries.get(`${key}_one`);
  const many = entries.get(`${key}_many`);
  const other = entries.get(`${key}_other`);
  return Boolean(one && many && other);
}

function stripComments(source: string): string {
  // Remove block comments (JSDoc/multiline) and full-line // comments without touching URL literals.
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
}

function collectSourceFiles(dir: string, out: string[]): void {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '__tests__' || entry.name === 'locales' || entry.name === 'node_modules') {
      continue;
    }
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectSourceFiles(full, out);
    } else if (
      entry.isFile() &&
      (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) &&
      !entry.name.includes('.test.') &&
      !entry.name.includes('.spec.')
    ) {
      const rel = path.relative(SRC_ROOT, full).replace(/\\/g, '/');
      if (!PRUNED_SOURCE_FILES.has(rel)) {
        out.push(full);
      }
    }
  }
}

describe('Visible keys pt-BR regression test', () => {
  it('has lean profile enabled (SHOW_GUIDED_CASES, SHOW_VIDEOS, SHOW_PROJECT_JOURNEY === false)', () => {
    expect(SHOW_GUIDED_CASES).toBe(false);
    expect(SHOW_VIDEOS).toBe(false);
    expect(SHOW_PROJECT_JOURNEY).toBe(false);
  });

  it('has 100% of baseline-faltando-ptbr.json keys translated in pt-BR.ts with zero duplicates or broken syntax', () => {
    const { entries, duplicates } = parsePtBr();
    expect(duplicates).toEqual([]);
    expect(entries.size).toBeGreaterThan(60000);

    const baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf-8')) as Record<
      string,
      Record<string, string>
    >;
    const baselineKeys = new Set<string>();
    for (const keys of Object.values(baseline)) {
      for (const k of Object.keys(keys)) {
        baselineKeys.add(k);
      }
    }
    expect(baselineKeys.size).toBe(1167);

    const missingBaseline = [...baselineKeys].filter((k) => !entries.has(k));
    expect(missingBaseline).toEqual([]);

    const brokenJsTemplates: string[] = [];
    const brokenDoubleEscapes: string[] = [];
    for (const k of baselineKeys) {
      const val = entries.get(k) ?? '';
      if (/\$\{[^}]+\}/.test(val)) brokenJsTemplates.push(`${k}: ${val}`);
      if (/\\\\n/.test(val)) brokenDoubleEscapes.push(`${k}: ${val}`);
    }
    expect(brokenJsTemplates).toEqual([]);
    expect(brokenDoubleEscapes).toEqual([]);
  });

  it('has all ModuleGuide chrome keys and tasksGuide keys translated in pt-BR.ts', () => {
    const { entries } = parsePtBr();
    const { entries: enEntries } = parseLocale(EN_PATH);
    const requiredGuideKeys = [
      'guide.button',
      'guide.button_aria',
      'guide.eyebrow',
      'guide.step_counter',
      'guide.close',
      'guide.back',
      'guide.next',
      'guide.finish',
      'guide.tasks.title',
      'guide.tasks.intro',
      'guide.tasks.board.title',
      'guide.tasks.board.body',
      'guide.tasks.create.title',
      'guide.tasks.create.body',
      'guide.tasks.types.title',
      'guide.tasks.types.body',
      'guide.tasks.move.title',
      'guide.tasks.move.body',
      'guide.tasks.find.title',
      'guide.tasks.find.body',
      'guide.tasks.io.title',
      'guide.tasks.io.body',
      'guide.tasks.cta',
    ];

    const missing = requiredGuideKeys.filter((k) => !hasPtBrTranslation(entries, enEntries, k));
    expect(missing).toEqual([]);
  });

  it('has 0 untranslated visible keys across all visible product modules and shell', () => {
    const { entries } = parsePtBr();
    const { entries: enEntries } = parseLocale(EN_PATH);

    const scanRoots = [
      path.join(SRC_ROOT, 'app'),
      path.join(SRC_ROOT, 'shared'),
      ...[...PRODUCT_MODULE_IDS].map((id) => path.join(SRC_ROOT, 'modules', id)),
      ...VISIBLE_FEATURE_DIRS.map((d) => path.join(SRC_ROOT, 'features', d)),
    ];

    const files: string[] = [];
    for (const root of scanRoots) {
      collectSourceFiles(root, files);
    }
    expect(files.length).toBeGreaterThan(200);

    const missingKeys = new Set<string>();
    for (const file of files) {
      const clean = stripComments(fs.readFileSync(file, 'utf-8'));
      for (const rx of [T_CALL_RE, KEY_PROP_RE, I18N_KEY_RE]) {
        rx.lastIndex = 0;
        let m: RegExpExecArray | null;
        while ((m = rx.exec(clean)) !== null) {
          const key = m[1];
          if (!key.includes('.') || key.endsWith('.') || key.endsWith('_')) continue;
          if (key.startsWith('product.')) continue;
          if (!hasPtBrTranslation(entries, enEntries, key)) {
            missingKeys.add(`${key} (${path.relative(SRC_ROOT, file)})`);
          }
        }
      }
    }

    expect([...missingKeys].sort()).toEqual([]);
  });
});
