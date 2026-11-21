// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, expect, it } from 'vitest';
import {
  PRUNED_DASHBOARD_ROUTES,
  isAllowedDashboardUrl,
  buildDashboardSuggestions,
} from '../DashboardPage';
import { navGroups } from '@/app/layout/navCatalog';

describe('dashboard suggestions and onboarding allowlist', () => {
  const visibleRoutes = new Set(navGroups.flatMap((group) => group.items.map((item) => item.to)));
  const fakeT = (key: string, opts?: { defaultValue?: string }) => opts?.defaultValue ?? key;

  it('rejects all pruned and hidden module routes in isAllowedDashboardUrl', () => {
    const prunedList = ['/contacts', '/5d', '/finance', '/tendering', '/gaeb-exchange'];
    for (const pruned of prunedList) {
      expect(PRUNED_DASHBOARD_ROUTES.has(pruned)).toBe(true);
      expect(isAllowedDashboardUrl(pruned, visibleRoutes)).toBe(false);
      expect(isAllowedDashboardUrl(`${pruned}/subpath`, visibleRoutes)).toBe(false);
      expect(isAllowedDashboardUrl(`${pruned}?tab=import`, visibleRoutes)).toBe(false);
    }
  });

  it('allows visible customer navigation routes and standard resource paths', () => {
    expect(isAllowedDashboardUrl('/projects', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/projects/proj-123', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/projects/new', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/boq/boq-456', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/costs/import', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/settings', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/schedule', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/validation', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/templates', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/bim', visibleRoutes)).toBe(true);
    expect(isAllowedDashboardUrl('/costs', visibleRoutes)).toBe(true);
  });

  it('never suggests adding contacts or any pruned module in NextSteps suggestions', () => {
    const scenarios = [
      { name: 'empty state', opts: { projects: [], boqs: [], schedules: [], allContacts: 0 } },
      {
        name: 'has project, no boq',
        opts: {
          projects: [{ id: 'p1', name: 'Project 1' } as any],
          boqs: [],
          schedules: [],
          allContacts: 0,
        },
      },
      {
        name: 'has boq, no positions',
        opts: {
          projects: [{ id: 'p1', name: 'Project 1' } as any],
          boqs: [{ id: 'b1', name: 'BOQ 1', hasPositions: false, hasPricedPositions: false } as any],
          schedules: [],
          allContacts: 0,
        },
      },
      {
        name: 'has positions, no rates',
        opts: {
          projects: [{ id: 'p1', name: 'Project 1' } as any],
          boqs: [{ id: 'b1', name: 'BOQ 1', hasPositions: true, hasPricedPositions: false } as any],
          schedules: [],
          allContacts: 0,
        },
      },
      {
        name: 'has rates, no schedule',
        opts: {
          projects: [{ id: 'p1', name: 'Project 1' } as any],
          boqs: [{ id: 'b1', name: 'BOQ 1', hasPositions: true, hasPricedPositions: true } as any],
          schedules: [],
          allContacts: 0,
        },
      },
      {
        name: 'fully set up project with schedule and contacts',
        opts: {
          projects: [{ id: 'p1', name: 'Project 1' } as any],
          boqs: [{ id: 'b1', name: 'BOQ 1', hasPositions: true, hasPricedPositions: true } as any],
          schedules: [{ id: 's1', name: 'Schedule 1' } as any],
          allContacts: 10,
        },
      },
    ];

    for (const { name, opts } of scenarios) {
      const suggestions = buildDashboardSuggestions(opts, fakeT);
      expect(suggestions.length, `${name} should have at most 3 suggestions`).toBeLessThanOrEqual(3);

      for (const s of suggestions) {
        expect(s.id, `${name}: suggestion id should not be add-contacts`).not.toBe('add-contacts');
        for (const pruned of PRUNED_DASHBOARD_ROUTES) {
          const bare = s.url.split(/[?#]/)[0]!;
          expect(bare === pruned || bare.startsWith(pruned + '/'), `${name}: suggestion ${s.id} url ${s.url} must not target pruned ${pruned}`).toBe(false);
        }
        expect(isAllowedDashboardUrl(s.url, visibleRoutes), `${name}: suggestion ${s.id} url ${s.url} must be allowed`).toBe(true);
      }
    }
  });

  it('guarantees standard onboarding routes only target allowed visible routes', () => {
    const onboardingTargets = [
      '/costs/import',
      '/settings',
      '/projects/new',
      '/projects',
      '/boq/sample-boq-id',
    ];

    for (const target of onboardingTargets) {
      for (const pruned of PRUNED_DASHBOARD_ROUTES) {
        const bare = target.split(/[?#]/)[0]!;
        expect(bare === pruned || bare.startsWith(pruned + '/')).toBe(false);
      }
      expect(isAllowedDashboardUrl(target, visibleRoutes)).toBe(true);
    }
  });
});
