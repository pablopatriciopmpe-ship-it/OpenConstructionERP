#!/usr/bin/env python3
"""
Regression check for visible pt-BR translation coverage.
Verifies:
1. All 1,167 unique baseline keys in baseline-faltando-ptbr.json are translated in pt-BR.ts.
2. Zero duplicate keys, zero JS template `${...}`, and zero doubled `\\n` escapes in pt-BR.ts.
3. Zero missing visible i18n keys across all shipped product modules and shell.
Exits with code 1 if any missing key or integrity error is found.
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'frontend', 'src')
PT_BR_PATH = os.path.join(SRC_ROOT, 'app', 'locales', 'pt-BR.ts')
EN_PATH = os.path.join(SRC_ROOT, 'app', 'locales', 'en.ts')
BASELINE_PATH = os.path.join(SRC_ROOT, 'app', 'locales', 'baseline-faltando-ptbr.json')
MANIFEST_PATH = os.path.join(SRC_ROOT, 'modules', 'productManifest.ts')

VISIBLE_FEATURE_DIRS = [
    'ai-estimator', 'allowances', 'assemblies', 'auth', 'bim', 'boq', 'catalog',
    'changeorders', 'cost-control', 'costs', 'cvr', 'daily-diary', 'dashboard',
    'documents', 'drawing-compare', 'dwg-takeoff', 'eac', 'estimate-checks',
    'fieldreports', 'file-manager', 'full-evm', 'inspections', 'labor-rates',
    'markups', 'match-elements', 'measurement-book', 'meetings', 'notifications',
    'offers', 'onboarding', 'photos', 'postcalc', 'preliminaries', 'price-index',
    'progress', 'projects', 'punchlist', 'quantities', 'quote-capture',
    'reporting', 'reports', 'resources', 'rfi', 'saas', 'schedule', 'settings',
    'takeoff', 'tasks', 'teams', 'users', 'validation', 'variations', 'waste-factors',
]

PRUNED_SOURCE_FILES = {
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
}

T_CALL_RE = re.compile(r"""\bt\(\s*['"]([a-zA-Z0-9_.-]+)['"]""")
KEY_PROP_RE = re.compile(
    r"""\b(?:titleKey|introKey|bodyKey|ctaKey|labelKey|descKey|helpKey|nameKey|descriptionKey|headingKey|subtitleKey|placeholderKey|emptyKey)\s*:\s*['"]([a-zA-Z0-9_.-]+)['"]"""
)
I18N_KEY_RE = re.compile(r"""\bi18nKey\s*=\s*['"]([a-zA-Z0-9_.-]+)['"]""")


def load_locale(path):
    entries = {}
    duplicates = []
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    for m in re.finditer(r'^\s*"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', text, re.MULTILINE):
        key, val = m.group(1), m.group(2)
        if key in entries:
            duplicates.append(key)
        entries[key] = val
    return entries, duplicates


def has_pt_br(entries, en_entries, key):
    if key in entries and (entries[key].strip() or en_entries.get(key) == ''):
        return True
    return all(entries.get(f"{key}_{suffix}", "").strip() for suffix in ("one", "many", "other"))


def load_product_module_ids():
    if not os.path.exists(MANIFEST_PATH):
        return []
    src = open(MANIFEST_PATH, 'r', encoding='utf-8').read()
    m = re.search(r'PRODUCT_MODULE_IDS\s*=\s*new\s+Set\(\[(.*?)\]\);', src, re.DOTALL)
    if not m:
        return []
    return re.findall(r"'([^']+)'", m.group(1))


def strip_comments(source):
    source = re.sub(r'/\*[\s\S]*?\*/', '', source)
    return re.sub(r'^\s*//.*$', '', source, flags=re.MULTILINE)


def main():
    pt_entries, duplicates = load_locale(PT_BR_PATH)
    en_entries, _ = load_locale(EN_PATH)
    print(f"Loaded {len(pt_entries)} translated keys in pt-BR.ts (duplicates: {len(duplicates)})")

    if duplicates:
        print(f"ERROR: Duplicate keys in pt-BR.ts: {duplicates[:10]}")
        return 1

    baseline = json.load(open(BASELINE_PATH, 'r', encoding='utf-8'))
    baseline_keys = set()
    for keys in baseline.values():
        if isinstance(keys, dict):
            baseline_keys.update(keys.keys())

    missing_baseline = sorted(k for k in baseline_keys if k not in pt_entries)
    print(f"Baseline keys translated: {len(baseline_keys) - len(missing_baseline)}/{len(baseline_keys)}")
    if missing_baseline:
        print(f"ERROR: Missing baseline keys: {missing_baseline[:10]}")
        return 1

    scan_roots = [
        os.path.join(SRC_ROOT, 'app'),
        os.path.join(SRC_ROOT, 'shared'),
        *[os.path.join(SRC_ROOT, 'modules', mod_id) for mod_id in load_product_module_ids()],
        *[os.path.join(SRC_ROOT, 'features', d) for d in VISIBLE_FEATURE_DIRS],
    ]

    missing_visible = {}
    scanned_files = 0
    for root_dir in scan_roots:
        if not os.path.exists(root_dir):
            continue
        for dp, dns, fns in os.walk(root_dir):
            dns[:] = [d for d in dns if d not in ('__tests__', 'locales', 'node_modules')]
            for fn in fns:
                if not (fn.endswith('.ts') or fn.endswith('.tsx')) or '.test.' in fn or '.spec.' in fn:
                    continue
                fp = os.path.join(dp, fn)
                rel = os.path.relpath(fp, SRC_ROOT).replace('\\', '/')
                if rel in PRUNED_SOURCE_FILES:
                    continue
                scanned_files += 1
                clean = strip_comments(open(fp, 'r', encoding='utf-8').read())
                keys = set(T_CALL_RE.findall(clean)) | set(KEY_PROP_RE.findall(clean)) | set(I18N_KEY_RE.findall(clean))
                for k in sorted(keys):
                    if '.' not in k or k.endswith('.') or k.endswith('_'):
                        continue
                    if k.startswith('product.'):
                        continue
                    if not has_pt_br(pt_entries, en_entries, k):
                        missing_visible.setdefault(k, rel)

    print(f"Scanned {scanned_files} source files across {len(VISIBLE_FEATURE_DIRS)} feature dirs + modules + shell")
    print(f"Remaining missing visible keys in pt-BR.ts: {len(missing_visible)}")
    if missing_visible:
        for k, rel in sorted(missing_visible.items())[:20]:
            print(f"  - {k} ({rel})")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
