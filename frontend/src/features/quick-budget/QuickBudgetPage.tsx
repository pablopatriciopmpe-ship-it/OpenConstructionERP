/**
 * Orçamento rápido: assistente em 3 passos que monta uma planilha orçamentária (BOQ) de verdade
 * a partir de um catálogo curado de serviços ligados a composições SINAPI da UF e do regime.
 *
 *   1. Obra: tipo, UF, cidade (rótulo), regime, projeto de destino e (casa/comercial) estimativa por CUB.
 *   2. Serviços: por categoria, com quantidade, busca, resumo do escopo, material do cliente e BDI.
 *   3. Prévia: material × mão de obra × total e "Gerar planilha orçamentária" (cria o BOQ e abre o editor).
 */

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  Calculator,
  Check,
  ChevronDown,
  ChevronRight,
  Hammer,
  Search,
  Wand2,
} from 'lucide-react';
import { Button, Card, ErrorState } from '@/shared/ui';
import { getErrorMessage } from '@/shared/lib/api';
import { fetchProjectList } from '@/shared/lib/projectList';
import { parseDecimalInput, toDecimalPayloadString } from '@/shared/lib/parseDecimal';
import { projectsApi, type Project } from '@/features/projects/api';
import { useToastStore } from '@/stores/useToastStore';
import {
  generateQuickBudget,
  getQuickBudgetCatalog,
  getQuickBudgetCub,
  previewQuickBudget,
  readQuickBudgetError,
  type QbBdiIn,
  type QbCubOut,
  type QbItemIn,
  type QbPlanOut,
  type QuickBudgetModo,
  type QuickBudgetRegime,
  type QuickBudgetTipo,
} from './api';

const UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
];

const CUB_STANDARDS: Record<'casa_nova' | 'comercial', string[]> = {
  casa_nova: ['R1-B', 'R1-N', 'R1-A', 'PP-4-B', 'PP-4-N', 'PP-4-A', 'R8-B', 'R8-N', 'R8-A', 'R16-N', 'R16-A', 'PIS', 'RP1Q'],
  comercial: ['CAL-8-N', 'CAL-8-A', 'CSL-8-N', 'CSL-8-A', 'CSL-16-N', 'CSL-16-A', 'GI'],
};

const TIPOS: { id: QuickBudgetTipo; key: string; label: string; desc: string }[] = [
  { id: 'casa_nova', key: 'casa_nova', label: 'Casa nova', desc: 'Construção residencial do zero' },
  { id: 'comercial', key: 'comercial', label: 'Comercial', desc: 'Lojas, salas e prédios comerciais' },
  { id: 'reforma', key: 'reforma', label: 'Reforma e serviços', desc: 'Reformas, ampliações e serviços avulsos' },
];

interface PickState {
  qty: string;
  price: string;
}

interface BdiForm {
  ac: string;
  s: string;
  r: string;
  g: string;
  df: string;
  l: string;
  pis: string;
  cofins: string;
  iss: string;
}

const EMPTY_BDI: BdiForm = { ac: '', s: '', r: '', g: '', df: '', l: '', pis: '', cofins: '', iss: '' };

const NEW_PROJECT = '__new__';

function fmtBRL(v: string | number | undefined): string {
  const n = typeof v === 'number' ? v : Number.parseFloat(v ?? '0');
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number.isFinite(n) ? n : 0);
}

function fmtQty(v: string): string {
  const n = Number.parseFloat(v);
  return Number.isFinite(n) ? new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 4 }).format(n) : v;
}

function positive(raw: string): boolean {
  const n = parseDecimalInput(raw);
  return n !== null && n > 0;
}

function buildBdi(form: BdiForm): QbBdiIn | null {
  const num = (raw: string): string => toDecimalPayloadString(raw, '0');
  const taxes = [
    { name: 'PIS', percentage: num(form.pis) },
    { name: 'COFINS', percentage: num(form.cofins) },
    { name: 'ISS', percentage: num(form.iss) },
  ].filter((t) => Number.parseFloat(t.percentage) > 0);
  const all = [form.ac, form.s, form.r, form.g, form.df, form.l, form.pis, form.cofins, form.iss];
  if (all.some((raw) => raw.trim() !== '' && parseDecimalInput(raw) === null)) return null;
  return { ac: num(form.ac), s: num(form.s), r: num(form.r), g: num(form.g), df: num(form.df), l: num(form.l), taxes };
}

