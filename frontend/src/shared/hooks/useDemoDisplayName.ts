import { useTranslation } from 'react-i18next';
import {
  getDemoDisplayName,
  type DemoLocalizableKind,
} from '@/shared/lib/demoLocalizations';

export function useDemoDisplayName() {
  const { i18n } = useTranslation();
  const locale = i18n.language;

  return (
    kind: DemoLocalizableKind,
    raw: string | null | undefined,
  ): string => getDemoDisplayName(kind, raw, locale);
}
