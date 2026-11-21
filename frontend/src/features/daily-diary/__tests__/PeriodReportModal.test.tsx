// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PeriodReportModal } from '../PeriodReportModal';
import * as api from '../api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { defaultValue?: string }) => opts?.defaultValue || key,
    i18n: { language: 'pt-BR' },
  }),
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
}));

vi.mock('@/shared/ui/Toast', () => ({
  useToast: () => ({
    show: vi.fn(),
  }),
}));

describe('PeriodReportModal component (v0.4)', () => {
  const mockPreviewResponse: api.PeriodReportPreviewResponse = {
    project_name: 'Obra Teste Aurora',
    period_label: '16/11/2026 a 20/11/2026',
    stats: {
      days_logged: 5,
      entries_count: 2,
      photos_count: 2,
      avg_workforce: 4.5,
      rain_days: 1,
      punchlist_opened: 1,
      punchlist_closed: 0,
      inspections_count: 0,
      tasks_completed: 1,
    },
    days: [
      {
        date: '2026-11-16',
        notes: 'Concretagem',
        workforce: 4,
        weather: {},
        entries: [{ type: 'completion', title: 'Concretagem laje' }],
        photos_count: 1,
      },
    ],
    photos: [
      {
        id: 'photo-1',
        source: 'daily_diary',
        url: '/photos/photo-1.jpg',
        date: '2026-11-16',
        caption: 'Concretagem concluída',
        selected: true,
      },
      {
        id: 'photo-2',
        source: 'photos',
        url: '/photos/photo-2.jpg',
        date: '2026-11-17',
        caption: 'Alvenaria',
        selected: false,
      },
    ],
    executive_summary: 'Resumo das obras na semana.',
    highlights: ['Laje concluída'],
    attention_points: ['Chuva na terça'],
    next_steps: ['Cura do concreto'],
    whatsapp_text: 'Obra Aurora: 5 dias, laje concluída.',
    ai_used: false,
    ai_notice: 'IA sem chave configurada; texto gerado a partir dos registros.',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders period presets and changes dates when selected', () => {
    render(
      <PeriodReportModal
        isOpen={true}
        onClose={vi.fn()}
        projectId="project-123"
      />
    );

    expect(screen.getByTestId('preset-this-week')).toBeDefined();
    expect(screen.getByTestId('preset-last-week')).toBeDefined();
    expect(screen.getByTestId('preset-last-15')).toBeDefined();
    expect(screen.getByTestId('preset-custom')).toBeDefined();

    // Click last 15 days
    fireEvent.click(screen.getByTestId('preset-last-15'));
    const dateFrom = screen.getByTestId('period-report-date-from') as HTMLInputElement;
    const dateTo = screen.getByTestId('period-report-date-to') as HTMLInputElement;
    expect(dateFrom.value).toBeTruthy();
    expect(dateTo.value).toBeTruthy();
  });

  it('calls previewPeriodReport on click and displays preview with AI notice banner when ai_used=false', async () => {
    const previewSpy = vi.spyOn(api, 'previewPeriodReport').mockResolvedValue(mockPreviewResponse);

    render(
      <PeriodReportModal
        isOpen={true}
        onClose={vi.fn()}
        projectId="project-123"
      />
    );

    const generateBtn = screen.getByTestId('generate-preview-btn');
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(previewSpy).toHaveBeenCalledTimes(1);
    });

    // Check AI notice banner
    expect(screen.getByTestId('ai-notice-banner')).toBeDefined();
    expect(screen.getByText(/IA sem chave configurada/i)).toBeDefined();

    // Check stats indicators
    expect(screen.getByTestId('stat-days-logged').textContent).toBe('5');
    expect(screen.getByTestId('stat-avg-workforce').textContent).toBe('4.5');
    expect(screen.getByTestId('stat-photos-count').textContent).toBe('2');
    expect(screen.getByTestId('stat-rain-days').textContent).toBe('1');

    // Check editable fields populated
    const summaryInput = screen.getByTestId('period-report-textarea-summary') as HTMLTextAreaElement;
    expect(summaryInput.value).toBe('Resumo das obras na semana.');
  });

  it('handles photo selection toggle in photo grid', async () => {
    vi.spyOn(api, 'previewPeriodReport').mockResolvedValue(mockPreviewResponse);

    render(
      <PeriodReportModal
        isOpen={true}
        onClose={vi.fn()}
        projectId="project-123"
      />
    );

    fireEvent.click(screen.getByTestId('generate-preview-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('selected-photos-count')).toBeDefined();
    });

    // Initially photo-1 is selected (1 / 2)
    expect(screen.getByTestId('selected-photos-count').textContent).toBe('1 / 2');

    // Toggle photo-2
    const photo2Item = screen.getByTestId('photo-item-photo-2');
    fireEvent.click(photo2Item);
    expect(screen.getByTestId('selected-photos-count').textContent).toBe('2 / 2');

    // Untoggle photo-1
    const photo1Item = screen.getByTestId('photo-item-photo-1');
    fireEvent.click(photo1Item);
    expect(screen.getByTestId('selected-photos-count').textContent).toBe('1 / 2');
  });

  it('copies whatsapp formatted text to clipboard and downloads PDF', async () => {
    vi.spyOn(api, 'previewPeriodReport').mockResolvedValue(mockPreviewResponse);
    const downloadPdfSpy = vi.spyOn(api, 'downloadPeriodReportPdf').mockResolvedValue(undefined);

    // Mock clipboard
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    render(
      <PeriodReportModal
        isOpen={true}
        onClose={vi.fn()}
        projectId="project-123"
      />
    );

    fireEvent.click(screen.getByTestId('generate-preview-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('copy-whatsapp-btn')).toBeDefined();
    });

    // Test WhatsApp copy
    fireEvent.click(screen.getByTestId('copy-whatsapp-btn'));
    expect(writeTextMock).toHaveBeenCalledWith('Obra Aurora: 5 dias, laje concluída.');

    // Test PDF download
    fireEvent.click(screen.getByTestId('download-pdf-btn'));
    await waitFor(() => {
      expect(downloadPdfSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          project_id: 'project-123',
          locale: 'pt-BR',
          include_daily_log: true,
          executive_summary: 'Resumo das obras na semana.',
          selected_photo_ids: ['photo-1'],
        })
      );
    });
  });
});
