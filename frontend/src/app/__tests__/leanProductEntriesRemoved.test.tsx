// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  SHOW_GUIDED_CASES,
  SHOW_VIDEOS,
  SHOW_PROJECT_JOURNEY,
} from '@/features/cases/casesConfig';
import { ModuleCasesButton } from '@/features/cases/ModuleCasesButton';
import { ProjectJourneyButton } from '@/app/layout/ProjectJourney';
import { ModuleVideosSlot } from '@/features/videos/ModuleVideosSlot';
import { LearningTipsCard } from '@/features/settings/LearningTipsCard';
import { ModuleGuideButton } from '@/shared/ui/ModuleGuideButton';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) =>
      (typeof opts?.defaultValue === 'string' ? opts.defaultValue : key),
  }),
}));

vi.mock('@/features/cases/playbookModules', () => ({
  playbooksForRoute: () => [
    {
      id: 'mock-case',
      title: 'Mock Case',
      category: 'estimating',
      stage: 'bidding',
      roles: ['estimator'],
      steps: [],
    },
  ],
}));

vi.mock('@/features/videos/videoRoutes', () => ({
  videoRouteFor: () => '/boq',
  videoCountForRoute: () => 3,
  itemCountForRoute: () => 2,
  useVideoHintsStore: (cb: (state: { off: boolean; hidden: string[]; setOff: () => void; showAgain: () => void }) => unknown) =>
    cb({ off: false, hidden: [], setOff: () => {}, showAgain: () => {} }),
}));

describe('Lean and functional product entry points (user decision)', () => {
  it('has all three lean profile flags disabled', () => {
    expect(SHOW_GUIDED_CASES).toBe(false);
    expect(SHOW_VIDEOS).toBe(false);
    expect(SHOW_PROJECT_JOURNEY).toBe(false);
  });

  it('renders null for ModuleCasesButton ("Casos N" button)', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/boq']}>
        <ModuleCasesButton />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByText(/Casos/i)).toBeNull();
  });

  it('renders null for ProjectJourneyButton ("Jornada do projeto" / "Etapa N")', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/boq']}>
        <ProjectJourneyButton />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId('project-journey-button')).toBeNull();
  });

  it('renders null for ModuleVideosSlot ("Aprenda este passo")', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/boq']}>
        <ModuleVideosSlot />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/Aprenda este passo/i)).toBeNull();
    expect(screen.queryByText(/Learn this step/i)).toBeNull();
  });

  it('renders null for LearningTipsCard in settings', () => {
    const { container } = render(<LearningTipsCard />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId('learning-tips-switch')).toBeNull();
  });

  it('keeps "Como funciona" (ModuleGuideButton) fully functional and visible', () => {
    const mockGuide = {
      titleKey: 'guide.test.title',
      titleDefault: 'Test Guide',
      introKey: 'guide.test.intro',
      introDefault: 'How this module works in 6 concepts.',
      sections: [],
    };

    render(
      <MemoryRouter initialEntries={['/boq']}>
        <ModuleGuideButton content={mockGuide} />
      </MemoryRouter>,
    );

    const guideBtn = screen.getByTestId('module-guide-button');
    expect(guideBtn).toBeDefined();
    expect(guideBtn.textContent).toContain('How it works');
    // Ensure no Casos button was rendered next to it
    expect(screen.queryByText(/Casos/i)).toBeNull();
  });
});
