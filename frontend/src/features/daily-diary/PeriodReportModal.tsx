// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileText,
  Calendar,
  Sparkles,
  Download,
  Share2,
  Check,
  AlertCircle,
  X,
  Image as ImageIcon,
  Users,
  CloudRain,
  CheckSquare,
  AlertTriangle,
} from 'lucide-react';
import { WideModal } from '@/shared/ui/WideModal';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { useToast } from '@/shared/ui/Toast';
import {
  previewPeriodReport,
  downloadPeriodReportPdf,
  type PeriodReportPreviewResponse,
} from './api';

interface PeriodReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
}

type PeriodPreset = 'this_week' | 'last_week' | 'last_15' | 'custom';
type Audience = 'client' | 'internal';

export const PeriodReportModal: React.FC<PeriodReportModalProps> = ({
  isOpen,
  onClose,
  projectId,
}) => {
  const { t } = useTranslation();
  const toast = useToast();

  // Helper date calculations
  const getPresetDates = (preset: PeriodPreset) => {
    const today = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    const toISO = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

    if (preset === 'this_week') {
      // Monday to Saturday of current week
      const day = today.getDay(); // 0 is Sun, 1 is Mon...
      const monDiff = day === 0 ? -6 : 1 - day;
      const monday = new Date(today);
      monday.setDate(today.getDate() + monDiff);
      const saturday = new Date(monday);
      saturday.setDate(monday.getDate() + 5);
      return { from: toISO(monday), to: toISO(saturday) };
    } else if (preset === 'last_week') {
      const day = today.getDay();
      const lastMonDiff = day === 0 ? -13 : 1 - day - 7;
      const lastMonday = new Date(today);
      lastMonday.setDate(today.getDate() + lastMonDiff);
      const lastSaturday = new Date(lastMonday);
      lastSaturday.setDate(lastMonday.getDate() + 5);
      return { from: toISO(lastMonday), to: toISO(lastSaturday) };
    } else if (preset === 'last_15') {
      const past = new Date(today);
      past.setDate(today.getDate() - 14);
      return { from: toISO(past), to: toISO(today) };
    }
    return { from: toISO(today), to: toISO(today) };
  };

  const initialDates = getPresetDates('this_week');
  const [preset, setPreset] = useState<PeriodPreset>('this_week');
  const [dateFrom, setDateFrom] = useState(initialDates.from);
  const [dateTo, setDateTo] = useState(initialDates.to);
  const [audience, setAudience] = useState<Audience>('client');

  // Inclusions
  const [includePhotos, setIncludePhotos] = useState(true);
  const [includePunchlist, setIncludePunchlist] = useState(true);
  const [includeInspections, setIncludeInspections] = useState(true);
  const [includeTasks, setIncludeTasks] = useState(true);

  // Preview state
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState<PeriodReportPreviewResponse | null>(null);

  // Editable fields
  const [title, setTitle] = useState('');
  const [executiveSummary, setExecutiveSummary] = useState('');
  const [highlights, setHighlights] = useState<string[]>([]);
  const [attentionPoints, setAttentionPoints] = useState<string[]>([]);
  const [nextSteps, setNextSteps] = useState<string[]>([]);
  const [selectedPhotoIds, setSelectedPhotoIds] = useState<string[]>([]);
  const [includeDailyLog, setIncludeDailyLog] = useState(true);

  const applyPreset = (newPreset: PeriodPreset) => {
    setPreset(newPreset);
    if (newPreset !== 'custom') {
      const dates = getPresetDates(newPreset);
      setDateFrom(dates.from);
      setDateTo(dates.to);
    }
  };

  const validateDates = (from: string, to: string) => {
    if (!from || !to) return false;
    const dFrom = new Date(from);
    const dTo = new Date(to);
    if (dFrom > dTo) return false;
    const diffTime = Math.abs(dTo.getTime() - dFrom.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    return diffDays <= 90;
  };

  const handleGeneratePreview = async () => {
    if (!validateDates(dateFrom, dateTo)) {
      toast.show(
        t('period_report.invalid_period', {
          defaultValue: 'Período inválido: verifique as datas e o limite máximo de 90 dias.',
        }),
        'error',
      );
      return;
    }

    setLoading(true);
    try {
      const res = await previewPeriodReport({
        project_id: projectId,
        date_from: dateFrom,
        date_to: dateTo,
        audience,
        include_photos: includePhotos,
        include_punchlist: includePunchlist,
        include_inspections: includeInspections,
        include_tasks: includeTasks,
        use_ai: true,
      });

      setPreview(res);
      setTitle(
        t('period_report.default_title', {
          defaultValue: 'Relatório da obra por período',
        }),
      );
      setExecutiveSummary(res.executive_summary || '');
      setHighlights(res.highlights || []);
      setAttentionPoints(res.attention_points || []);
      setNextSteps(res.next_steps || []);
      setSelectedPhotoIds(res.photos.filter((p) => p.selected).map((p) => p.id));
    } catch (err: any) {
      toast.show(
        err?.message ||
          t('period_report.preview_error', {
            defaultValue: 'Erro ao gerar prévia do relatório.',
          }),
        'error',
      );
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePhoto = (photoId: string) => {
    setSelectedPhotoIds((prev) =>
      prev.includes(photoId) ? prev.filter((id) => id !== photoId) : [...prev, photoId],
    );
  };

  const handleDownloadPdf = async () => {
    if (!preview) return;
    setDownloading(true);
    try {
      await downloadPeriodReportPdf({
        project_id: projectId,
        date_from: dateFrom,
        date_to: dateTo,
        title: title.trim() || undefined,
        executive_summary: executiveSummary,
        highlights,
        attention_points: attentionPoints,
        next_steps: nextSteps,
        selected_photo_ids: selectedPhotoIds,
        include_daily_log: includeDailyLog,
        locale: 'pt-BR',
      });
      toast.show(
        t('period_report.pdf_download_success', {
          defaultValue: 'PDF gerado com sucesso!',
        }),
        'success',
      );
    } catch (err: any) {
      toast.show(
        err?.message ||
          t('period_report.pdf_download_error', {
            defaultValue: 'Erro ao baixar PDF.',
          }),
        'error',
      );
    } finally {
      setDownloading(false);
    }
  };

  const handleCopyWhatsApp = () => {
    if (!preview) return;
    const textToCopy = preview.whatsapp_text || executiveSummary;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    toast.show(
      t('period_report.whatsapp_copied', { defaultValue: 'Copiado!' }),
      'success',
    );
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <WideModal open={isOpen}
      isOpen={isOpen}
      onClose={onClose}
      title={t('period_report.modal_title', {
        defaultValue: 'Relatório da obra por período',
      })}
      size="xl"
    >
      <div className="space-y-6 pb-2" data-testid="period-report-modal">
        {/* Step 1: Configuração do período e opções */}
        <div className="bg-surface-elevated/40 border border-border/60 rounded-xl p-4 sm:p-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-2">
              {t('period_report.period_shortcuts', { defaultValue: 'Período' })}
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => applyPreset('this_week')}
                className={`min-h-[44px] px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  preset === 'this_week'
                    ? 'bg-primary text-white shadow-sm'
                    : 'bg-surface hover:bg-surface-elevated border border-border/80 text-text'
                }`}
                data-testid="preset-this-week"
              >
                {t('period_report.preset_this_week', { defaultValue: 'Esta semana (Seg–Sáb)' })}
              </button>
              <button
                type="button"
                onClick={() => applyPreset('last_week')}
                className={`min-h-[44px] px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  preset === 'last_week'
                    ? 'bg-primary text-white shadow-sm'
                    : 'bg-surface hover:bg-surface-elevated border border-border/80 text-text'
                }`}
                data-testid="preset-last-week"
              >
                {t('period_report.preset_last_week', { defaultValue: 'Semana passada' })}
              </button>
              <button
                type="button"
                onClick={() => applyPreset('last_15')}
                className={`min-h-[44px] px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  preset === 'last_15'
                    ? 'bg-primary text-white shadow-sm'
                    : 'bg-surface hover:bg-surface-elevated border border-border/80 text-text'
                }`}
                data-testid="preset-last-15"
              >
                {t('period_report.preset_last_15', { defaultValue: 'Últimos 15 dias' })}
              </button>
              <button
                type="button"
                onClick={() => setPreset('custom')}
                className={`min-h-[44px] px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  preset === 'custom'
                    ? 'bg-primary text-white shadow-sm'
                    : 'bg-surface hover:bg-surface-elevated border border-border/80 text-text'
                }`}
                data-testid="preset-custom"
              >
                {t('period_report.preset_custom', { defaultValue: 'Personalizado' })}
              </button>
            </div>
          </div>

          {/* Date range inputs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div>
              <label className="text-xs font-medium text-text-muted block mb-1">
                {t('period_report.date_from', { defaultValue: 'De' })}
              </label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPreset('custom');
                }}
                className="w-full min-h-[44px]"
                data-testid="period-report-date-from"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-text-muted block mb-1">
                {t('period_report.date_to', { defaultValue: 'Até (máx. 90 dias)' })}
              </label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPreset('custom');
                }}
                className="w-full min-h-[44px]"
                data-testid="period-report-date-to"
              />
            </div>
          </div>

          {/* Audience and Inclusions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2 border-t border-border/40">
            <div>
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-2">
                {t('period_report.tone_label', { defaultValue: 'Tom do relatório' })}
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setAudience('client')}
                  className={`min-h-[44px] flex-1 py-2 px-3 rounded-lg text-xs font-medium border text-center transition-colors ${
                    audience === 'client'
                      ? 'border-primary bg-primary/10 text-primary font-semibold'
                      : 'border-border bg-surface text-text-muted hover:text-text'
                  }`}
                  data-testid="audience-client"
                >
                  {t('period_report.audience_client', { defaultValue: 'Para o cliente' })}
                </button>
                <button
                  type="button"
                  onClick={() => setAudience('internal')}
                  className={`min-h-[44px] flex-1 py-2 px-3 rounded-lg text-xs font-medium border text-center transition-colors ${
                    audience === 'internal'
                      ? 'border-primary bg-primary/10 text-primary font-semibold'
                      : 'border-border bg-surface text-text-muted hover:text-text'
                  }`}
                  data-testid="audience-internal"
                >
                  {t('period_report.audience_internal', { defaultValue: 'Equipe interna' })}
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-2">
                {t('period_report.include_items', { defaultValue: 'Incluir no resumo' })}
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <label className="flex items-center gap-2 cursor-pointer p-1 min-h-[44px]">
                  <input
                    type="checkbox"
                    checked={includePhotos}
                    onChange={(e) => setIncludePhotos(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>{t('period_report.inc_photos', { defaultValue: 'Fotos' })}</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer p-1 min-h-[44px]">
                  <input
                    type="checkbox"
                    checked={includePunchlist}
                    onChange={(e) => setIncludePunchlist(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>{t('period_report.inc_punchlist', { defaultValue: 'Pendências' })}</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer p-1 min-h-[44px]">
                  <input
                    type="checkbox"
                    checked={includeInspections}
                    onChange={(e) => setIncludeInspections(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>{t('period_report.inc_inspections', { defaultValue: 'Inspeções' })}</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer p-1 min-h-[44px]">
                  <input
                    type="checkbox"
                    checked={includeTasks}
                    onChange={(e) => setIncludeTasks(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>{t('period_report.inc_tasks', { defaultValue: 'Tarefas' })}</span>
                </label>
              </div>
            </div>
          </div>

          {/* Action: Gerar Prévia */}
          <div className="flex justify-end pt-2">
            <Button
              variant="primary"
              className="min-h-[44px] w-full sm:w-auto"
              onClick={handleGeneratePreview}
              disabled={loading}
              data-testid="generate-preview-btn"
            >
              <Sparkles size={16} className={loading ? 'animate-spin' : ''} />
              {loading
                ? t('period_report.generating', { defaultValue: 'Gerando prévia...' })
                : t('period_report.generate_preview', { defaultValue: 'Gerar prévia' })}
            </Button>
          </div>
        </div>

        {/* Step 2: Prévia editável e exportação */}
        {preview && (
          <div className="space-y-5 animate-in fade-in duration-200" data-testid="period-report-preview-section">
            {/* AI notice banner */}
            {!preview.ai_used && preview.ai_notice && (
              <div
                className="bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 p-3 rounded-lg flex items-center gap-2.5 text-xs"
                data-testid="ai-notice-banner"
              >
                <AlertCircle size={16} className="shrink-0" />
                <span>{preview.ai_notice}</span>
              </div>
            )}

            {/* Stats indicators */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="bg-surface border border-border/70 rounded-lg p-3 text-center">
                <span className="text-[11px] text-text-muted block">
                  {t('period_report.stats_days', { defaultValue: 'Dias com registro' })}
                </span>
                <span className="text-lg font-bold text-text mt-0.5 block" data-testid="stat-days-logged">
                  {preview.stats.days_logged}
                </span>
              </div>
              <div className="bg-surface border border-border/70 rounded-lg p-3 text-center">
                <span className="text-[11px] text-text-muted block">
                  {t('period_report.stats_workforce', { defaultValue: 'Efetivo médio' })}
                </span>
                <span className="text-lg font-bold text-text mt-0.5 block" data-testid="stat-avg-workforce">
                  {preview.stats.avg_workforce}
                </span>
              </div>
              <div className="bg-surface border border-border/70 rounded-lg p-3 text-center">
                <span className="text-[11px] text-text-muted block">
                  {t('period_report.stats_photos', { defaultValue: 'Fotos' })}
                </span>
                <span className="text-lg font-bold text-text mt-0.5 block" data-testid="stat-photos-count">
                  {preview.stats.photos_count}
                </span>
              </div>
              <div className="bg-surface border border-border/70 rounded-lg p-3 text-center">
                <span className="text-[11px] text-text-muted block">
                  {t('period_report.stats_rain', { defaultValue: 'Dias de chuva' })}
                </span>
                <span className="text-lg font-bold text-text mt-0.5 block" data-testid="stat-rain-days">
                  {preview.stats.rain_days}
                </span>
              </div>
            </div>

            {/* Editable Title and Executive Summary */}
            <div className="space-y-4 bg-surface rounded-xl border border-border/70 p-4">
              <div>
                <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-1">
                  {t('period_report.report_title', { defaultValue: 'Título do relatório' })}
                </label>
                <Input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full min-h-[44px]"
                  data-testid="period-report-input-title"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-1">
                  {t('period_report.executive_summary', { defaultValue: 'Resumo executivo' })}
                </label>
                <textarea
                  rows={4}
                  value={executiveSummary}
                  onChange={(e) => setExecutiveSummary(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface-elevated/40 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary text-text"
                  data-testid="period-report-textarea-summary"
                />
              </div>

              {/* Highlights */}
              <div>
                <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-1">
                  {t('period_report.highlights', { defaultValue: 'Principais entregas' })}
                </label>
                <textarea
                  rows={3}
                  value={highlights.join('\n')}
                  onChange={(e) => setHighlights(e.target.value.split('\n'))}
                  placeholder={t('period_report.one_per_line', { defaultValue: 'Uma entrega por linha' })}
                  className="w-full rounded-lg border border-border bg-surface-elevated/40 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary text-text"
                  data-testid="period-report-textarea-highlights"
                />
              </div>

              {/* Attention points & Next steps */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-1">
                    {t('period_report.attention_points', { defaultValue: 'Pontos de atenção' })}
                  </label>
                  <textarea
                    rows={3}
                    value={attentionPoints.join('\n')}
                    onChange={(e) => setAttentionPoints(e.target.value.split('\n'))}
                    placeholder={t('period_report.one_per_line', { defaultValue: 'Um ponto por linha' })}
                    className="w-full rounded-lg border border-border bg-surface-elevated/40 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary text-text"
                    data-testid="period-report-textarea-attention"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-1">
                    {t('period_report.next_steps', { defaultValue: 'Próximos passos' })}
                  </label>
                  <textarea
                    rows={3}
                    value={nextSteps.join('\n')}
                    onChange={(e) => setNextSteps(e.target.value.split('\n'))}
                    placeholder={t('period_report.one_per_line', { defaultValue: 'Um passo por linha' })}
                    className="w-full rounded-lg border border-border bg-surface-elevated/40 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary text-text"
                    data-testid="period-report-textarea-nextsteps"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-border/40">
                <label className="flex items-center gap-2 cursor-pointer min-h-[44px]">
                  <input
                    type="checkbox"
                    checked={includeDailyLog}
                    onChange={(e) => setIncludeDailyLog(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                    data-testid="include-daily-log-checkbox"
                  />
                  <span className="text-sm font-medium text-text">
                    {t('period_report.include_daily_log', { defaultValue: 'Incluir resumo dia a dia no PDF' })}
                  </span>
                </label>
              </div>
            </div>

            {/* Photos selection grid */}
            {preview.photos && preview.photos.length > 0 && (
              <div className="bg-surface rounded-xl border border-border/70 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block">
                    {t('period_report.photos_grid_title', {
                      defaultValue: 'Fotos do período (selecione as que entram no PDF)',
                    })}
                  </label>
                  <span className="text-xs text-text-muted" data-testid="selected-photos-count">
                    {selectedPhotoIds.length} / {preview.photos.length}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-64 overflow-y-auto p-1">
                  {preview.photos.map((photo) => {
                    const isSelected = selectedPhotoIds.includes(photo.id);
                    return (
                      <div
                        key={photo.id}
                        onClick={() => handleTogglePhoto(photo.id)}
                        className={`relative rounded-lg border overflow-hidden cursor-pointer group transition-all min-h-[90px] ${
                          isSelected
                            ? 'border-primary ring-2 ring-primary/30 shadow-sm'
                            : 'border-border/60 opacity-60 hover:opacity-100'
                        }`}
                        data-testid={`photo-item-${photo.id}`}
                      >
                        <div className="aspect-video bg-surface-elevated flex items-center justify-center overflow-hidden">
                          {photo.url ? (
                            <img
                              src={photo.url}
                              alt={photo.caption || photo.date}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <ImageIcon className="text-text-muted" size={24} />
                          )}
                        </div>
                        <div className="p-1.5 bg-surface/90 text-[10px] truncate">
                          <span className="font-medium text-text block truncate">
                            {photo.caption || photo.date}
                          </span>
                        </div>
                        <div className="absolute top-1.5 right-1.5">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}} // handled by parent div
                            className="rounded border-border text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                            data-testid={`photo-checkbox-${photo.id}`}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Bottom action buttons: WhatsApp and PDF */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-border/60">
              <Button
                variant="secondary"
                className="min-h-[44px] w-full sm:w-auto"
                onClick={handleCopyWhatsApp}
                data-testid="copy-whatsapp-btn"
              >
                {copied ? (
                  <>
                    <Check size={16} className="text-emerald-500" />
                    {t('period_report.whatsapp_copied', { defaultValue: 'Copiado!' })}
                  </>
                ) : (
                  <>
                    <Share2 size={16} />
                    {t('period_report.copy_whatsapp', { defaultValue: 'Copiar para WhatsApp' })}
                  </>
                )}
              </Button>

              <div className="flex gap-2 w-full sm:w-auto">
                <Button
                  variant="primary"
                  className="min-h-[44px] w-full sm:w-auto"
                  onClick={handleDownloadPdf}
                  disabled={downloading}
                  data-testid="download-pdf-btn"
                >
                  <Download size={16} className={downloading ? 'animate-spin' : ''} />
                  {downloading
                    ? t('period_report.downloading_pdf', { defaultValue: 'Baixando PDF...' })
                    : t('period_report.download_pdf', { defaultValue: 'Baixar PDF' })}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </WideModal>
  );
};
