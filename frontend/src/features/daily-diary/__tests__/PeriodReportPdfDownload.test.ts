// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { downloadPeriodReportPdf } from '../api';
import * as sharedApi from '@/shared/lib/api';

describe('downloadPeriodReportPdf real contract test', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls /api/v1/daily-diary/period-report/pdf with POST, JSON content-type and handles success', async () => {
    const triggerDownloadSpy = vi.spyOn(sharedApi, 'triggerDownload').mockImplementation(() => {});
    const mockBlob = new Blob(['%PDF-1.4 mock content'], { type: 'application/pdf' });
    const mockHeaders = new Headers({
      'Content-Type': 'application/pdf',
      'Content-Disposition': 'attachment; filename="relatorio-obra-2026-11-16-a-2026-11-20.pdf"',
    });

    const mockResponse = {
      ok: true,
      status: 200,
      headers: mockHeaders,
      blob: vi.fn().mockResolvedValue(mockBlob),
    } as unknown as Response;

    const fetchWithAuthSpy = vi.spyOn(sharedApi, 'fetchWithAuth').mockResolvedValue(mockResponse);

    await downloadPeriodReportPdf({
      project_id: 'proj-123',
      date_from: '2026-11-16',
      date_to: '2026-11-20',
      executive_summary: 'Resumo das obras',
    });

    expect(fetchWithAuthSpy).toHaveBeenCalledTimes(1);
    expect(fetchWithAuthSpy).toHaveBeenCalledWith(
      '/api/v1/daily-diary/period-report/pdf',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/pdf',
        },
        body: JSON.stringify({
          project_id: 'proj-123',
          date_from: '2026-11-16',
          date_to: '2026-11-20',
          executive_summary: 'Resumo das obras',
        }),
      })
    );

    expect(triggerDownloadSpy).toHaveBeenCalledWith(
      mockBlob,
      'relatorio-obra-2026-11-16-a-2026-11-20.pdf'
    );
  });

  it('rejects when response is not ok (non-2xx)', async () => {
    const mockResponse = {
      ok: false,
      status: 422,
      json: vi.fn().mockResolvedValue({ detail: 'Período excede o limite máximo de 90 dias' }),
    } as unknown as Response;

    vi.spyOn(sharedApi, 'fetchWithAuth').mockResolvedValue(mockResponse);

    await expect(
      downloadPeriodReportPdf({
        project_id: 'proj-123',
        date_from: '2026-01-01',
        date_to: '2026-12-31',
        executive_summary: 'Resumo inválido',
      })
    ).rejects.toThrow(/90 dias|Download failed/i);
  });

  it('rejects when response Content-Type is text/html (SPA fallback or error page)', async () => {
    const mockHeaders = new Headers({
      'Content-Type': 'text/html; charset=utf-8',
    });

    const mockResponse = {
      ok: true,
      status: 200,
      headers: mockHeaders,
    } as unknown as Response;

    vi.spyOn(sharedApi, 'fetchWithAuth').mockResolvedValue(mockResponse);

    await expect(
      downloadPeriodReportPdf({
        project_id: 'proj-123',
        date_from: '2026-11-16',
        date_to: '2026-11-20',
        executive_summary: 'Resumo',
      })
    ).rejects.toThrow(/Invalid response content type/i);
  });
});
