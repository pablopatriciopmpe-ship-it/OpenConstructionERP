import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileText,
  FileSpreadsheet,
  Download,
  Calendar,
  TrendingUp,
  Boxes,
  Users,
  FileDown,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';
import { Card, Badge, Button } from '@/shared/ui';
import { offerPdfUrl, offerExcelUrl } from './api';

interface ExportHubCardsProps {
  offerId?: string;
  boqId?: string;
  projectId?: string;
}

export function ExportHubCards({ offerId, boqId, projectId }: ExportHubCardsProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6" data-testid="export-hub-cards">
      <div>
        <h2 className="text-lg font-bold text-content-primary flex items-center gap-2">
          <Download size={20} className="text-[#156D61]" />
          {t('offers.export_hub_title', { defaultValue: 'Central de Exportações' })}
        </h2>
        <p className="text-xs text-content-secondary mt-0.5">
          {t('offers.export_hub_subtitle', {
            defaultValue: 'Emita relatórios oficiais separados para apresentação ao cliente e aprovação em bancos ou engenharia.',
          })}
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Bloco 1: Documentos para o Cliente */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-content-primary flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#156D61]" />
              Documentos Comerciais (Para o Cliente)
            </h3>
            <Badge variant="neutral" size="sm">Comercial</Badge>
          </div>

          <div className="grid gap-3">
            {/* Card 1: Proposta Sintética */}
            <div className="p-3.5 rounded-xl border border-border-light bg-surface-primary hover:border-[#156D61]/40 transition-all flex items-start justify-between gap-3 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-[#156D61]/10 text-[#156D61] shrink-0 mt-0.5">
                  <FileText size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-content-primary">Proposta Comercial Sintética</h4>
                  <p className="text-[11px] text-content-secondary mt-0.5">
                    Resumo executivo com valores totais, BDI embutido, dados PIX e campo de aceite do cliente.
                  </p>
                </div>
              </div>
              {offerId ? (
                <a
                  href={offerPdfUrl(offerId, 'synthetic')}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="min-h-[44px] px-3 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-[#156D61]/10 hover:text-[#156D61] transition-colors flex items-center gap-1.5 shrink-0"
                >
                  <FileDown size={14} />
                  PDF
                </a>
              ) : (
                <span className="text-[11px] text-content-tertiary shrink-0">Selecione proposta</span>
              )}
            </div>

            {/* Card 2: Proposta Analítica */}
            <div className="p-3.5 rounded-xl border border-border-light bg-surface-primary hover:border-[#156D61]/40 transition-all flex items-start justify-between gap-3 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-[#156D61]/10 text-[#156D61] shrink-0 mt-0.5">
                  <FileText size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-content-primary">Proposta Comercial Analítica</h4>
                  <p className="text-[11px] text-content-secondary mt-0.5">
                    Detalhamento dos serviços por categoria, prazos de execução, composição BDI e garantias.
                  </p>
                </div>
              </div>
              {offerId ? (
                <a
                  href={offerPdfUrl(offerId, 'analytic')}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="min-h-[44px] px-3 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-[#156D61]/10 hover:text-[#156D61] transition-colors flex items-center gap-1.5 shrink-0"
                >
                  <FileDown size={14} />
                  PDF
                </a>
              ) : (
                <span className="text-[11px] text-content-tertiary shrink-0">Selecione proposta</span>
              )}
            </div>

            {/* Card 3: Planilha Excel Comercial */}
            <div className="p-3.5 rounded-xl border border-border-light bg-surface-primary hover:border-emerald-500/40 transition-all flex items-start justify-between gap-3 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 shrink-0 mt-0.5">
                  <FileSpreadsheet size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-content-primary">Planilha Comercial em Excel</h4>
                  <p className="text-[11px] text-content-secondary mt-0.5">
                    Arquivo .xlsx editável com abas Sintética e Analítica para conferência e fórmulas abertas.
                  </p>
                </div>
              </div>
              {offerId ? (
                <div className="flex items-center gap-1 shrink-0">
                  <a
                    href={offerExcelUrl(offerId, 'synthetic')}
                    download
                    className="min-h-[44px] px-2.5 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-emerald-50 hover:text-emerald-700 transition-colors flex items-center gap-1"
                    title="Excel Sintético"
                  >
                    Sint.
                  </a>
                  <a
                    href={offerExcelUrl(offerId, 'analytic')}
                    download
                    className="min-h-[44px] px-2.5 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-emerald-50 hover:text-emerald-700 transition-colors flex items-center gap-1"
                    title="Excel Analítico"
                  >
                    Analít.
                  </a>
                </div>
              ) : (
                <span className="text-[11px] text-content-tertiary shrink-0">Selecione proposta</span>
              )}
            </div>
          </div>
        </div>

        {/* Bloco 2: Documentos de Engenharia & Financiamento Bancário */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-content-primary flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-600" />
              Engenharia & Financiamento (Caixa / Bancos)
            </h3>
            <Badge variant="blue" size="sm">Técnico</Badge>
          </div>

          <div className="grid gap-3">
            {/* Card 4: Planilha Orçamentária SINAPI */}
            <div className="p-3.5 rounded-xl border border-border-light bg-surface-primary hover:border-blue-500/40 transition-all flex items-start justify-between gap-3 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-600 shrink-0 mt-0.5">
                  <FileSpreadsheet size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-content-primary">Planilha Orçamentária Completa (SINAPI)</h4>
                  <p className="text-[11px] text-content-secondary mt-0.5">
                    Discriminação oficial por etapas e códigos SINAPI, atendendo Caixa Econômica e órgãos públicos.
                  </p>
                </div>
              </div>
              {boqId ? (
                <a
                  href={`/api/v1/boq/${boqId}/export/excel`}
                  download
                  className="min-h-[44px] px-3 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-blue-50 hover:text-blue-700 transition-colors flex items-center gap-1.5 shrink-0"
                >
                  <FileSpreadsheet size={14} />
                  Excel
                </a>
              ) : (
                <span className="text-[11px] text-content-tertiary shrink-0">Na obra</span>
              )}
            </div>

            {/* Card 5: Curva ABC */}
            <div className="p-3.5 rounded-xl border border-border-light bg-surface-primary hover:border-blue-500/40 transition-all flex items-start justify-between gap-3 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-600 shrink-0 mt-0.5">
                  <TrendingUp size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-content-primary">Curva ABC de Insumos e Serviços</h4>
                  <p className="text-[11px] text-content-secondary mt-0.5">
                    Classificação dos itens por impacto orçamentário (80/20) para negociação com fornecedores.
                  </p>
                </div>
              </div>
              {boqId ? (
                <a
                  href={`/boq/${boqId}`}
                  className="min-h-[44px] px-3 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-purple-50 hover:text-purple-700 transition-colors flex items-center gap-1.5 shrink-0"
                >
                  <ExternalLink size={14} />
                  Visualizar
                </a>
              ) : (
                <span className="text-[11px] text-content-tertiary shrink-0">Na obra</span>
              )}
            </div>

            {/* Card 6: Cronograma Físico-Financeiro */}
            <div className="p-3.5 rounded-xl border border-border-light bg-surface-primary hover:border-blue-500/40 transition-all flex items-start justify-between gap-3 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-600 shrink-0 mt-0.5">
                  <Calendar size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-content-primary">Cronograma Físico-Financeiro</h4>
                  <p className="text-[11px] text-content-secondary mt-0.5">
                    Previsão de desembolso mensal e evolução física das etapas de obra para medição bancária.
                  </p>
                </div>
              </div>
              {boqId ? (
                <a
                  href={`/boq/${boqId}`}
                  className="min-h-[44px] px-3 py-1.5 text-xs font-medium rounded-lg border border-border-light bg-surface-secondary hover:bg-amber-50 hover:text-amber-700 transition-colors flex items-center gap-1.5 shrink-0"
                >
                  <ExternalLink size={14} />
                  Cronograma
                </a>
              ) : (
                <span className="text-[11px] text-content-tertiary shrink-0">Na obra</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
