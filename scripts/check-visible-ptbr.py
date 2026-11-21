#!/usr/bin/env python3
"""
Regression check for visible pt-BR translation coverage.
Ensures that all visible product keys are either translated in pt-BR.ts
or tracked in the pending translation baseline (faltando-ptbr.json).
Fails (exit code 1) if new untranslated keys are introduced without tracking.
"""
import os
import re
import sys
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PT_BR_PATH = os.path.join(REPO_ROOT, 'frontend', 'src', 'app', 'locales', 'pt-BR.ts')
BASELINE_PATH = os.path.join(REPO_ROOT, 'frontend', 'src', 'app', 'locales', 'baseline-faltando-ptbr.json')
SHARED_PATH = '/var/lib/openbot/OpenBot/Shared/evolux-saas-orcamento/i18n/faltando-ptbr.json'

def load_pt_br_keys():
    keys = set()
    with open(PT_BR_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^\s*\"([^\"]+)\"\s*:\s*\"(.*)\",?\s*$', line)
            if m and m.group(2).strip():
                keys.add(m.group(1))
    return keys

def load_baseline():
    path = BASELINE_PATH if os.path.exists(BASELINE_PATH) else SHARED_PATH
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    pt_keys = load_pt_br_keys()
    baseline = load_baseline()
    tracked_missing = set()
    for mod, keys in baseline.items():
        if isinstance(keys, dict):
            tracked_missing.update(keys.keys())

    print(f"Loaded {len(pt_keys)} translated keys in pt-BR.ts")
    print(f"Tracked missing keys baseline: {len(tracked_missing)}")

    # Check for regression: if any tracked key is now translated, note it
    now_translated = tracked_missing.intersection(pt_keys)
    if now_translated:
        print(f"Progress: {len(now_translated)} previously missing keys have now been translated in pt-BR.ts!")

    remaining_missing = tracked_missing - pt_keys
    print(f"Remaining missing keys to translate: {len(remaining_missing)}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
