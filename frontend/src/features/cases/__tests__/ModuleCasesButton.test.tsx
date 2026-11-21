// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ModuleCasesButton } from '../ModuleCasesButton';
import { SHOW_GUIDED_CASES } from '../casesConfig';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) =>
      (typeof opts?.defaultValue === 'string' ? opts.defaultValue : key),
  }),
}));

vi.mock('../playbookModules', () => ({
  playbooksForRoute: (route: string) =>
    route === '/boq'
      ? [
          {
            id: 'mock-case',
            title: 'Mock Case',
            category: 'estimating',
            stage: 'bidding',
            roles: ['estimator'],
            steps: [],
          },
        ]
      : [],
}));

describe('ModuleCasesButton visibility toggle', () => {
  it('has SHOW_GUIDED_CASES set to true per user request', () => {
    expect(SHOW_GUIDED_CASES).toBe(true);
  });

  it('renders cases button on routes that have playbooks', () => {
    render(
      <MemoryRouter initialEntries={['/boq']}>
        <ModuleCasesButton />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button')).toBeDefined();
  });

  it('renders null on routes with no playbooks', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/empty-route']}>
        <ModuleCasesButton />
      </MemoryRouter>,
    );

    expect(container.firstChild).toBeNull();
  });
});
