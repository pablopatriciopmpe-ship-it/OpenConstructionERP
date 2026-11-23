import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ExportHubCards } from './ExportHubCards';

describe('ExportHubCards', () => {
  it('renders commercial client documents and engineering documents cards', () => {
    render(<ExportHubCards offerId="offer-123" boqId="boq-456" projectId="proj-789" />);

    // Central container
    expect(screen.getByTestId('export-hub-cards')).toBeDefined();

    // Client card
    expect(screen.getByText(/Documentos Comerciais/i)).toBeDefined();
    expect(screen.getByText('Proposta Comercial Sintética')).toBeDefined();
    expect(screen.getByText('Proposta Comercial Analítica')).toBeDefined();

    // Engineering card
    expect(screen.getByText(/Engenharia & Financiamento/i)).toBeDefined();
    expect(screen.getByText('Planilha Orçamentária Completa (SINAPI)')).toBeDefined();
    expect(screen.getByText('Curva ABC de Insumos e Serviços')).toBeDefined();
    expect(screen.getByText('Cronograma Físico-Financeiro')).toBeDefined();
  });

  it('renders correct links with query params', () => {
    const { container } = render(<ExportHubCards offerId="offer-999" boqId="boq-888" projectId="proj-777" />);

    const links = Array.from(container.querySelectorAll('a'));
    const hrefs = links.map((l) => l.getAttribute('href') ?? '');

    // Proposta Sintética PDF
    expect(hrefs.some((h) => h.includes('offer-999') && h.includes('pdf') && h.includes('synthetic'))).toBe(true);

    // Proposta Analítica Excel
    expect(hrefs.some((h) => h.includes('offer-999') && h.includes('excel') && h.includes('analytic'))).toBe(true);

    // BOQ Planilha Orçamentária Excel
    expect(hrefs.some((h) => h.includes('boq-888') && h.includes('export/excel'))).toBe(true);
  });
});
