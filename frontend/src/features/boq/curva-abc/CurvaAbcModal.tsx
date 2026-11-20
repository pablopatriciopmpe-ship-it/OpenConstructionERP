// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  X,
  FileSpreadsheet,
  FileDown,
  Layers,
  Package,
  RotateCcw,
  Search,
  Filter,
} from 'lucide-react';
import { Button, WideModal } from '@/shared/ui';
import { boqApi, isSection, type Position } from '../api';
import {
  calculateCurvaAbc,
  getCategoriaLabel,
  type CurvaAbcItem,
  type RawCurvaAbcInput,
} from './curvaAbcCalculations';
import { CurvaAbcChart } from './CurvaAbcChart';
import {
  exportCurvaAbcToExcel,
  exportCurvaAbcToPdf,
  formatMoneyPtBr,
  formatPercentPtBr,
} from './curvaAbcExport';

export interface CurvaAbcModalProps {
  open: boolean;
  onClose: () => void;
  boqId: string;
  projectName?: string;
  boqName?: string;
  positions?: Position[];
  readOnly?: boolean;
}

type TabVision = 'services' | 'resources';

export function CurvaAbcModal({
  open,
  onClose,
  boqId,
  projectName = 'Projeto',
  boqName = 'Planilha Orçamentária',
  positions = [],
}: CurvaAbcModalProps) {
  const [activeTab, setActiveTab] = useState<TabVision>('services');
  const [cutoffA, setCutoffA] = useState<number>(80);
  const [cutoffB, setCutoffB] = useState<number>(95);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>('all');
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  // Carrega insumos agregados do backend
  const { data: resourceData, isLoading: isLoadingResources } = useQuery({
    queryKey: ['boq-resource-summary', boqId],
    queryFn: () => boqApi.getResourceSummary(boqId),
    enabled: open && Boolean(boqId),
    staleTime: 60_000,
  });

  // ── 1. Preparação dos Serviços e Etapas da Planilha ─────────────────────────
  const servicesInputs = useMemo<RawCurvaAbcInput[]>(() => {
    if (!positions || positions.length === 0) return [];
    return positions
      .filter((p) => {
        // Ignora cabeçalhos de seção puros sem quantidade ou taxa
        if (isSection(p) && !Number(p.quantity) && !Number(p.unit_rate)) {
          return false;
        }
        return true;
      })
      .map((p) => {
        const qty = Number(p.quantity) || 0;
        const rate = Number(p.unit_rate) || 0;
        const total = Number(p.total) || qty * rate;
        return {
          id: p.id,
          code: p.ordinal || '',
          description: p.description || '',
          unit: p.unit || 'un',
          quantity: qty,
          unit_rate: rate,
          total_cost: total,
        };
      });
  }, [positions]);

  // ── 2. Preparação dos Insumos da Planilha ──────────────────────────────────
  const resourcesInputs = useMemo<RawCurvaAbcInput[]>(() => {
    if (!resourceData?.resources || resourceData.resources.length === 0) {
      return [];
    }
    return resourceData.resources.map((r, idx) => ({
      id: r.resource_code || `res-${idx}`,
      code: r.resource_code || String(idx + 1).padStart(2, '0'),
      description: r.name || 'Insumo',
      unit: r.unit || 'un',
      quantity: Number(r.total_quantity) || 0,
      unit_rate: Number(r.avg_unit_rate) || 0,
      total_cost: Number(r.total_cost) || 0,
      category: r.type || 'other',
    }));
  }, [resourceData]);

  // ── 3. Cálculos de Curva ABC ────────────────────────────────────────────────
  const servicesResult = useMemo(
    () => calculateCurvaAbc(servicesInputs, cutoffA, cutoffB),
    [servicesInputs, cutoffA, cutoffB],
  );

  const resourcesResult = useMemo(
    () => calculateCurvaAbc(resourcesInputs, cutoffA, cutoffB),
    [resourcesInputs, cutoffA, cutoffB],
  );

  const activeResult = activeTab === 'services' ? servicesResult : resourcesResult;

  // ── 4. Filtros de Tabela ───────────────────────────────────────────────────
  const filteredItems = useMemo(() => {
    let list = activeResult.items;

    if (activeTab === 'resources' && resourceTypeFilter !== 'all') {
      list = list.filter((item) => (item.category || '').toLowerCase() === resourceTypeFilter.toLowerCase());
    }

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase().trim();
      list = list.filter(
        (item) =>
          item.description.toLowerCase().includes(q) ||
          item.code.toLowerCase().includes(q) ||
          (item.category && item.category.toLowerCase().includes(q)),
      );
    }

    return list;
  }, [activeResult.items, activeTab, resourceTypeFilter, searchTerm]);

  // ── 5. Ações de Exportação ─────────────────────────────────────────────────
  const handleExportExcel = async () => {
    try {
      setIsExportingExcel(true);
      await exportCurvaAbcToExcel({
        projectName,
        boqName,
        servicesResult,
        resourcesResult,
        date: new Date(),
      });
    } finally {
      setIsExportingExcel(false);
    }
  };

  const handleExportPdf = async () => {
    try {
      setIsExportingPdf(true);
      await exportCurvaAbcToPdf({
        projectName,
        boqName,
        servicesResult,
        resourcesResult,
        date: new Date(),
      });
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleResetCutoffs = () => {
    setCutoffA(80);
    setCutoffB(95);
  };

  return (
    <WideModal open={open} onClose={onClose} size="full">
      <div className="flex flex-col h-[calc(100vh-5rem)] max-h-[920px] text-content-primary">
        {/* ── Topo do Modal ─────────────────────────────────────────────────── */}
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#CED8D5] pb-4 px-1">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-[#163953]">Curva ABC e Análise de Pareto</h2>
              <span className="inline-block rounded-md bg-[#156D61]/10 px-2 py-0.5 text-xs font-semibold text-[#156D61]">
                Evolux Obras
              </span>
            </div>
            <p className="text-xs text-[#465C69] mt-0.5">
              <strong className="text-[#163953]">{projectName}</strong> · {boqName} ·{' '}
              <span>Total: <strong className="text-[#156D61]">{formatMoneyPtBr(servicesResult.grand_total)}</strong></span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<FileSpreadsheet size={16} className="text-[#156D61]" />}
              onClick={handleExportExcel}
              loading={isExportingExcel}
              title="Baixar planilha Excel com 3 abas: Resumo, Categorias e Serviços"
              data-testid="curva-abc-export-excel"
            >
              Exportar Excel (.xlsx)
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<FileDown size={16} className="text-[#163953]" />}
              onClick={handleExportPdf}
              loading={isExportingPdf}
              title="Baixar relatório em PDF com as 3 visões em pt-BR"
              data-testid="curva-abc-export-pdf"
            >
              Exportar PDF
            </Button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-[#465C69] hover:bg-[#F6F6EF] hover:text-[#163953] transition-colors"
              aria-label="Fechar"
            >
              <X size={20} />
            </button>
          </div>
        </header>

        {/* ── Barra de Navegação e Configurações ─────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3 py-3 border-b border-[#CED8D5]/60 bg-[#F6F6EF]/40 px-1">
          {/* Seletor de Visões */}
          <div className="flex items-center gap-1.5 rounded-lg border border-[#CED8D5] p-1 bg-white">
            <button
              type="button"
              onClick={() => setActiveTab('services')}
              data-testid="curva-abc-tab-services"
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeTab === 'services'
                  ? 'bg-[#156D61] text-white shadow-xs'
                  : 'text-[#465C69] hover:text-[#163953] hover:bg-[#F6F6EF]'
              }`}
            >
              <Layers size={14} />
              <span>Por Serviços e Etapas</span>
              <span className={`ml-1 rounded px-1.5 py-0.2 text-2xs ${
                activeTab === 'services' ? 'bg-white/20 text-white' : 'bg-[#F6F6EF] text-[#465C69]'
              }`}>
                {servicesResult.total_count}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('resources')}
              data-testid="curva-abc-tab-resources"
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeTab === 'resources'
                  ? 'bg-[#156D61] text-white shadow-xs'
                  : 'text-[#465C69] hover:text-[#163953] hover:bg-[#F6F6EF]'
              }`}
            >
              <Package size={14} />
              <span>Por Insumos e Categorias</span>
              <span className={`ml-1 rounded px-1.5 py-0.2 text-2xs ${
                activeTab === 'resources' ? 'bg-white/20 text-white' : 'bg-[#F6F6EF] text-[#465C69]'
              }`}>
                {resourcesResult.total_count}
              </span>
            </button>
          </div>

          {/* Configuração de Limites ABC */}
          <div className="flex items-center gap-2 text-xs text-[#465C69] bg-white border border-[#CED8D5] rounded-lg px-3 py-1.5">
            <span className="font-medium text-[#163953]">Limites de Corte:</span>
            <label className="flex items-center gap-1">
              <span className="font-semibold text-[#12594D]">Classe A:</span>
              <input
                type="number"
                min="1"
                max="98"
                value={cutoffA}
                onChange={(e) => setCutoffA(Number(e.target.value) || 80)}
                className="w-12 rounded border border-[#CED8D5] px-1.5 py-0.5 text-center text-xs font-semibold text-[#163953] focus:border-[#156D61] focus:outline-none"
                data-testid="curva-abc-cutoff-a"
              />
              <span>%</span>
            </label>
            <span className="text-[#CED8D5]">|</span>
            <label className="flex items-center gap-1">
              <span className="font-semibold text-[#163953]">Classe B:</span>
              <input
                type="number"
                min={cutoffA + 1}
                max="99"
                value={cutoffB}
                onChange={(e) => setCutoffB(Number(e.target.value) || 95)}
                className="w-12 rounded border border-[#CED8D5] px-1.5 py-0.5 text-center text-xs font-semibold text-[#163953] focus:border-[#156D61] focus:outline-none"
                data-testid="curva-abc-cutoff-b"
              />
              <span>%</span>
            </label>
            {(cutoffA !== 80 || cutoffB !== 95) && (
              <button
                type="button"
                onClick={handleResetCutoffs}
                className="ml-1 inline-flex items-center gap-1 text-2xs text-[#156D61] hover:underline"
                title="Restaurar padrão 80/95"
              >
                <RotateCcw size={12} />
                <span>Padrão</span>
              </button>
            )}
          </div>
        </div>

        {/* ── Conteúdo Rolável ──────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto space-y-4 py-3 px-1">
          {/* Cards de Resumo (KPIs) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Total Geral */}
            <div className="rounded-xl border border-[#CED8D5] bg-white p-3.5 shadow-xs">
              <span className="text-2xs font-semibold uppercase tracking-wider text-[#465C69]">Total do Orçamento</span>
              <div className="text-lg font-bold text-[#163953] mt-1">
                {formatMoneyPtBr(activeResult.grand_total)}
              </div>
              <div className="text-2xs text-[#465C69] mt-0.5">
                {activeResult.total_count} itens · 100% da planilha
              </div>
            </div>

            {/* Classe A */}
            <div className="rounded-xl border border-[#156D61]/40 bg-[#E2F2EC]/60 p-3.5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-2xs font-bold uppercase tracking-wider text-[#12594D]">Classe A (Até {cutoffA}%)</span>
                <span className="rounded bg-[#12594D]/15 px-1.5 py-0.2 text-2xs font-bold text-[#12594D]">
                  {formatPercentPtBr(activeResult.summary.A.percentage)}
                </span>
              </div>
              <div className="text-lg font-bold text-[#12594D] mt-1">
                {formatMoneyPtBr(activeResult.summary.A.total)}
              </div>
              <div className="text-2xs text-[#12594D]/80 mt-0.5">
                {activeResult.summary.A.count} itens ({formatPercentPtBr((activeResult.summary.A.count / (activeResult.total_count || 1)) * 100)} dos itens)
              </div>
            </div>

            {/* Classe B */}
            <div className="rounded-xl border border-[#163953]/30 bg-[#DCEEE9]/60 p-3.5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-2xs font-bold uppercase tracking-wider text-[#163953]">Classe B ({cutoffA}% a {cutoffB}%)</span>
                <span className="rounded bg-[#163953]/15 px-1.5 py-0.2 text-2xs font-bold text-[#163953]">
                  {formatPercentPtBr(activeResult.summary.B.percentage)}
                </span>
              </div>
              <div className="text-lg font-bold text-[#163953] mt-1">
                {formatMoneyPtBr(activeResult.summary.B.total)}
              </div>
              <div className="text-2xs text-[#163953]/80 mt-0.5">
                {activeResult.summary.B.count} itens ({formatPercentPtBr((activeResult.summary.B.count / (activeResult.total_count || 1)) * 100)} dos itens)
              </div>
            </div>

            {/* Classe C */}
            <div className="rounded-xl border border-[#CED8D5] bg-[#F6F6EF]/70 p-3.5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-2xs font-bold uppercase tracking-wider text-[#465C69]">Classe C (Acima de {cutoffB}%)</span>
                <span className="rounded bg-[#465C69]/15 px-1.5 py-0.2 text-2xs font-bold text-[#465C69]">
                  {formatPercentPtBr(activeResult.summary.C.percentage)}
                </span>
              </div>
              <div className="text-lg font-bold text-[#465C69] mt-1">
                {formatMoneyPtBr(activeResult.summary.C.total)}
              </div>
              <div className="text-2xs text-[#465C69]/80 mt-0.5">
                {activeResult.summary.C.count} itens ({formatPercentPtBr((activeResult.summary.C.count / (activeResult.total_count || 1)) * 100)} dos itens)
              </div>
            </div>
          </div>

          {/* Gráfico de Pareto */}
          <CurvaAbcChart
            items={activeResult.items}
            cutoffA={cutoffA}
            cutoffB={cutoffB}
          />

          {/* ── Tabela da Curva ABC ────────────────────────────────────────── */}
          <div className="rounded-xl border border-[#CED8D5] bg-white shadow-sm overflow-hidden">
            {/* Barra de Filtros da Tabela */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 border-b border-[#CED8D5] bg-[#F6F6EF]/30">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-[#163953]">
                  {activeTab === 'services' ? 'Tabela de Serviços e Etapas' : 'Tabela de Insumos da Obra'}
                </h4>
                <span className="text-xs text-[#465C69]">({filteredItems.length} exibidos)</span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Filtro por tipo de insumo (apenas na aba de insumos) */}
                {activeTab === 'resources' && (
                  <div className="flex items-center gap-1 text-xs">
                    <Filter size={14} className="text-[#465C69]" />
                    <select
                      value={resourceTypeFilter}
                      onChange={(e) => setResourceTypeFilter(e.target.value)}
                      className="rounded-md border border-[#CED8D5] bg-white px-2 py-1 text-xs text-[#163953] focus:border-[#156D61] focus:outline-none"
                    >
                      <option value="all">Todas as Categorias</option>
                      <option value="material">Materiais</option>
                      <option value="labor">Mão de Obra</option>
                      <option value="equipment">Equipamentos</option>
                      <option value="subcontractor">Terceirizados</option>
                      <option value="other">Outros</option>
                    </select>
                  </div>
                )}

                {/* Campo de Busca Rápida */}
                <div className="relative">
                  <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#465C69]" />
                  <input
                    type="text"
                    placeholder="Filtrar item ou código..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-48 sm:w-64 rounded-md border border-[#CED8D5] pl-8 pr-2.5 py-1 text-xs text-[#163953] placeholder:text-[#465C69]/60 focus:border-[#156D61] focus:outline-none"
                  />
                  {searchTerm && (
                    <button
                      type="button"
                      onClick={() => setSearchTerm('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-2xs text-[#465C69] hover:text-[#163953]"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Grid da Tabela */}
            <div className="overflow-x-auto max-h-[460px]">
              <table className="w-full border-collapse text-left text-xs" data-testid="curva-abc-table">
                <thead className="sticky top-0 z-10 bg-[#163953] text-white">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold text-center w-12">#</th>
                    <th className="py-2.5 px-3 font-semibold text-center w-16">Classe</th>
                    <th className="py-2.5 px-3 font-semibold w-24">Código</th>
                    <th className="py-2.5 px-3 font-semibold min-w-[200px]">
                      {activeTab === 'services' ? 'Descrição do Serviço' : 'Descrição do Insumo'}
                    </th>
                    {activeTab === 'resources' && (
                      <th className="py-2.5 px-3 font-semibold w-32">Categoria</th>
                    )}
                    <th className="py-2.5 px-3 font-semibold text-center w-14">Unid.</th>
                    <th className="py-2.5 px-3 font-semibold text-right w-24">Qtd.</th>
                    <th className="py-2.5 px-3 font-semibold text-right w-28">Preço Unit.</th>
                    <th className="py-2.5 px-3 font-semibold text-right w-32">Valor Total</th>
                    <th className="py-2.5 px-3 font-semibold text-right w-24">% Indiv.</th>
                    <th className="py-2.5 px-3 font-semibold text-right w-24">% Acum.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#CED8D5]/60 bg-white">
                  {isLoadingResources && activeTab === 'resources' ? (
                    <tr>
                      <td colSpan={11} className="py-12 text-center text-[#465C69]">
                        Carregando insumos da obra...
                      </td>
                    </tr>
                  ) : filteredItems.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="py-12 text-center text-[#465C69]">
                        Nenhum registro encontrado para os critérios selecionados.
                      </td>
                    </tr>
                  ) : (
                    filteredItems.map((item, idx) => {
                      // Verifica se deve renderizar a linha de corte
                      const prevItem = idx > 0 ? filteredItems[idx - 1] : null;
                      const showCutA = prevItem && prevItem.abc_class === 'A' && item.abc_class !== 'A';
                      const showCutB = prevItem && prevItem.abc_class === 'B' && item.abc_class === 'C';

                      const badgeStyle =
                        item.abc_class === 'A'
                          ? 'bg-[#E2F2EC] text-[#12594D] border-[#156D61]/30 font-bold'
                          : item.abc_class === 'B'
                          ? 'bg-[#DCEEE9] text-[#163953] border-[#163953]/30 font-bold'
                          : 'bg-[#F6F6EF] text-[#465C69] border-[#CED8D5] font-semibold';

                      return (
                        <React.Fragment key={item.id}>
                          {/* Linha de Corte Classe A */}
                          {showCutA && (
                            <tr className="bg-[#E2F2EC]/80 border-y-2 border-[#156D61]" data-testid="curva-abc-divider-a">
                              <td colSpan={11} className="py-1 px-4 text-xs font-bold text-[#12594D] tracking-wide">
                                ━━━ LIMITE CLASSE A ({cutoffA}%) ━━━
                              </td>
                            </tr>
                          )}

                          {/* Linha de Corte Classe B */}
                          {showCutB && (
                            <tr className="bg-[#DCEEE9]/80 border-y-2 border-[#163953]" data-testid="curva-abc-divider-b">
                              <td colSpan={11} className="py-1 px-4 text-xs font-bold text-[#163953] tracking-wide">
                                ━━━ LIMITE CLASSE B ({cutoffB}%) ━━━
                              </td>
                            </tr>
                          )}

                          <tr className="hover:bg-[#F6F6EF]/60 transition-colors">
                            <td className="py-2 px-3 text-center text-[#465C69] font-mono">{item.index}</td>
                            <td className="py-2 px-3 text-center">
                              <span className={`inline-block px-2 py-0.5 rounded text-2xs border ${badgeStyle}`}>
                                {item.abc_class}
                              </span>
                            </td>
                            <td className="py-2 px-3 font-mono text-2xs text-[#163953]">{item.code || '—'}</td>
                            <td className="py-2 px-3 font-medium text-[#163953]">{item.description}</td>
                            {activeTab === 'resources' && (
                              <td className="py-2 px-3 text-[#465C69]">{getCategoriaLabel(item.category)}</td>
                            )}
                            <td className="py-2 px-3 text-center text-[#465C69]">{item.unit}</td>
                            <td className="py-2 px-3 text-right text-content-primary tabular-nums font-mono">
                              {item.quantity.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}
                            </td>
                            <td className="py-2 px-3 text-right text-content-primary tabular-nums font-mono">
                              {formatMoneyPtBr(item.unit_rate)}
                            </td>
                            <td className="py-2 px-3 text-right font-bold text-[#163953] tabular-nums font-mono">
                              {formatMoneyPtBr(item.total_cost)}
                            </td>
                            <td className="py-2 px-3 text-right text-content-secondary tabular-nums font-mono">
                              {formatPercentPtBr(item.percentage)}
                            </td>
                            <td className="py-2 px-3 text-right font-semibold text-[#E05D38] tabular-nums font-mono">
                              {formatPercentPtBr(item.cumulative_percentage)}
                            </td>
                          </tr>
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
                <tfoot className="sticky bottom-0 z-10 bg-[#F6F6EF] border-t-2 border-[#163953] font-bold text-xs text-[#163953]">
                  <tr>
                    <td colSpan={activeTab === 'resources' ? 8 : 7} className="py-2.5 px-3 text-right uppercase tracking-wider">
                      Total da Planilha Orçamentária:
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-sm font-bold text-[#156D61]">
                      {formatMoneyPtBr(activeResult.grand_total)}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums">100,00%</td>
                    <td className="py-2.5 px-3 text-right tabular-nums">100,00%</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>

        {/* ── Rodapé Fixo ──────────────────────────────────────────────────── */}
        <footer className="flex items-center justify-between border-t border-[#CED8D5] pt-3 px-1 mt-2 text-xs text-[#465C69]">
          <div>
            Os cálculos respeitam estritamente a soma dos itens da planilha.
          </div>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Fechar
          </Button>
        </footer>
      </div>
    </WideModal>
  );
}
