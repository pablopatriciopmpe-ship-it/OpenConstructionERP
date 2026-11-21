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
  it('has SHOW_GUIDED_CASES set to false per user decision to remove tutorials/cases', () => {
    expect(SHOW_GUIDED_CASES).toBe(false);
  });

  it('renders null when SHOW_GUIDED_CASES is false even if route has playbooks', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/boq']}>
        <ModuleCasesButton />
      </MemoryRouter>,
    );

    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByText(/Casos/i)).toBeNull();
  });
});
