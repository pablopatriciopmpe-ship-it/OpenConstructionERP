import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  Plus,
  Search,
  Filter,
  Download,
  FileSpreadsheet,
  FileDown,
  Calendar,
  Clock,
  CheckCircle2,
  Send,
  XCircle,
  Eye,
  Building2,
  ExternalLink,
  MessageCircle,
} from 'lucide-react';
import { useActiveProjectId } from '@/shared/hooks/useActiveProjectId';
import { boqApi } from '@/features/boq/api';
import { useQuery } from '@tanstack/react-query';
import {
  OfferStatus,
  OfferSummary,
  useAllOffers,
  offerPdfUrl,
  offerExcelUrl,
} from './api';
import { Button } from '@/shared/ui/Button';
import { Card } from '@/shared/ui/Card';
import { formatCurrency } from '@/shared/lib/money';
import { downloadWithAuth, getErrorMessage } from '@/shared/lib/api';
import { useToastStore } from '@/stores/useToastStore';
import { ExportHubCards } from './ExportHubCards';

type FilterTab = 'all' | 'draft' | 'sent' | 'accepted' | 'declined';

const STATUS_CONFIG: Record<
  OfferStatus,
  { label: string; bg: string; text: string; icon: React.FC<{ size?: number; className?: string }> }
