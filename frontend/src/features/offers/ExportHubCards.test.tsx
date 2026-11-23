import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ExportHubCards } from './ExportHubCards';
import { downloadWithAuth } from '@/shared/lib/api';

vi.mock('@/shared/lib/api', () => ({
  downloadWithAuth: vi.fn().mockResolvedValue(undefined),
  getErrorMessage: vi.fn((e) => String(e)),
}));

describe('ExportHubCards', () => {
  it('renders commercial client documents and engineering documents cards', () => {
    render(
      <MemoryRouter>
        <ExportHubCards offerId="offer-123" boqId="boq-456" projectId="proj-789" />
      </MemoryRouter>
    );

    expect(screen.getByTestId('export-hub-cards')).toBeDefined();
    expect(screen.getByText(/Documentos Comerciais/i)).toBeDefined();
    expect(screen.getByText('Proposta Comercial Sintética')).toBeDefined();
    expect(screen.getByText('Proposta Comercial Analítica')).toBeDefined();
    expect(screen.getByText(/Engenharia & Financiamento/i)).toBeDefined();
    expect(screen.getByText('Planilha Orçamentária Completa (SINAPI)')).toBeDefined();
    expect(screen.getByText('Curva ABC de Insumos e Serviços')).toBeDefined();
    expect(screen.getByText('Cronograma Físico-Financeiro')).toBeDefined();
  });

  it('triggers downloadWithAuth with correct routes including /boqs/ for BOQ export', async () => {
    render(
      <MemoryRouter>
        <ExportHubCards offerId="offer-999" boqId="boq-888" projectId="proj-777" />
      </MemoryRouter>
    );

    // Click BOQ Excel download
    const excelBtns = screen.getAllByRole('button', { name: /Excel/i });
    const boqExcelBtn = excelBtns[excelBtns.length - 1];
    fireEvent.click(boqExcelBtn);

    await waitFor(() => {
      expect(downloadWithAuth).toHaveBeenCalledWith(
        '/api/v1/boq/boqs/boq-888/export/excel',
        'orcamento-boq-888.xlsx'
      );
    });

    // Click Synthetic PDF
    const pdfBtns = screen.getAllByRole('button', { name: /PDF/i });
    fireEvent.click(pdfBtns[0]);

    await waitFor(() => {
      expect(downloadWithAuth).toHaveBeenCalledWith(
        expect.stringContaining('/v1/offers/offer-999/pdf?mode=synthetic'),
        expect.stringContaining('proposta-sintetica-offer-99.pdf')
      );
    });
  });

  it('renders router Links for BOQ navigation without full page reload', () => {
    render(
      <MemoryRouter>
        <ExportHubCards offerId="offer-123" boqId="boq-456" projectId="proj-789" />
      </MemoryRouter>
    );

    const visualLink = screen.getByRole('link', { name: /Visualizar/i });
    expect(visualLink.getAttribute('href')).toBe('/boq/boq-456');

    const cronogramaLink = screen.getByRole('link', { name: /Cronograma/i });
    expect(cronogramaLink.getAttribute('href')).toBe('/boq/boq-456');
  });
});
