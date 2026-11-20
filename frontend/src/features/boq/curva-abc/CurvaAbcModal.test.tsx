// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CurvaAbcModal } from './CurvaAbcModal';
import type { Position } from '../api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options: Record<string, unknown> = {}) =>
      String(options.defaultValue ?? key).replace(/{{(\w+)}}/g, (_, name) => String(options[name] ?? '')),
  }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ getQueryData: vi.fn(), invalidateQueries: vi.fn() }),
  useQuery: () => ({
    data: {
      total_resources: 2,
      resources: [
        {
          resource_code: 'RES-01',
          name: 'Cimento CP-II',
          type: 'material',
          unit: 'kg',
          total_quantity: 1000,
          avg_unit_rate: 0.8,
          total_cost: 800,
          positions_used: 1,
        },
        {
          resource_code: 'RES-02',
          name: 'Pedreiro',
          type: 'labor',
          unit: 'h',
          total_quantity: 20,
          avg_unit_rate: 25.0,
          total_cost: 500,
          positions_used: 1,
        },
      ],
      by_type: {},
      grand_total: '1300.00',
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('./CurvaAbcChart', () => ({
  CurvaAbcChart: () => <div data-testid="mock-curva-abc-chart">Mock Chart</div>,
}));

vi.mock('./curvaAbcExport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./curvaAbcExport')>();
  return {
    ...actual,
    exportCurvaAbcToExcel: vi.fn().mockResolvedValue(undefined),
    exportCurvaAbcToPdf: vi.fn().mockResolvedValue(undefined),
  };
});

describe('CurvaAbcModal', () => {
  const mockPositions: Position[] = [
    {
      id: 'p-1',
      boq_id: 'b-1',
      parent_id: null,
      ordinal: '01.01',
      description: 'Concreto Estrutural Fck 30 MPa',
      unit: 'm3',
      quantity: 100,
      unit_rate: 450,
      total: 45000,
      classification: {},
      source: 'sinapi',
      confidence: 1,
      sort_order: 1,
      validation_status: 'valid',
    },
    {
      id: 'p-2',
      boq_id: 'b-1',
      parent_id: null,
      ordinal: '01.02',
      description: 'Aço CA-50 10mm',
      unit: 'kg',
      quantity: 1000,
      unit_rate: 8.5,
      total: 8500,
      classification: {},
      source: 'sinapi',
      confidence: 1,
      sort_order: 2,
      validation_status: 'valid',
    },
  ];

  it('renderiza o modal quando aberto com as abas e botões', () => {
    render(
      <CurvaAbcModal
        open={true}
        onClose={vi.fn()}
        boqId="b-1"
        projectName="Edifício Residencial Jardins - São Paulo"
        boqName="Orçamento Sintético"
        positions={mockPositions}
      />,
    );

    expect(screen.getByText('Curva ABC e Análise de Pareto')).toBeDefined();
    expect(screen.getByTestId('curva-abc-tab-services')).toBeDefined();
    expect(screen.getByTestId('curva-abc-tab-resources')).toBeDefined();
    expect(screen.getByTestId('curva-abc-export-excel')).toBeDefined();
    expect(screen.getByTestId('curva-abc-export-pdf')).toBeDefined();
    expect(screen.getByTestId('mock-curva-abc-chart')).toBeDefined();
    expect(screen.getByTestId('curva-abc-table')).toBeDefined();
  });

  it('permite alternar para a visão de insumos', () => {
    render(
      <CurvaAbcModal
        open={true}
        onClose={vi.fn()}
        boqId="b-1"
        projectName="Edifício Residencial Jardins"
        boqName="Orçamento Sintético"
        positions={mockPositions}
      />,
    );

    const resTab = screen.getByTestId('curva-abc-tab-resources');
    fireEvent.click(resTab);

    expect(screen.getByText('Tabela de Insumos da Obra')).toBeDefined();
    expect(screen.getByText('Cimento CP-II')).toBeDefined();
  });

  it('permite ajustar os limites de corte A e B', () => {
    render(
      <CurvaAbcModal
        open={true}
        onClose={vi.fn()}
        boqId="b-1"
        projectName="Edifício Residencial Jardins"
        boqName="Orçamento Sintético"
        positions={mockPositions}
      />,
    );

    const inputA = screen.getByTestId('curva-abc-cutoff-a') as HTMLInputElement;
    fireEvent.change(inputA, { target: { value: '70' } });
    expect(inputA.value).toBe('70');
  });
});