> = {
  draft: { label: 'Rascunho', bg: 'bg-surface-secondary text-content-secondary border-border-light', text: 'text-content-secondary', icon: Clock },
  sent: { label: 'Enviado', bg: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800', text: 'text-blue-600', icon: Send },
  accepted: { label: 'Aprovado', bg: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800', text: 'text-emerald-600', icon: CheckCircle2 },
  declined: { label: 'Recusado', bg: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800', text: 'text-rose-600', icon: XCircle },
  expired: { label: 'Expirado', bg: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800', text: 'text-amber-600', icon: Clock },
  superseded: { label: 'Substituído', bg: 'bg-surface-secondary text-content-tertiary border-border-light', text: 'text-content-tertiary', icon: Clock },
};

export function OffersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projectId = useActiveProjectId();
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewModal, setShowNewModal] = useState(false);
  const addToast = useToastStore((s) => s.addToast);

  const handleDownload = async (url: string, filename: string) => {
    try {
      await downloadWithAuth(url, filename);
    } catch (err) {
      addToast({
        type: 'error',
        title: t('common.download_failed', { defaultValue: 'Falha no download' }),
        message: getErrorMessage(err),
      });
    }
  };

  // Load all offers so funnel chips always reflect true counts across all statuses
  const offersQuery = useAllOffers(undefined, projectId || undefined);
  const estimatesQuery = useQuery({
    queryKey: ['offer-estimates', projectId],
    queryFn: () => (projectId ? boqApi.list(projectId) : Promise.resolve([])),
    enabled: Boolean(projectId),
  });

  const offers = offersQuery.data ?? [];

  const filteredOffers = useMemo(() => {
    let result = offers;
    if (activeTab !== 'all') {
      result = result.filter((o) => o.status === activeTab);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (o) =>
          o.number.toLowerCase().includes(q) ||
          (o.customer_name && o.customer_name.toLowerCase().includes(q)) ||
          (o.customer_whatsapp && o.customer_whatsapp.toLowerCase().includes(q)) ||
          (o.title && o.title.toLowerCase().includes(q))
      );
    }
    return result;
  }, [offers, activeTab, searchQuery]);

  const tabs: { id: FilterTab; label: string; count?: number }[] = [
    { id: 'all', label: 'Todas as Propostas', count: offers.length },
    { id: 'draft', label: 'Rascunho', count: offers.filter((o) => o.status === 'draft').length },
    { id: 'sent', label: 'Enviadas', count: offers.filter((o) => o.status === 'sent').length },
    { id: 'accepted', label: 'Aprovadas', count: offers.filter((o) => o.status === 'accepted').length },
    { id: 'declined', label: 'Recusadas', count: offers.filter((o) => o.status === 'declined').length },
  ];

  return (
    <div className="space-y-6 p-6 animate-fade-in max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border-light pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-content-primary">
            {t('offers.title', { defaultValue: 'Propostas Comerciais' })}
          </h1>
          <p className="mt-1 text-sm text-content-secondary">
            {t('offers.subtitle', {
              defaultValue: 'Gerencie propostas para clientes com prazos, condições, dados PIX e exportações em PDF e Excel.',
            })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            icon={<Plus size={16} />}
            onClick={() => setShowNewModal(true)}
            data-testid="nova-proposta-btn"
          >
            {t('offers.new_offer', { defaultValue: 'Nova Proposta' })}
          </Button>
        </div>
      </div>

      {/* Funil de Status em Chips Responsivos */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Funil Status Chips */}
        <div className="flex flex-wrap gap-1.5 bg-surface-secondary/70 p-1.5 rounded-xl border border-border-light" role="tablist" aria-label="Funil de status de propostas">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`min-h-[44px] flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                  isActive
                    ? 'bg-surface-elevated text-content-primary shadow-sm font-semibold border border-border-light'
                    : 'text-content-secondary hover:text-content-primary hover:bg-surface-elevated/40'
                }`}
                data-testid={`tab-${tab.id}`}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      isActive
                        ? 'bg-[#156D61] text-white'
                        : 'bg-surface-tertiary text-content-tertiary'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[260px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('offers.search_placeholder', { defaultValue: 'Buscar por cliente, WhatsApp, nº…' })}
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-border-light bg-surface-elevated text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-[#156D61]"
          />
        </div>
      </div>

      {/* Table / List */}
      <Card>
        {offersQuery.isPending ? (
          <div className="p-12 text-center text-sm text-content-secondary">
            {t('offers.loading', { defaultValue: 'Carregando propostas…' })}
          </div>
        ) : filteredOffers.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="inline-flex p-3 rounded-full bg-[#156D61]/10 text-[#156D61]">
              <FileText size={24} />
            </div>
            <h3 className="text-base font-semibold text-content-primary">
              {searchQuery ? 'Nenhuma proposta encontrada' : 'Nenhuma proposta nesta categoria'}
            </h3>
            <p className="text-xs text-content-secondary max-w-md mx-auto">
              {searchQuery
                ? 'Tente ajustar os termos de busca ou remover os filtros aplicados.'
                : 'Crie uma nova proposta comercial a partir de um orçamento de obra para apresentar ao seu cliente.'}
            </p>
            {!searchQuery && (
              <Button variant="secondary" size="sm" onClick={() => setShowNewModal(true)}>
                Criar Proposta
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-border-light bg-surface-secondary/50 text-content-secondary uppercase tracking-wider font-semibold">
                  <th className="py-3 px-4">Número / Rev</th>
                  <th className="py-3 px-4">Cliente / Contato</th>
                  <th className="py-3 px-4">Valor Total</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Emissão / Validade</th>
                  <th className="py-3 px-4 text-right">Ações e Exportações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {filteredOffers.map((o) => {
                  const statusConf = STATUS_CONFIG[o.status] || STATUS_CONFIG.draft;
                  const StatusIcon = statusConf.icon;
                  const editUrl = o.boq_id
                    ? `/boq/${encodeURIComponent(o.boq_id)}/offer?project=${encodeURIComponent(o.project_id)}`
                    : `/projects/${encodeURIComponent(o.project_id)}`;

                  return (
                    <tr key={o.id} className="hover:bg-surface-secondary/40 transition-colors group">
                      {/* Número / Rev */}
                      <td className="py-3.5 px-4 font-medium text-content-primary whitespace-nowrap">
                        <Link
                          to={editUrl}
                          className="text-[#156D61] hover:underline font-semibold flex items-center gap-1.5"
                        >
                          <FileText size={14} className="text-content-tertiary" />
                          <span>{o.number}</span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-surface-secondary text-content-tertiary">
                            Rev {o.revision || 'A'}
                          </span>
                        </Link>
                        {o.title && <div className="text-[11px] text-content-tertiary mt-0.5">{o.title}</div>}
                      </td>

                      {/* Cliente / WhatsApp */}
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-content-primary">
                          {o.customer_name || 'Cliente não definido'}
                        </div>
                        {o.customer_whatsapp && (
                          <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 mt-0.5">
                            <MessageCircle size={12} />
                            <span>{o.customer_whatsapp}</span>
                          </div>
                        )}
                      </td>

                      {/* Valor Total */}
                      <td className="py-3.5 px-4 font-semibold text-content-primary whitespace-nowrap">
                        {formatCurrency(Number(o.gross || 0), o.currency || 'BRL')}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.8 rounded-full text-[11px] font-medium border ${statusConf.bg}`}
                        >
                          <StatusIcon size={12} />
                          {statusConf.label}
                        </span>
                      </td>

                      {/* Emissão / Validade */}
                      <td className="py-3.5 px-4 text-content-secondary whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          <Calendar size={12} className="text-content-tertiary" />
                          <span>{o.issue_date || '—'}</span>
                        </div>
                        {o.valid_until && (
                          <div className="text-[11px] text-content-tertiary mt-0.5">
                            Val: {o.valid_until}
                          </div>
                        )}
                      </td>

                      {/* Ações e Exportações */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Editar / Visualizar */}
                          <Link
                            to={editUrl}
                            className="p-1.5 rounded-lg border border-border-light hover:bg-surface-secondary text-content-secondary hover:text-content-primary transition-colors"
                            title="Editar Proposta"
                          >
                            <Eye size={14} />
                          </Link>

                          {/* Baixar PDF Analítico */}
                          <button
                            type="button"
                            onClick={() => handleDownload(offerPdfUrl(o.id, 'analytic'), `proposta-analitica-${o.number}.pdf`)}
                            className="p-1.5 rounded-lg border border-border-light hover:bg-[#156D61]/10 text-content-secondary hover:text-[#156D61] transition-colors"
                            title="Baixar Proposta Analítica (PDF)"
                          >
                            <FileDown size={14} />
                          </button>

                          {/* Baixar PDF Sintético */}
                          <button
                            type="button"
                            onClick={() => handleDownload(offerPdfUrl(o.id, 'synthetic'), `proposta-sintetica-${o.number}.pdf`)}
                            className="px-1.5 py-1 rounded-lg border border-border-light hover:bg-[#156D61]/10 text-[10px] font-medium text-content-secondary hover:text-[#156D61] transition-colors"
                            title="Baixar Proposta Sintética (PDF)"
                          >
                            PDF Sint.
                          </button>

                          {/* Baixar Excel Analítico */}
                          <button
                            type="button"
                            onClick={() => handleDownload(offerExcelUrl(o.id, 'analytic'), `proposta-analitica-${o.number}.xlsx`)}
                            className="p-1.5 rounded-lg border border-border-light hover:bg-emerald-50 text-content-secondary hover:text-emerald-700 dark:hover:bg-emerald-950/40 transition-colors"
                            title="Baixar Proposta Analítica (Excel)"
                          >
                            <FileSpreadsheet size={14} />
                          </button>

                          {/* Baixar Excel Sintético */}
                          <button
                            type="button"
                            onClick={() => handleDownload(offerExcelUrl(o.id, 'synthetic'), `proposta-sintetica-${o.number}.xlsx`)}
                            className="px-1.5 py-1 rounded-lg border border-border-light hover:bg-emerald-50 text-[10px] font-medium text-content-secondary hover:text-emerald-700 dark:hover:bg-emerald-950/40 transition-colors"
                            title="Baixar Proposta Sintética (Excel)"
                          >
                            XLS Sint.
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Central Visual de Exportações (Export Hub) */}
      <ExportHubCards
        offerId={offers[0]?.id}
        boqId={offers[0]?.boq_id}
        projectId={projectId || undefined}
      />

      {/* Modal / Dialog para criar Nova Proposta a partir de um Orçamento */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl border border-border-light bg-surface-elevated p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-content-primary">Criar Nova Proposta Comercial</h3>
              <button
                onClick={() => setShowNewModal(false)}
                className="text-content-tertiary hover:text-content-primary"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-content-secondary">
              Selecione o orçamento da obra base para gerar a proposta comercial:
            </p>

            {estimatesQuery.isPending ? (
              <p className="text-xs text-content-tertiary">Carregando orçamentos…</p>
            ) : estimatesQuery.data?.length ? (
              <ul className="space-y-2 max-h-64 overflow-y-auto">
                {estimatesQuery.data.map((b) => (
                  <li key={b.id}>
                    <button
                      onClick={() => {
                        setShowNewModal(false);
                        navigate(`/boq/${encodeURIComponent(b.id)}/offer?project=${encodeURIComponent(projectId!)}`);
                      }}
                      className="w-full text-left p-3 rounded-lg border border-border-light hover:border-[#156D61] hover:bg-surface-secondary transition-all flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-semibold text-content-primary">{b.name}</div>
                        <div className="text-[10px] text-content-tertiary">Orçamento da obra</div>
                      </div>
                      <ExternalLink size={14} className="text-content-tertiary" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="p-4 text-center text-xs text-content-secondary">
                Nenhum orçamento encontrado nesta obra.{' '}
                <Link to="/boq" className="text-[#156D61] underline">
                  Criar orçamento
                </Link>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <Button variant="secondary" size="sm" onClick={() => setShowNewModal(false)}>
                Fechar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
