// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
//
// New accounts see the full approved catalogue. A saved choice still wins.

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/useAuthStore';
import {
  hydrateViewModeFromServer,
  useViewModeStore,
  type ViewMode,
} from '@/stores/useViewModeStore';
import { useCompanyPresetKey } from './useCompanyWorkspace';

/** The product default is independent of the company preset. */
export function defaultViewModeFor(presetKey: string | null): ViewMode {
  void presetKey;
  return 'advanced';
}

/** Load the user's stored choice and, while there is none, show the default. */
export function useViewModeDefault(): void {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const userId = useAuthStore((s) => s.userId) ?? null;
  const presetKey = useCompanyPresetKey();
  const chosen = useViewModeStore((s) => s.chosen);
  const applyDefault = useViewModeStore((s) => s.applyDefault);

  useEffect(() => {
    void hydrateViewModeFromServer(isAuthenticated ? userId : null);
  }, [isAuthenticated, userId]);

  useEffect(() => {
    if (!isAuthenticated || chosen) return;
    applyDefault(defaultViewModeFor(presetKey));
  }, [isAuthenticated, chosen, presetKey, applyDefault]);
}
