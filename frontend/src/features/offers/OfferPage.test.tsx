import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { OfferPage } from './OfferPage';
import * as api from './api';
import { downloadWithAuth } from '@/shared/lib/api';

vi.mock('@/shared/lib/api', () => ({
  downloadWithAuth: vi.fn().mockResolvedValue(undefined),
  getErrorMessage: vi.fn((e) => String(e)),
}));

const mockOffer: api.Offer = {
  id: 'offer-1',
  group_id: 'grp-1',
  project_id: 'proj-1',
  boq_id: 'boq-1',
  contact_id: 'cust-1',
  number: 'PROP-001',
  revision: 'A',
  title: 'Proposta Comercial Reforma',
  status: 'draft',
  currency: 'BRL',
  customer: { name: 'Empresa Teste Ltda', whatsapp: '(11) 98765-4321' },
  customer_kind: 'business',
  site_same_as_billing: true,
  editable: true,
  locale: 'pt-BR',
  tax_mode: 'standard',
  tax_rate: '0',
  tax_label: 'Sem impostos',
  issue_date: '2026-11-23',
  validity_days: 30,
  valid_until: '2026-12-23',
  payment_days: 15,
  execution_period: '45 dias úteis',
  payment_details: 'PIX: 00.000.000/0001-00',
  reference: 'REF-2026',
  estimate_net: '10000.00',
  markup_presentation: 'spread',
  options: {
    show_pix: true,
    show_acceptance: true,
  },
  totals: {
    net: '10000.00',
    gross: '12000.00',
    tax_total: '0.00',
    rounding_gap: '0.00',
    tax_groups: [],
    not_included: [],
  },
  lines: [
    { kind: 'item', ordinal: '1.1', description: 'Serviço de alvenaria', total: '10000.00' },
  ],
  texts: {
    notes: { source: 'offer', body: 'Observações padrão da proposta', block_id: null },
    exclusions: { source: 'company', body: 'Não inclui taxas de condomínio', block_id: null },
  },
  instalments: [],
  schedule: [],
  retention_percent: '0',
  advance_security: false,
  sent_at: null,
  contract_id: null,
  stale: false,
  updated_at: '2026-11-23T10:00:00Z',
};

const mockSettings: api.OfferSettings = {
  number_pattern: 'PROP-{YYYY}-{NNN}',
  validity_days: 30,
  payment_days: 15,
  markup_presentation: 'spread',
  schedule_templates: [],
  default_schedule: 'standard',
  next_number: '2',
  default_payment_details: 'PIX PADRÃO EMPRESA: 11.222.333/0001-44',
  default_execution_period: '60 dias úteis',
  default_exclusions: 'Exclusões padrão da empresa',
  default_notes: 'Notas padrão da empresa',
};

const patchMutateMock = vi.fn();

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    useOffer: vi.fn(() => ({ data: mockOffer, isLoading: false })),
    useOfferContext: vi.fn(() => ({
      data: {
        offers: [mockOffer],
        client_contact_id: 'cust-1',
        pack: { country: 'BR', consumer_rule: false },
        document_languages: ['pt-BR'],
      },
      isLoading: false,
    })),
    useOfferSettings: vi.fn(() => ({ data: mockSettings, isLoading: false })),
    useOfferValidation: vi.fn(() => ({ data: { findings: [], errors: 0, warnings: 0, can_send: true } })),
    usePatchOffer: vi.fn(() => ({ mutate: patchMutateMock, isPending: false })),
    useOfferAction: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
    useAcceptOffer: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
    useCreateOffer: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
    useResetOfferText: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
    fetchPreview: vi.fn().mockResolvedValue({ pdf_base64: 'JVBERi0xLjQK', page_count: 1, filename: 'proposta.pdf' }),
  };
});

function renderOfferPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/boq/boq-1/offer?project=proj-1']}>
        <Routes>
          <Route path="/boq/:boqId/offer" element={<OfferPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('OfferPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders successfully without reference errors and displays totals matching PDF', async () => {
    renderOfferPage();

    expect(screen.getByText(/PROP-001/)).toBeDefined();
    expect(screen.getByText('Composição Comercial em Tempo Real:')).toBeDefined();
    expect(screen.getByText('Custo Base Técnico (Itens):')).toBeDefined();
    expect(screen.getByText('Valor Final da Proposta:')).toBeDefined();
  });

  it('toggles show_pix and show_acceptance triggering patch on options', async () => {
    renderOfferPage();

    const pixCheckbox = screen.getByLabelText(/Exibir dados de pagamento e PIX/i);
    fireEvent.click(pixCheckbox);

    expect(patchMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({ show_pix: false }),
      }),
      expect.anything()
    );

    const acceptanceCheckbox = screen.getByLabelText(/Incluir campo para aceite e assinatura/i);
    fireEvent.click(acceptanceCheckbox);

    expect(patchMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({ show_acceptance: false }),
      }),
      expect.anything()
    );
  });

  it('restores company default payment details on click', async () => {
    renderOfferPage();

    const restoreBtn = screen.getByTitle('Restaurar dados bancários e PIX padrão da empresa');
    fireEvent.click(restoreBtn);

    expect(patchMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        payment_details: mockSettings.default_payment_details,
      }),
      expect.anything()
    );
  });

  it('triggers downloadWithAuth when clicking header PDF download button', async () => {
    renderOfferPage();

    const pdfSyntheticBtn = screen.getByTitle('Baixar Proposta Sintética (PDF)');
    fireEvent.click(pdfSyntheticBtn);

    await waitFor(() => {
      expect(downloadWithAuth).toHaveBeenCalledWith(
        expect.stringContaining('/v1/offers/offer-1/pdf?mode=synthetic'),
        'PROP-001_sintetica.pdf'
      );
    });
  });
});
