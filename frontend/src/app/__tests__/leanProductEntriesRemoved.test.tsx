// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  SHOW_GUIDED_CASES,
  SHOW_VIDEOS,
  SHOW_PROJECT_JOURNEY,
} from '@/features/cases/casesConfig';
import { ModuleCasesButton } from '@/features/cases/ModuleCasesButton';
import { ProjectJourneyButton } from '@/app/layout/ProjectJourney';
import { ModuleVideosSlot } from '@/features/videos/ModuleVideosSlot';
import { VideoHint } from '@/features/videos/VideoHint';
import { LearningTipsCard } from '@/features/settings/LearningTipsCard';
import { TopBarCard } from '@/features/settings/TopBarCard';
import { CommandPalette } from '@/shared/ui/CommandPalette';
import { ModuleGuideButton } from '@/shared/ui/ModuleGuideButton';
import { tasksGuide } from '@/features/tasks/tasksGuide';
import ptBrResource from '@/app/locales/pt-BR';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      const dict = ptBrResource.translation;
      let template = dict[key];
      if (!template) {
        template = typeof opts?.defaultValue === 'string' ? opts.defaultValue : key;
      }
      if (!opts) return template;
      return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
        opts[name] !== undefined ? String(opts[name]) : '',
      );
    },
    i18n: { language: 'pt-BR', changeLanguage: vi.fn() },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

vi.mock('@/features/projects/api', () => ({ projectsApi: { list: () => Promise.resolve([]) } }));
vi.mock('@/features/boq/api', () => ({ boqApi: { list: () => Promise.resolve([]) } }));
vi.mock('@/shared/lib/api', () => ({ apiGet: () => Promise.resolve({ hits: [] }) }));

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
  useVideoHintsStore: (
    cb: (state: {
      off: boolean;
      hidden: string[];
      setOff: () => void;
      showAgain: () => void;
    }) => unknown,
  ) => cb({ off: false, hidden: [], setOff: () => {}, showAgain: () => {} }),
}));

describe('Lean and functional product entry points (user decision)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

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

  it('renders null for ModuleVideosSlot ("Aprenda este passo") and VideoHint chips', () => {
    const { container: slotContainer } = render(
      <MemoryRouter initialEntries={['/boq']}>
        <ModuleVideosSlot />
      </MemoryRouter>,
    );
    expect(slotContainer.firstChild).toBeNull();
    expect(screen.queryByText(/Aprenda este passo/i)).toBeNull();
    expect(screen.queryByText(/Learn this step/i)).toBeNull();

    const { container: hintDiary } = render(
      <MemoryRouter initialEntries={['/daily-diary']}>
        <VideoHint topic="daily-diary" />
      </MemoryRouter>,
    );
    expect(hintDiary.firstChild).toBeNull();

    const { container: hintCo } = render(
      <MemoryRouter initialEntries={['/changeorders']}>
        <VideoHint topic="change-order" />
      </MemoryRouter>,
    );
    expect(hintCo.firstChild).toBeNull();
    expect(screen.queryByTestId('video-hint-change-order')).toBeNull();
  });

  it('renders null for LearningTipsCard and hides journey control in TopBarCard', () => {
    const { container } = render(<LearningTipsCard />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId('learning-tips-switch')).toBeNull();

    render(<TopBarCard />);
    expect(screen.queryByTestId('topbar-switch-journey')).toBeNull();
    expect(screen.queryByTestId('topbar-preview-journey')).toBeNull();
    expect(screen.getByTestId('topbar-switch-search')).toBeDefined();
  });

  it('does not show academy or course rows in CommandPalette', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <CommandPalette open onClose={vi.fn()} />
      </MemoryRouter>,
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'clash' } });
    expect(document.querySelectorAll('[data-testid^="palette-row-academy-"]')).toHaveLength(0);

    fireEvent.change(input, { target: { value: 'cost' } });
    expect(document.querySelectorAll('[data-testid^="palette-row-academy-"]')).toHaveLength(0);
  });

  it('keeps "Como funciona" (ModuleGuideButton) translated in pt-BR and visible on Tasks without Casos button', () => {
    render(
      <MemoryRouter initialEntries={['/tasks']}>
        <ModuleGuideButton content={tasksGuide} />
      </MemoryRouter>,
    );

    const guideBtn = screen.getByTestId('module-guide-button');
    expect(guideBtn).toBeDefined();
    expect(guideBtn.textContent).toContain('Como funciona');
    expect(screen.queryByText(/Casos/i)).toBeNull();

    fireEvent.click(guideBtn);

    const card = screen.getByTestId('module-guide-card');
    expect(card.textContent).toContain('Tarefas');
    expect(card.textContent).toContain('O quadro e suas colunas');
    expect(screen.getByTestId('module-guide-counter').textContent).toBe('Conceito 1 de 6');
  });
});
