// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP​‌‍⁠​‌‍⁠​‌‍⁠​‌‍⁠
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
/**
 * "Navigation shortcuts" card in Settings > General: the key after G for each
 * "G then key" chord. Defaults are what the app always had; a key already used
 * by another chord is refused with a message. Kept on this device.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw } from 'lucide-react';
import { Card, CardHeader, CardContent, Button } from '@/shared/ui';
import {
  G_CHORDS,
  chordConflict,
  chordKey,
  gChordPref,
  isChordKey,
  setChordKey,
  type GChord,
} from '@/shared/lib/gChords';
import { navGroups } from '@/app/layout/navCatalog';

/** Excluded modules: support or out-of-product shortcuts (CEO instruction). */
const EXCLUDED_SHORTCUT_ROUTES = new Set(['/tendering', '/finance', '/5d', '/contacts']);

export function ChordShortcutsCard() {
  const { t } = useTranslation();
  const chosen = gChordPref.use();
  const [error, setError] = useState<{ id: string; text: string } | null>(null);

  const visibleChords = useMemo(() => {
    const visibleRoutes = new Set(navGroups.flatMap((group) => group.items.map((item) => item.to)));
    return G_CHORDS.filter(
      (chord) => visibleRoutes.has(chord.route) && !EXCLUDED_SHORTCUT_ROUTES.has(chord.route),
    );
  }, []);

  const visibleChordIds = useMemo(() => new Set(visibleChords.map((c) => c.id)), [visibleChords]);

  const label = (c: GChord) => t(c.labelKey, { defaultValue: c.fallback });

  const onType = (chord: GChord, raw: string) => {
    const key = raw.trim().toLowerCase().slice(-1);
    if (!key) return;
    if (!isChordKey(key)) {
      setError({
        id: chord.id,
        text: t('settings.chords_invalid', { defaultValue: 'Use one letter, digit or comma (not G).' }),
      });
      return;
    }
    const other = chordConflict(chord, key);
    if (other && visibleChordIds.has(other.id)) {
      setError({
        id: chord.id,
        text: t('settings.chords_taken', {
          defaultValue: '{{key}} is already used for {{other}}.',
          key: key.toUpperCase(),
          other: label(other),
        }),
      });
      return;
    }
    setError(null);
    setChordKey(chord, key);
  };

  return (
    <Card>
      <CardHeader
        title={t('settings.chords_title', { defaultValue: 'Navigation shortcuts' })}
        subtitle={t('settings.chords_subtitle', {
          defaultValue: 'Press G, then the key, to jump to a page. Change the key for any page.',
        })}
      />
      <CardContent>
        <ul className="flex flex-col divide-y divide-border-light">
          {visibleChords.map((chord) => {
            const key = chordKey(chord, chosen);
            const changed = key !== chord.key;
            const text = label(chord);
            return (
              <li key={chord.id} className="py-1.5">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm text-content-primary">{text}</span>
                  <span className="flex items-center gap-2">
                    <span className="text-xs text-content-tertiary">G</span>
                    <input
                      value={key.toUpperCase()}
                      maxLength={2}
                      onChange={(e) => onType(chord, e.target.value)}
                      onFocus={(e) => e.currentTarget.select()}
                      aria-label={t('settings.chords_key_for', { defaultValue: 'Key after G for {{page}}', page: text })}
                      className="oe-input w-10 text-center uppercase"
                    />
                    <button
                      type="button"
                      disabled={!changed}
                      onClick={() => {
                        setError(null);
                        setChordKey(chord, chord.key);
                      }}
                      aria-label={t('settings.chords_reset_one', { defaultValue: 'Reset {{page}} to {{key}}', page: text, key: chord.key.toUpperCase() })}
                      title={t('settings.chords_reset_one', { defaultValue: 'Reset {{page}} to {{key}}', page: text, key: chord.key.toUpperCase() })}
                      className="flex h-7 w-7 items-center justify-center rounded-md text-content-secondary hover:bg-surface-secondary disabled:opacity-30"
                    >
                      <RotateCcw size={14} />
                    </button>
                  </span>
                </div>
                {error?.id === chord.id && (
                  <p role="alert" className="mt-1 text-xs text-semantic-error">
                    {error.text}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        <div className="mt-3 flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            disabled={Object.keys(chosen).length === 0}
            onClick={() => {
              setError(null);
              gChordPref.reset();
            }}
          >
            {t('settings.chords_reset_all', { defaultValue: 'Reset all shortcuts' })}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
