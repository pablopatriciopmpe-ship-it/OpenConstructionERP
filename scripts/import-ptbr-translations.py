#!/usr/bin/env python3
"""
import-ptbr-translations.py

Imports translated keys from /var/lib/openbot/OpenBot/Shared/evolux-saas-orcamento/i18n/traduzido-*.json
into frontend/src/app/locales/pt-BR.ts.

Features:
- Validates that {{placeholder}} variables match between English source and Portuguese translation.
- Validates that HTML tags (e.g. <b>, <span>, <a>) are preserved.
- Preserves line breaks (\n) and proper escaping.
- Supports --dry-run (default: checks and reports stats without modifying file) and --apply (writes to pt-BR.ts).
"""

import os
import sys
import glob
import json
import re
import argparse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PT_BR_PATH = os.path.join(REPO_ROOT, 'frontend', 'src', 'app', 'locales', 'pt-BR.ts')
DEFAULT_TRANSLATED_PATTERN = '/var/lib/openbot/OpenBot/Shared/evolux-saas-orcamento/i18n/traduzido-*.json'
DEFAULT_ORIG_BASELINE = '/var/lib/openbot/OpenBot/Shared/evolux-saas-orcamento/i18n/faltando-ptbr.json'

PLACEHOLDER_RE = re.compile(r'\{\{([a-zA-Z0-9_]+)\}\}')
TAG_RE = re.compile(r'<([a-zA-Z0-9_-]+)[^>]*>')
JS_TEMPLATE_RE = re.compile(r'\$\{[^}]+\}')

def load_json_files(pattern):
    files = sorted(glob.glob(pattern))
    translations = {}
    total_entries = 0
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                # Flatten if grouped by module or direct
                for k, v in data.items():
                    if isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            total_entries += 1
                            translations[sub_k] = str(sub_v)
                    else:
                        total_entries += 1
                        translations[k] = str(v)
    return files, translations, total_entries

def load_english_baseline(baseline_path):
    if not os.path.exists(baseline_path):
        return {}
    with open(baseline_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    baseline = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    baseline[sub_k] = str(sub_v)
            else:
                baseline[k] = str(v)
    return baseline

def validate_placeholders_and_tags(key, en_text, pt_text):
    warnings = []
    if en_text:
        en_placeholders = set(PLACEHOLDER_RE.findall(en_text))
        pt_placeholders = set(PLACEHOLDER_RE.findall(pt_text))
        missing_ph = en_placeholders - pt_placeholders
        if missing_ph:
            warnings.append(f"Chave '{key}': placeholders ausentes em pt-BR: {missing_ph}")

        en_tags = set(TAG_RE.findall(en_text))
        pt_tags = set(TAG_RE.findall(pt_text))
        missing_tags = en_tags - pt_tags
        if missing_tags:
            warnings.append(f"Chave '{key}': tags HTML ausentes em pt-BR: {missing_tags}")

    js_templates = JS_TEMPLATE_RE.findall(pt_text)
    if js_templates:
        warnings.append(f"Chave '{key}': sintaxe template JS ${{...}} detectada (use {{{{...}}}}): {js_templates}")

    return warnings

def escape_ts_string(s):
    # Normalize literal escape sequences from JSON source strings so they do not become double-escaped
    s = s.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r').replace('\\"', '"')
    # Escape backslashes, double quotes, and control whitespace for single-line TS string literals
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\r\n', '\\n').replace('\r', '\\n').replace('\n', '\\n').replace('\t', '\\t')
    return s

def apply_translations_to_pt_br(pt_br_path, new_translations, en_baseline):
    with open(pt_br_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find where the translation dictionary ends
    end_marker_match = re.search(r'(\n\s*(?://[^\n]*\n\s*)*\}\s*\n\}\s*as\s*\{\s*translation)', content)
    if not end_marker_match:
        raise ValueError("Não foi possível localizar o fechamento do objeto 'translation' em pt-BR.ts")

    insert_pos = end_marker_match.start(1)

    # Check which keys already exist in pt-BR.ts
    existing_keys = set(re.findall(r'^\s*\"([^\"]+)\"\s*:', content, re.MULTILINE))

    added_keys = []
    updated_keys = []
    all_warnings = []

    lines_to_append = []

    for key, pt_val in new_translations.items():
        en_val = en_baseline.get(key, '')
        warns = validate_placeholders_and_tags(key, en_val, pt_val)
        if warns:
            all_warnings.extend(warns)

        escaped_val = escape_ts_string(pt_val)
        escaped_key = escape_ts_string(key)

        if key in existing_keys:
            # Replace existing key in place
            pattern = re.compile(r'(\"' + re.escape(key) + r'\"\s*:\s*\")(.*?)(\",?\n)')
            new_content, count = pattern.subn(r'\g<1>' + escaped_val.replace('\\', '\\\\') + r'\g<3>', content)
            if count > 0:
                content = new_content
                updated_keys.append(key)
        else:
            lines_to_append.append(f'    "{escaped_key}": "{escaped_val}",\n')
            added_keys.append(key)

    if lines_to_append:
        content = content[:insert_pos] + '\n    // --- Importado via import-ptbr-translations ---\n' + ''.join(lines_to_append) + content[insert_pos:]

    with open(pt_br_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return added_keys, updated_keys, all_warnings

def main():
    parser = argparse.ArgumentParser(description="Importa traduções traduzido-*.json para pt-BR.ts")
    parser.add_argument('--pattern', default=DEFAULT_TRANSLATED_PATTERN, help="Padrão glob para arquivos traduzidos")
    parser.add_argument('--baseline', default=DEFAULT_ORIG_BASELINE, help="Caminho do baseline de chaves originais em inglês")
    parser.add_argument('--apply', action='store_true', help="Grava alterações diretamente em pt-BR.ts (padrão é dry-run)")
    args = parser.parse_args()

    files, translations, total_entries = load_json_files(args.pattern)
    print(f"Arquivos encontrados ({len(files)}):")
    for f in files:
        print(f"  - {f}")
    print(f"Total de entradas lidas dos arquivos: {total_entries} (chaves únicas: {len(translations)})")

    en_baseline = load_english_baseline(args.baseline)
    print(f"Total de chaves carregadas do baseline em inglês: {len(en_baseline)}")

    # Validation pass
    validation_warnings = []
    for k, v in translations.items():
        w = validate_placeholders_and_tags(k, en_baseline.get(k, ''), v)
        if w:
            validation_warnings.extend(w)

    if validation_warnings:
        print(f"\n[AVISO] {len(validation_warnings)} divergências de placeholder/tags detectadas:")
        for w in validation_warnings[:10]:
            print(f"  - {w}")
        if len(validation_warnings) > 10:
            print(f"  ... e mais {len(validation_warnings) - 10} avisos")
    else:
        print("\n[OK] Todos os placeholders {{...}} e tags HTML foram validados com 100% de integridade.")

    if not args.apply:
        print("\nModo DRY-RUN concluído. Nenhuma alteração gravada em pt-BR.ts.")
        print("Para gravar as alterações no arquivo pt-BR.ts, execute com o parâmetro: --apply")
        return 0

    added, updated, _ = apply_translations_to_pt_br(PT_BR_PATH, translations, en_baseline)
    print(f"\n[SUCESSO] Importação concluída em {PT_BR_PATH}:")
    print(f"  - Chaves novas inseridas: {len(added)}")
    print(f"  - Chaves existentes atualizadas: {len(updated)}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
