import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { REGION_MAP } from '@/stores/useCostDatabaseStore';
import { CatalogPage } from '../CatalogPage';

vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>();
  return {
    ...actual,
    useTranslation: () => ({
      t: (key: string, opts?: { defaultValue?: string }) => {
        const translations: Record<string, string> = {
          'catalog.tab_all': 'Todos',
          'catalog.tab_material': 'Materiais',
          'catalog.tab_equipment': 'Equipamentos',
          'catalog.tab_labor': 'Mão de obra',
          'catalog.tab_operator': 'Operadores',
          'catalog.source_sinapi': 'SINAPI (CAIXA)',
          'catalog.import_region': 'Importar base oficial',
          'catalog.my_catalog': 'Meu Catálogo',
          'catalog.no_series_hint': 'Nenhuma série de índice de preços cadastrada. Sincronize séries oficiais como o INCC-M para reajustes automáticos.',
          'catalog.go_to_price_index': 'Sincronizar INCC-M em Índice de preços',
        };
        if (translations[key]) return translations[key];
        if (opts?.defaultValue) return opts.defaultValue;
        return key;
      },
      i18n: {
        language: 'pt-BR',
      },
    }),
  };
});

// Mock catalog APIs and price-index APIs
vi.mock('../api', () => ({
  fetchCatalogResources: vi.fn().mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    limit: 50,
  }),
  fetchCatalogStats: vi.fn().mockResolvedValue({
    total_resources: 0,
    by_type: { material: 0, equipment: 0, labor: 0, operator: 0 },
    regions_loaded: ['BR_NATIONAL'],
  }),
  createCatalogResource: vi.fn().mockResolvedValue({}),
  adjustCatalogPrices: vi.fn().mockResolvedValue({}),
  importRegionCatalog: vi.fn().mockResolvedValue({}),
  deleteRegionCatalog: vi.fn().mockResolvedValue({}),
  fetchResourceCompositions: vi.fn().mockResolvedValue([]),
}));

vi.mock('@/features/price-index/api', () => ({
  listSeries: vi.fn().mockResolvedValue([]),
  fetchSeries: vi.fn().mockResolvedValue({ points: [] }),
}));

vi.mock('@/stores/useCostDatabaseStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/stores/useCostDatabaseStore')>();
  return {
    ...actual,
    useCostDatabaseStore: () => ({
      installedRegions: ['BR_NATIONAL'],
      activeRegion: 'BR_NATIONAL',
      fetchInstalledRegions: vi.fn(),
      setActiveRegion: vi.fn(),
    }),
  };
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        {ui}
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe('CatalogBrasil — SINAPI 100% Brasil', () => {
  it('defines REGION_MAP with BR_NATIONAL mapped to Brasil (SINAPI)', () => {
    expect(REGION_MAP['BR_NATIONAL']).toBeDefined();
    expect(REGION_MAP['BR_NATIONAL'].name).toBe('Brasil (SINAPI)');
    expect(REGION_MAP['BR_NATIONAL'].currency).toBe('BRL');
    expect(REGION_MAP['BR_NATIONAL'].flag).toBe('br');
    expect(REGION_MAP['BR_NATIONAL'].label).toBe('Brasil — SINAPI (R$)');
  });

  it('renders type tabs in pt-BR: Todos, Materiais, Equipamentos, Mão de obra, Operadores', async () => {
    renderWithClient(<CatalogPage />);
    await waitFor(() => {
      expect(screen.getByText('Todos')).toBeInTheDocument();
      expect(screen.getByText('Materiais')).toBeInTheDocument();
      expect(screen.getByText('Equipamentos')).toBeInTheDocument();
      expect(screen.getByText('Mão de obra')).toBeInTheDocument();
      expect(screen.getByText('Operadores')).toBeInTheDocument();
    });
  });

  it('only exposes BR_NATIONAL in RegionImportGrid without foreign countries', async () => {
    renderWithClient(<CatalogPage />);
    // Foreign countries like DE_BERLIN, FR_PARIS, UK_LONDON must not appear
    expect(screen.queryByText(/Alemanha/i)).toBeNull();
    expect(screen.queryByText(/França/i)).toBeNull();
    expect(screen.queryByText(/Reino Unido/i)).toBeNull();
    expect(screen.queryByText(/Estados Unidos/i)).toBeNull();
  });
});