export function QuickBudgetPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const addToast = useToastStore((s) => s.addToast);

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [tipo, setTipo] = useState<QuickBudgetTipo>('reforma');
  const [uf, setUf] = useState('BA');
  const [cidade, setCidade] = useState('');
  const [regime, setRegime] = useState<QuickBudgetRegime>('desonerado');
  const [projectId, setProjectId] = useState<string>(NEW_PROJECT);
  const [projectName, setProjectName] = useState('');
  const [cubArea, setCubArea] = useState('');
  const [cubStd, setCubStd] = useState('R1-N');
  const [picks, setPicks] = useState<Record<string, PickState>>({});
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [materialCliente, setMaterialCliente] = useState(false);
  const [useBdi, setUseBdi] = useState(false);
  const [bdi, setBdi] = useState<BdiForm>(EMPTY_BDI);
  const [cubResult, setCubResult] = useState<QbCubOut | null>(null);
  const [cubNote, setCubNote] = useState<string | null>(null);

  const modo: QuickBudgetModo = materialCliente ? 'so_mao_de_obra' : 'completo';

  const projectsQ = useQuery({
    queryKey: ['quick-budget-projects'],
    queryFn: () => fetchProjectList<Project[]>(),
  });

  const catalogQ = useQuery({
    queryKey: ['quick-budget-catalog', tipo],
    queryFn: () => getQuickBudgetCatalog(tipo),
  });

  // Ao trocar o tipo de obra, serviços que não se aplicam saem do escopo.
  useEffect(() => {
    const cat = catalogQ.data;
    if (!cat) return;
    const allowed = new Set(cat.categorias.flatMap((c) => c.servicos.map((s) => s.id)));
    setPicks((prev) => {
      const next: Record<string, PickState> = {};
      for (const [id, p] of Object.entries(prev)) if (allowed.has(id)) next[id] = p;
      return Object.keys(next).length === Object.keys(prev).length ? prev : next;
    });
  }, [catalogQ.data]);

  useEffect(() => {
    if (tipo === 'casa_nova') setCubStd('R1-N');
    else if (tipo === 'comercial') setCubStd('CSL-8-N');
    setCubResult(null);
    setCubNote(null);
  }, [tipo]);

  const serviceById = useMemo(() => {
    const m = new Map<string, { descricao: string; unidade: string; preco_informado: boolean }>();
    for (const c of catalogQ.data?.categorias ?? []) for (const s of c.servicos) m.set(s.id, s);
    return m;
  }, [catalogQ.data]);

  const itens: QbItemIn[] = useMemo(
    () =>
      Object.entries(picks)
        .filter(([, p]) => positive(p.qty))
        .map(([servico, p]) => {
          const meta = serviceById.get(servico);
          const item: QbItemIn = { servico, quantidade: toDecimalPayloadString(p.qty) };
          if (meta?.preco_informado && positive(p.price)) item.preco_unitario = toDecimalPayloadString(p.price);
          return item;
        }),
    [picks, serviceById],
  );

  const previewKey = JSON.stringify({ tipo, uf, regime, modo, itens });
  const previewQ = useQuery<QbPlanOut>({
    queryKey: ['quick-budget-preview', previewKey],
    queryFn: () => previewQuickBudget({ tipo, uf, regime, modo, itens }),
    enabled: step === 3 && itens.length > 0,
    retry: false,
  });

  const cubMutation = useMutation({
    mutationFn: () =>
      getQuickBudgetCub({ tipo, uf, area_m2: toDecimalPayloadString(cubArea), regime, padrao: cubStd }),
    onSuccess: (data) => {
      setCubResult(data);
      setCubNote(null);
    },
    onError: (err) => {
      setCubResult(null);
      const info = readQuickBudgetError(err);
      setCubNote(info?.message ?? getErrorMessage(err));
    },
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      let pid = projectId;
      if (pid === NEW_PROJECT) {
        const base = projectName.trim() || `${cidade.trim() ? `${cidade.trim()}/` : ''}${uf}`;
        const created = await projectsApi.create({
          name: base,
          region: 'Brazil',
          currency: 'BRL',
          locale: 'pt-BR',
          country_code: 'BR',
          classification_standard: 'sinapi',
        });
        pid = created.id;
      }
      const bdiBody = useBdi ? buildBdi(bdi) : null;
      if (useBdi && bdiBody === null) {
        throw new Error(t('quick_budget.bdi_invalid', { defaultValue: 'Confira os percentuais do BDI: use apenas números.' }));
      }
      const tipoLabel = TIPOS.find((x) => x.id === tipo)?.label ?? tipo;
      return generateQuickBudget({
        tipo,
        uf,
        regime,
        modo,
        itens,
        project_id: pid,
        nome: `Orçamento rápido - ${tipoLabel} ${cidade.trim() ? `${cidade.trim()}/` : ''}${uf}`,
        ignorar_indisponiveis: true,
        bdi: bdiBody,
      });
    },
    onSuccess: (data) => {
      addToast({
        type: 'success',
        title: t('quick_budget.generated', { defaultValue: 'Planilha orçamentária gerada' }),
        message: fmtBRL(data.bdi?.price_with_bdi ?? data.total),
      });
      navigate(`/boq/${data.boq_id}`);
    },
    onError: (err) => {
      const info = readQuickBudgetError(err);
      addToast({
        type: 'error',
        title: t('quick_budget.generate_failed', { defaultValue: 'Não foi possível gerar a planilha' }),
        message: info?.message ?? getErrorMessage(err),
      });
    },
  });

  const categorias = catalogQ.data?.categorias ?? [];
  const term = search.trim().toLowerCase();
  const visible = categorias
    .map((c) => ({
      ...c,
      servicos: term
        ? c.servicos.filter((s) => `${s.descricao} ${s.sinapi ?? ''} ${c.rotulo}`.toLowerCase().includes(term))
        : c.servicos,
    }))
    .filter((c) => c.servicos.length > 0);

  const selectedByCategory = useMemo(() => {
    const out: Record<string, number> = {};
    for (const c of categorias) {
      out[c.id] = c.servicos.filter((s) => positive(picks[s.id]?.qty ?? '')).length;
    }
    return out;
  }, [categorias, picks]);

  const setPick = (id: string, patch: Partial<PickState>) =>
    setPicks((prev) => ({ ...prev, [id]: { qty: '', price: '', ...prev[id], ...patch } }));

  const toggle = (id: string, on: boolean) =>
    setPicks((prev) => {
      const next = { ...prev };
      if (on) next[id] = { qty: prev[id]?.qty ?? '1', price: prev[id]?.price ?? '' };
      else delete next[id];
      return next;
    });

  const canStep3 = itens.length > 0;
  const cubApplies = tipo === 'casa_nova' || tipo === 'comercial';
  const preview = previewQ.data;
  const previewErr = previewQ.error ? readQuickBudgetError(previewQ.error) : null;
  const blocked = preview?.itens.filter((i) => i.status !== 'ok') ?? [];

  const stepTitles = [
    t('quick_budget.step1', { defaultValue: 'Obra' }),
    t('quick_budget.step2', { defaultValue: 'Serviços' }),
    t('quick_budget.step3', { defaultValue: 'Prévia e planilha' }),
  ];

  return (
    <div className="space-y-5" data-testid="quick-budget-page">
      <div>
        <h1 className="text-2xl font-semibold text-content-primary">
          {t('quick_budget.title', { defaultValue: 'Orçamento rápido' })}
        </h1>
        <p className="mt-1 text-sm text-content-secondary">
          {t('quick_budget.subtitle', {
            defaultValue:
              'Escolha o tipo de obra e a UF, marque os serviços e digite só as quantidades. A planilha sai com composições SINAPI, material e mão de obra separados.',
          })}
        </p>
      </div>

      <ol className="flex flex-wrap items-center gap-2" aria-label={t('quick_budget.steps', { defaultValue: 'Passos' })}>
        {stepTitles.map((title, i) => {
          const n = (i + 1) as 1 | 2 | 3;
          const current = step === n;
          const done = step > n;
          return (
            <li key={title} className="flex items-center gap-2">
              <span
                aria-current={current ? 'step' : undefined}
                className={
                  'inline-flex h-8 items-center gap-2 rounded-full border px-3 text-sm font-medium ' +
                  (current
                    ? 'border-oe-blue bg-oe-blue text-content-inverse'
                    : done
                      ? 'border-oe-blue/40 bg-oe-blue/10 text-oe-blue'
                      : 'border-border text-content-secondary')
                }
              >
                {done ? <Check size={14} aria-hidden /> : <span aria-hidden>{n}</span>}
                {title}
              </span>
              {n < 3 && <ChevronRight size={14} className="text-content-tertiary" aria-hidden />}
            </li>
          );
        })}
      </ol>

      {/* ───────────── Passo 1 ───────────── */}
      {step === 1 && (
        <div className="space-y-5">
          <Card>
            <h2 className="text-lg font-semibold text-content-primary">
              {t('quick_budget.type_title', { defaultValue: 'Tipo de obra' })}
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Tipo de obra">
              {TIPOS.map((x) => (
                <button
                  key={x.id}
                  type="button"
                  role="radio"
                  aria-checked={tipo === x.id}
                  onClick={() => setTipo(x.id)}
                  className={
                    'min-h-[44px] rounded-lg border p-4 text-left transition ' +
                    (tipo === x.id
                      ? 'border-oe-blue bg-oe-blue/10 ring-1 ring-oe-blue'
                      : 'border-border bg-surface-primary hover:bg-surface-secondary')
                  }
                >
                  <span className="block font-semibold text-content-primary">
                    {t(`quick_budget.tipo_${x.key}`, { defaultValue: x.label })}
                  </span>
                  <span className="mt-1 block text-sm text-content-secondary">
                    {t(`quick_budget.tipo_${x.key}_desc`, { defaultValue: x.desc })}
                  </span>
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold text-content-primary">
              {t('quick_budget.where_title', { defaultValue: 'Local e preços' })}
            </h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <label className="text-sm text-content-secondary">
                {t('quick_budget.uf', { defaultValue: 'UF' })}
                <select
                  className="oe-select mt-1 w-full"
                  value={uf}
                  onChange={(e) => setUf(e.target.value)}
                  data-testid="quick-budget-uf"
                >
                  {UFS.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-content-secondary">
                {t('quick_budget.city', { defaultValue: 'Cidade (rótulo do projeto)' })}
                <input
                  className="oe-input mt-1 w-full"
                  value={cidade}
                  onChange={(e) => setCidade(e.target.value)}
                  placeholder="Salvador"
                />
              </label>
              <label className="text-sm text-content-secondary lg:col-span-2">
                {t('quick_budget.regime', { defaultValue: 'Regime de encargos (SINAPI)' })}
                <select
                  className="oe-select mt-1 w-full"
                  value={regime}
                  onChange={(e) => setRegime(e.target.value as QuickBudgetRegime)}
                  data-testid="quick-budget-regime"
                >
                  <option value="desonerado">{t('quick_budget.regime_des', { defaultValue: 'Desonerado' })}</option>
                  <option value="nao_desonerado">
                    {t('quick_budget.regime_nd', { defaultValue: 'Não desonerado' })}
                  </option>
                </select>
              </label>
            </div>
            <p className="mt-2 text-sm text-content-tertiary">
              {t('quick_budget.regime_help', {
                defaultValue:
                  'O SINAPI publica preços por UF em dois regimes de encargos sociais. Os preços são os da tabela importada para a UF e o regime escolhidos; o SINAPI não separa por cidade.',
              })}
            </p>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold text-content-primary">
              {t('quick_budget.project_title', { defaultValue: 'Projeto de destino' })}
            </h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="text-sm text-content-secondary">
                {t('quick_budget.project', { defaultValue: 'Projeto' })}
                <select
                  className="oe-select mt-1 w-full"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  data-testid="quick-budget-project"
                >
                  <option value={NEW_PROJECT}>{t('quick_budget.new_project', { defaultValue: 'Criar um projeto novo' })}</option>
                  {(projectsQ.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              {projectId === NEW_PROJECT && (
                <label className="text-sm text-content-secondary">
                  {t('quick_budget.project_name', { defaultValue: 'Nome do projeto novo' })}
                  <input
                    className="oe-input mt-1 w-full"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder={t('quick_budget.project_name_ph', { defaultValue: 'Reforma de banheiro - Salvador/BA' })}
                  />
                </label>
              )}
            </div>
          </Card>

          {cubApplies && (
            <Card data-testid="quick-budget-cub">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-content-primary">
                <Calculator size={18} className="text-oe-blue" aria-hidden />
                {t('quick_budget.cub_title', { defaultValue: 'Estimativa preliminar por área × CUB' })}
              </h2>
              <div className="mt-3 grid gap-4 sm:grid-cols-3">
                <label className="text-sm text-content-secondary">
                  {t('quick_budget.cub_area', { defaultValue: 'Área construída (m²)' })}
                  <input
                    className="oe-input mt-1 w-full"
                    inputMode="decimal"
                    value={cubArea}
                    onChange={(e) => setCubArea(e.target.value)}
                    placeholder="120"
                  />
                </label>
                <label className="text-sm text-content-secondary">
                  {t('quick_budget.cub_standard', { defaultValue: 'Padrão (NBR 12.721)' })}
                  <select className="oe-select mt-1 w-full" value={cubStd} onChange={(e) => setCubStd(e.target.value)}>
                    {CUB_STANDARDS[tipo === 'comercial' ? 'comercial' : 'casa_nova'].map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex items-end">
                  <Button
                    variant="secondary"
                    disabled={!positive(cubArea)}
                    loading={cubMutation.isPending}
                    onClick={() => cubMutation.mutate()}
                  >
                    {t('quick_budget.cub_calc', { defaultValue: 'Calcular estimativa' })}
                  </Button>
                </div>
              </div>
              {cubNote && (
                <p
                  role="status"
                  className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-surface-secondary px-3 py-2 text-sm text-content-secondary"
                  data-testid="quick-budget-cub-note"
                >
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-semantic-warning" aria-hidden />
                  {cubNote}
                </p>
              )}
              {cubResult && (
                <div className="mt-3 rounded-lg border border-oe-blue/30 bg-oe-blue/5 p-3" data-testid="quick-budget-cub-result">
                  <p className="text-xl font-semibold text-content-primary">{fmtBRL(cubResult.total)}</p>
                  <p className="text-sm text-content-secondary">
                    {fmtQty(cubResult.area_m2)} m² × {fmtBRL(cubResult.cub_por_m2)}/m² · CUB {cubResult.padrao} ·{' '}
                    {cubResult.competencia}
                  </p>
                  <p className="mt-1 text-xs text-content-tertiary">{cubResult.fonte}</p>
                  <p className="mt-1 text-xs text-content-tertiary">{cubResult.aviso}</p>
                </div>
              )}
            </Card>
          )}

          <div className="flex justify-end">
            <Button variant="primary" onClick={() => setStep(2)} data-testid="quick-budget-next-1">
              {t('quick_budget.next', { defaultValue: 'Escolher serviços' })}
            </Button>
          </div>
        </div>
      )}

      {/* ───────────── Passo 2 ───────────── */}
      {step === 2 && (
        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            <label className="relative block">
              <span className="sr-only">{t('quick_budget.search', { defaultValue: 'Buscar serviço' })}</span>
              <Search size={16} className="pointer-events-none absolute left-3 top-3 text-content-tertiary" aria-hidden />
              <input
                className="oe-input w-full pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('quick_budget.search_ph', { defaultValue: 'Buscar serviço, categoria ou código SINAPI' })}
                data-testid="quick-budget-search"
              />
            </label>

            {catalogQ.isError && (
              <ErrorState
                title={t('quick_budget.catalog_error', { defaultValue: 'Não foi possível carregar o catálogo de serviços' })}
                onRetry={() => catalogQ.refetch()}
              />
            )}
            {catalogQ.isLoading && (
              <p role="status" className="text-sm text-content-secondary">
                {t('common.loading', { defaultValue: 'Carregando...' })}
              </p>
            )}

            {visible.map((c) => {
              const isOpen = term ? true : open[c.id] ?? false;
              const count = selectedByCategory[c.id] ?? 0;
              return (
                <Card key={c.id} data-testid={`quick-budget-cat-${c.id}`}>
                  <button
                    type="button"
                    className="flex min-h-[44px] w-full items-center justify-between gap-3 text-left"
                    aria-expanded={isOpen}
                    onClick={() => setOpen((prev) => ({ ...prev, [c.id]: !isOpen }))}
                  >
                    <span className="flex items-center gap-2 font-semibold text-content-primary">
                      {isOpen ? <ChevronDown size={16} aria-hidden /> : <ChevronRight size={16} aria-hidden />}
                      {c.rotulo}
                      <span className="text-sm font-normal text-content-tertiary">({c.servicos.length})</span>
                    </span>
                    {count > 0 && (
                      <span className="rounded-full bg-oe-blue/10 px-2 py-0.5 text-xs font-semibold text-oe-blue">
                        {t('quick_budget.n_selected', { defaultValue: '{{n}} marcado(s)', n: count })}
                      </span>
                    )}
                  </button>
                  {isOpen && (
                    <ul className="mt-2 divide-y divide-border-light">
                      {c.servicos.map((s) => {
                        const pick = picks[s.id];
                        const on = pick !== undefined;
                        return (
                          <li key={s.id} className="flex flex-wrap items-center gap-3 py-2">
                            <label className="flex min-h-[44px] flex-1 cursor-pointer items-center gap-3">
                              <input
                                type="checkbox"
                                className="h-4 w-4"
                                checked={on}
                                onChange={(e) => toggle(s.id, e.target.checked)}
                                data-testid={`quick-budget-check-${s.id}`}
                              />
                              <span>
                                <span className="block text-sm font-medium text-content-primary">{s.descricao}</span>
                                <span className="block text-xs text-content-tertiary">
                                  {s.sinapi
                                    ? `SINAPI ${s.sinapi} · ${s.unidade.toLowerCase()}`
                                    : t('quick_budget.manual_price', {
                                        defaultValue: 'Sem composição SINAPI: informe o preço unitário',
                                      })}
                                </span>
                              </span>
                            </label>
                            {pick && (
                              <div className="flex items-center gap-2">
                                <input
                                  className="oe-input w-24 text-right"
                                  inputMode="decimal"
                                  aria-label={t('quick_budget.qty', { defaultValue: 'Quantidade' })}
                                  value={pick.qty}
                                  onChange={(e) => setPick(s.id, { qty: e.target.value })}
                                  data-testid={`quick-budget-qty-${s.id}`}
                                />
                                <span className="w-10 text-sm text-content-secondary">{s.unidade.toLowerCase()}</span>
                                {s.preco_informado && (
                                  <input
                                    className="oe-input w-28 text-right"
                                    inputMode="decimal"
                                    aria-label={t('quick_budget.unit_price', { defaultValue: 'Preço unitário (R$)' })}
                                    placeholder="R$"
                                    value={pick.price}
                                    onChange={(e) => setPick(s.id, { price: e.target.value })}
                                  />
                                )}
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Card>
              );
            })}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
            <Card data-testid="quick-budget-summary">
              <h2 className="font-semibold text-content-primary">
                {t('quick_budget.scope', { defaultValue: 'Resumo do escopo' })}
              </h2>
              <p className="mt-1 text-sm text-content-secondary">
                {TIPOS.find((x) => x.id === tipo)?.label} · {uf}
                {cidade.trim() ? ` · ${cidade.trim()}` : ''} · {regime === 'desonerado' ? 'desonerado' : 'não desonerado'}
              </p>
              <p className="mt-2 text-sm text-content-primary">
                {t('quick_budget.scope_count', {
                  defaultValue: '{{n}} serviço(s) em {{c}} categoria(s)',
                  n: itens.length,
                  c: Object.values(selectedByCategory).filter((n) => n > 0).length,
                })}
              </p>
              <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-xs text-content-secondary">
                {itens.map((i) => (
                  <li key={i.servico}>
                    {serviceById.get(i.servico)?.descricao ?? i.servico} · {fmtQty(i.quantidade)}
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <label className="flex min-h-[44px] cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4"
                  checked={materialCliente}
                  onChange={(e) => setMaterialCliente(e.target.checked)}
                  data-testid="quick-budget-material-cliente"
                />
                <span>
                  <span className="block text-sm font-semibold text-content-primary">
                    {t('quick_budget.client_material', { defaultValue: 'Material fornecido pelo cliente' })}
                  </span>
                  <span className="block text-xs text-content-tertiary">
                    {t('quick_budget.client_material_help', {
                      defaultValue:
                        'A planilha sai só com a parcela de mão de obra de cada composição SINAPI. Serviços sem mão de obra na composição ficam de fora e são listados.',
                    })}
                  </span>
                </span>
              </label>
            </Card>

            <Card>
              <label className="flex min-h-[44px] cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4"
                  checked={useBdi}
                  onChange={(e) => setUseBdi(e.target.checked)}
                  data-testid="quick-budget-use-bdi"
                />
                <span className="text-sm font-semibold text-content-primary">
                  {t('quick_budget.use_bdi', { defaultValue: 'Aplicar BDI (fórmula do TCU)' })}
                </span>
              </label>
              {useBdi && (
                <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-content-secondary" data-testid="quick-budget-bdi">
                  {(
                    [
                      ['ac', 'Administração central (AC) %'],
                      ['s', 'Seguro (S) %'],
                      ['r', 'Risco (R) %'],
                      ['g', 'Garantia (G) %'],
                      ['df', 'Despesas financeiras (DF) %'],
                      ['l', 'Lucro (L) %'],
                      ['pis', 'PIS %'],
                      ['cofins', 'COFINS %'],
                      ['iss', 'ISS %'],
                    ] as [keyof BdiForm, string][]
                  ).map(([k, label]) => (
                    <label key={k}>
                      {label}
                      <input
                        className="oe-input mt-1 w-full text-right"
                        inputMode="decimal"
                        value={bdi[k]}
                        onChange={(e) => setBdi((prev) => ({ ...prev, [k]: e.target.value }))}
                      />
                    </label>
                  ))}
                  <p className="col-span-2 text-content-tertiary">
                    {t('quick_budget.bdi_help', {
                      defaultValue:
                        'BDI = ((1+AC+S+R+G)×(1+DF)×(1+L)/(1−I))−1. Informe os percentuais da sua empresa; nada vem preenchido.',
                    })}
                  </p>
                </div>
              )}
            </Card>
          </aside>

          <div className="flex justify-between lg:col-span-2">
            <Button variant="secondary" onClick={() => setStep(1)}>
              {t('quick_budget.back', { defaultValue: 'Voltar' })}
            </Button>
            <Button variant="primary" disabled={!canStep3} onClick={() => setStep(3)} data-testid="quick-budget-next-2">
              {t('quick_budget.next2', { defaultValue: 'Ver prévia' })}
            </Button>
          </div>
        </div>
      )}

      {/* ───────────── Passo 3 ───────────── */}
      {step === 3 && (
        <div className="space-y-5">
          {previewQ.isLoading && (
            <p role="status" className="text-sm text-content-secondary">
              {t('quick_budget.calculating', { defaultValue: 'Calculando a prévia...' })}
            </p>
          )}

          {previewErr && previewErr.code === 'sinapi_nao_importado' && (
            <Card data-testid="quick-budget-no-sinapi">
              <h2 className="flex items-center gap-2 font-semibold text-content-primary">
                <AlertTriangle size={18} className="text-semantic-warning" aria-hidden />
                {t('quick_budget.no_sinapi_title', { defaultValue: 'A tabela SINAPI desta UF ainda não foi importada' })}
              </h2>
              <p className="mt-2 text-sm text-content-secondary">{previewErr.message}</p>
            </Card>
          )}
          {previewErr && previewErr.code !== 'sinapi_nao_importado' && (
            <ErrorState
              title={t('quick_budget.preview_error', { defaultValue: 'Não foi possível calcular a prévia' })}
              hint={previewErr.message}
              onRetry={() => previewQ.refetch()}
            />
          )}

          {preview && (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-oe-blue/10 px-3 py-1 text-sm font-medium text-oe-blue">
                  SINAPI {preview.sinapi_referencia} · {preview.uf} · {preview.regime === 'desonerado' ? 'desonerado' : 'não desonerado'}
                </span>
                <label className="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-content-secondary">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={materialCliente}
                    onChange={(e) => setMaterialCliente(e.target.checked)}
                  />
                  {t('quick_budget.client_material', { defaultValue: 'Material fornecido pelo cliente' })}
                </label>
              </div>

              {blocked.length > 0 && (
                <div
                  role="status"
                  className="rounded-lg border border-semantic-warning/40 bg-semantic-warning-bg px-4 py-3 text-sm text-content-primary"
                  data-testid="quick-budget-blocked"
                >
                  <p className="font-semibold">
                    {t('quick_budget.blocked_title', { defaultValue: 'Estes serviços ficarão fora da planilha:' })}
                  </p>
                  <ul className="mt-1 list-disc pl-5">
                    {blocked.map((b) => (
                      <li key={b.servico}>
                        {b.descricao}: {b.motivo}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[820px] text-sm" data-testid="quick-budget-table">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase text-content-tertiary">
                        <th className="py-2 pr-2">{t('quick_budget.col_desc', { defaultValue: 'Descrição' })}</th>
                        <th className="px-2">SINAPI</th>
                        <th className="px-2">{t('quick_budget.col_unit', { defaultValue: 'Un' })}</th>
                        <th className="px-2 text-right">{t('quick_budget.col_qty', { defaultValue: 'Qtd' })}</th>
                        <th className="px-2 text-right">{t('quick_budget.col_price', { defaultValue: 'Preço unit.' })}</th>
                        <th className="px-2 text-right">{t('quick_budget.col_material', { defaultValue: 'Material (un)' })}</th>
                        <th className="px-2 text-right">{t('quick_budget.col_labor', { defaultValue: 'Mão de obra (un)' })}</th>
                        <th className="pl-2 text-right">{t('quick_budget.col_total', { defaultValue: 'Total' })}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.itens
                        .filter((i) => i.status === 'ok')
                        .map((i, idx, arr) => {
                          const prev = arr[idx - 1];
                          const newCat = !prev || prev.categoria !== i.categoria;
                          const other = Number.parseFloat(i.material) + Number.parseFloat(i.equipamento) + Number.parseFloat(i.terceiros);
                          return (
                            <FragmentRow key={i.servico} header={newCat ? i.categoria_rotulo : null}>
                              <td className="py-2 pr-2 text-content-primary">{i.descricao}</td>
                              <td className="px-2 text-content-secondary">{i.sinapi ?? '—'}</td>
                              <td className="px-2 text-content-secondary">{i.unidade.toLowerCase()}</td>
                              <td className="px-2 text-right tabular-nums">{fmtQty(i.quantidade)}</td>
                              <td className="px-2 text-right tabular-nums">{fmtBRL(i.preco_unitario)}</td>
                              <td className="px-2 text-right tabular-nums">{other > 0 ? fmtBRL(other) : '—'}</td>
                              <td className="px-2 text-right tabular-nums">
                                {Number.parseFloat(i.mao_de_obra) > 0 ? fmtBRL(i.mao_de_obra) : '—'}
                              </td>
                              <td className="pl-2 text-right font-medium tabular-nums">{fmtBRL(i.total)}</td>
                            </FragmentRow>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </Card>

              <div className="grid gap-3 sm:grid-cols-3" data-testid="quick-budget-totals">
                <Card>
                  <p className="text-xs text-content-tertiary">
                    {t('quick_budget.total_material', { defaultValue: 'Material e equipamentos' })}
                  </p>
                  <p className="text-xl font-semibold tabular-nums">
                    {fmtBRL(
                      Number.parseFloat(preview.por_tipo.material ?? '0') +
                        Number.parseFloat(preview.por_tipo.equipment ?? '0') +
                        Number.parseFloat(preview.por_tipo.subcontractor ?? '0') +
                        Number.parseFloat(preview.por_tipo.other ?? '0'),
                    )}
                  </p>
                </Card>
                <Card>
                  <p className="text-xs text-content-tertiary">{t('quick_budget.total_labor', { defaultValue: 'Mão de obra' })}</p>
                  <p className="text-xl font-semibold tabular-nums">{fmtBRL(preview.por_tipo.labor)}</p>
                </Card>
                <Card>
                  <p className="text-xs text-content-tertiary">
                    {t('quick_budget.total_direct', { defaultValue: 'Custo direto (sem BDI)' })}
                  </p>
                  <p className="text-xl font-semibold tabular-nums text-oe-blue" data-testid="quick-budget-total">
                    {fmtBRL(preview.total)}
                  </p>
                </Card>
              </div>
              {useBdi && (
                <p className="text-sm text-content-secondary">
                  {t('quick_budget.bdi_after', {
                    defaultValue: 'O BDI informado será aplicado na planilha gerada; o preço final com BDI aparece no editor.',
                  })}
                </p>
              )}
            </>
          )}

          <div className="flex justify-between">
            <Button variant="secondary" onClick={() => setStep(2)}>
              {t('quick_budget.back', { defaultValue: 'Voltar' })}
            </Button>
            <Button
              variant="primary"
              icon={<Hammer size={16} />}
              disabled={!preview || preview.itens.every((i) => i.status !== 'ok')}
              loading={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
              data-testid="quick-budget-generate"
            >
              {t('quick_budget.generate', { defaultValue: 'Gerar planilha orçamentária' })}
            </Button>
          </div>
        </div>
      )}

      <p className="flex items-center gap-2 text-xs text-content-tertiary">
        <Wand2 size={14} aria-hidden />
        {t('quick_budget.ai_hint', {
          defaultValue: 'Prefere descrever a obra em texto? Use a Estimativa IA, que continua disponível à parte.',
        })}{' '}
        <button type="button" className="underline" onClick={() => navigate('/ai-estimate')}>
          {t('quick_budget.ai_link', { defaultValue: 'Abrir Estimativa IA' })}
        </button>
      </p>
    </div>
  );
}

/** Linha de tabela com cabeçalho opcional de categoria acima (sem depender de Fragment com chave). */
function FragmentRow({ header, children }: { header: string | null; children: ReactNode }) {
  return (
    <>
      {header && (
        <tr className="bg-surface-secondary">
          <td colSpan={8} className="py-1.5 pl-1 text-xs font-semibold uppercase text-content-secondary">
            {header}
          </td>
        </tr>
      )}
      <tr className="border-b border-border-light">{children}</tr>
    </>
  );
}
