// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
/**
 * CUB/m² reference panel.
 *
 * The CUB is published monthly by each state's Sinduscon under Lei 4.591/1964
 * and ABNT NBR 12.721:2006. Nothing here fetches a portal: an administrator
 * imports a curated CSV or edits one row by hand, and every figure is shown
 * with the publisher's credit and the exclusions the CUB does not cover.
 *
 * Reads are open to any signed-in user; the import/edit controls follow the
 * ``price_index.manage`` permission and the API enforces the same gate.
 */

import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BadgeCheck,
  Calculator,
  Download,
  FileUp,
  Landmark,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  InfoHint,
  SkeletonTable,
} from '@/shared/ui';
import { getErrorMessage, triggerDownload } from '@/shared/lib/api';
import { useHasPermission } from '@/shared/lib/permissionGates';
import { useToastStore } from '@/stores/useToastStore';
import {
  compareCub,
  createCubRate,
  deleteCubRate,
  getCubCatalog,
  importCubCsv,
  listCubRates,
  replaceCubRate,
  verifyCubRate,
  type CubCatalog,
  type CubCompareResult,
  type CubRate,
  type CubRatePayload,
} from './api';

const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
  'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
  'SP', 'SE', 'TO',
];

const STANDARDS = [
  'R1-B', 'R1-N', 'R1-A', 'PP-4-B', 'PP-4-N', 'PP-4-A', 'R8-B', 'R8-N',
  'R8-A', 'R16-N', 'R16-A', 'PIS', 'RP1Q', 'CAL-8-N', 'CAL-8-A',
  'CSL-8-N', 'CSL-8-A', 'CSL-16-N', 'CSL-16-A', 'GI',
];

const CUB_FALLBACK_ATTRIBUTION =
  'CUB/m² divulgado por Sinduscon / CBIC, calculado nos termos da Lei Federal nº 4.591/1964 e ABNT NBR 12.721:2006 — valor exclusivamente referencial.';

const CUB_EXCLUSIONS =
  'O CUB não inclui fundações, elevadores, ar-condicionado, projetos, remuneração do construtor e impostos. Compare com o custo direto de construção, não com o preço de venda.';

interface FormState {
  id: string | null;
  reference_month: string;
  uf: string;
  regional_code: string;
  sinduscon_code: string;
  sinduscon_name: string;
  project_standard: string;
  tax_regime: 'desonerado' | 'nao_desonerado';
  material: string;
  labor: string;
  administrative: string;
  equipment: string;
  total_sqm: string;
  source_name: string;
  source_url: string;
  published_at: string;
  notes: string;
}

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): FormState {
  return {
    id: null,
    reference_month: currentMonth(),
    uf: 'SP',
    regional_code: '',
    sinduscon_code: '',
    sinduscon_name: '',
    project_standard: 'R8-N',
    tax_regime: 'nao_desonerado',
    material: '',
    labor: '',
    administrative: '',
    equipment: '',
    total_sqm: '',
    source_name: '',
    source_url: '',
    published_at: today(),
    notes: '',
  };
}

function fromRow(row: CubRate): FormState {
  return {
    id: row.id,
    reference_month: row.reference_month,
    uf: row.uf,
    regional_code: row.regional_code,
    sinduscon_code: row.sinduscon_code,
    sinduscon_name: row.sinduscon_name,
    project_standard: row.project_standard,
    tax_regime: row.tax_regime === 'desonerado' ? 'desonerado' : 'nao_desonerado',
    material: row.material,
    labor: row.labor,
    administrative: row.administrative,
    equipment: row.equipment,
    total_sqm: row.total_sqm,
    source_name: row.source_name,
    source_url: row.source_url,
    published_at: row.published_at ?? '',
    notes: row.notes,
  };
}

/** Normalise a pt-BR typed amount ("2.245,68") to the API's decimal string. */
function decimalString(raw: string): string {
  const text = raw.trim().replace(/R\$/g, '').replace(/\s/g, '');
  if (!text) return '';
  const normalised =
    text.includes(',') && text.includes('.')
      ? text.replace(/\./g, '').replace(',', '.')
      : text.replace(',', '.');
  return normalised;
}

function money(locale: string, value: string | number): string {
  const n = Number(value);
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'BRL',
    currencyDisplay: 'narrowSymbol',
  }).format(Number.isFinite(n) ? n : 0);
}

export function CubPanel() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || 'pt-BR';
  const addToast = useToastStore((s) => s.addToast);
  const canManage = useHasPermission('price_index.manage');
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [filters, setFilters] = useState({ uf: '', month: '', standard: '', regime: '' });
  const [form, setForm] = useState<FormState | null>(null);
  const [verifyOnImport, setVerifyOnImport] = useState(false);
  const [lastSkipped, setLastSkipped] = useState<Array<{ line: number; message: string }>>([]);
  const [showEstimator, setShowEstimator] = useState(false);
  const [estimatorForm, setEstimatorForm] = useState({
    area: '1250',
    uf: 'SP',
    standard: 'R8-N',
    regime: 'nao_desonerado',
    margin: '10',
  });

  const estimatorQuery = useQuery<CubCompareResult>({
    queryKey: ['price-index', 'cub', 'compare', estimatorForm],
    queryFn: () =>
      compareCub({
        area: estimatorForm.area || 1,
        uf: estimatorForm.uf,
        standard: estimatorForm.standard,
        regime: estimatorForm.regime,
        margin: estimatorForm.margin || 10,
      }),
    enabled: showEstimator && Number(estimatorForm.area) > 0,
    staleTime: 30_000,
  });

  const catalogQuery = useQuery<CubCatalog>({
    queryKey: ['price-index', 'cub', 'catalog'],
    queryFn: getCubCatalog,
    staleTime: 60_000,
  });

  const listQuery = useQuery({
    queryKey: ['price-index', 'cub', 'list', filters],
    queryFn: () =>
      listCubRates({
        uf: filters.uf || undefined,
        month: filters.month || undefined,
        standard: filters.standard || undefined,
        regime: filters.regime || undefined,
      }),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['price-index', 'cub'] });
  };

  const saveMutation = useMutation({
    mutationFn: async (state: FormState) => {
      const payload: CubRatePayload = {
        reference_month: state.reference_month,
        uf: state.uf,
        regional_code: state.regional_code.trim(),
        sinduscon_code: state.sinduscon_code.trim(),
        sinduscon_name: state.sinduscon_name.trim(),
        project_standard: state.project_standard.trim().toUpperCase(),
        tax_regime: state.tax_regime,
        material: decimalString(state.material) || '0',
        labor: decimalString(state.labor) || '0',
        administrative: decimalString(state.administrative) || '0',
        equipment: decimalString(state.equipment) || '0',
        total_sqm: decimalString(state.total_sqm),
        source_name: state.source_name.trim(),
        source_url: state.source_url.trim(),
        published_at: state.published_at || null,
        notes: state.notes.trim(),
      };
      return state.id ? replaceCubRate(state.id, payload) : createCubRate(payload);
    },
    onSuccess: () => {
      addToast({
        type: 'success',
        title: t('price_index.cub_saved', { defaultValue: 'CUB value saved' }),
      });
      setForm(null);
      invalidate();
    },
    onError: (error) =>
      addToast({
        type: 'error',
        title: t('price_index.cub_save_failed', { defaultValue: 'Could not save the CUB value' }),
        message: getErrorMessage(error),
      }),
  });

  const verifyMutation = useMutation({
    mutationFn: ({ id, verified }: { id: string; verified: boolean }) => verifyCubRate(id, verified),
    onSuccess: invalidate,
    onError: (error) =>
      addToast({
        type: 'error',
        title: t('price_index.cub_verify_failed', { defaultValue: 'Could not update the check' }),
        message: getErrorMessage(error),
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCubRate(id),
    onSuccess: invalidate,
    onError: (error) =>
      addToast({
        type: 'error',
        title: t('price_index.cub_delete_failed', { defaultValue: 'Could not delete the CUB value' }),
        message: getErrorMessage(error),
      }),
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => importCubCsv(file, verifyOnImport),
    onSuccess: (summary) => {
      setLastSkipped(summary.skipped.slice(0, 8));
      addToast({
        type: summary.skipped.length ? 'warning' : 'success',
        title: t('price_index.cub_import_done', {
          defaultValue: 'CUB import: {{created}} created, {{updated}} updated, {{skipped}} skipped',
          created: summary.created,
          updated: summary.updated,
          skipped: summary.skipped.length,
        }),
      });
      invalidate();
    },
    onError: (error) => {
      setLastSkipped([]);
      addToast({
        type: 'error',
        title: t('price_index.cub_import_failed', { defaultValue: 'Could not import the CUB CSV' }),
        message: getErrorMessage(error),
      });
    },
  });

  const rows = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const catalog = catalogQuery.data;

  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);

  const activeRow = useMemo(() => {
    if (selectedRowId) {
      const match = rows.find((r) => r.id === selectedRowId);
      if (match) return match;
    }
    if (filters.uf) {
      const match = rows.find((r) => r.uf === filters.uf);
      if (match) return match;
    }
    // Default to SP (primary showcase UF) or first available row
    return rows.find((r) => r.uf === 'SP') || rows[0] || null;
  }, [selectedRowId, filters.uf, rows]);

  const attribution = activeRow?.attribution || CUB_FALLBACK_ATTRIBUTION;

  const monthOptions = useMemo(() => {
    const set = new Set<string>(catalog?.months ?? []);
    if (form?.reference_month) set.add(form.reference_month);
    return Array.from(set).sort().reverse();
  }, [catalog?.months, form?.reference_month]);

  const componentSum = useMemo(() => {
    if (!form) return 0;
    return ['material', 'labor', 'administrative', 'equipment'].reduce(
      (sum, key) => sum + (Number(decimalString(form[key as keyof FormState] as string)) || 0),
      0,
    );
  }, [form]);

  const totalValue = form ? Number(decimalString(form.total_sqm)) || 0 : 0;
  const breakdownMismatch =
    form !== null && componentSum > 0 && Math.abs(componentSum - totalValue) > 0.02;

  const downloadTemplate = () => {
    const header =
      'reference_month,uf,regional_code,sinduscon_code,sinduscon_name,project_standard,tax_regime,material,labor,administrative,equipment,total_sqm,source_name,source_url,published_at,notes';
    const example = `${currentMonth()},SP,SP-CAPITAL,SINDUSCON_SP,SindusCon-SP / FGV,R8-N,nao_desonerado,1285.40,845.20,78.50,36.58,2245.68,SindusCon-SP / FGV,https://sindusconsp.com.br,${today()},`;
    const blob = new Blob([`\ufeff${header}\n${example}\n`], {
      type: 'text/csv;charset=utf-8',
    });
    triggerDownload(blob, 'modelo-cub.csv');
  };

  const onPickFile = (file: File | undefined) => {
    if (!file) return;
    importMutation.mutate(file);
    if (fileRef.current) fileRef.current.value = '';
  };

  const filterLabel = t('price_index.cub_filters', { defaultValue: 'Filters' });

  return (
    <Card data-testid="price-index-cub">
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <Landmark className="h-4 w-4 text-oe-blue" aria-hidden />
            {t('price_index.cub_title', { defaultValue: 'CUB/m² — construction unit cost' })}
          </span>
        }
        subtitle={t('price_index.cub_subtitle', {
          defaultValue:
            'Monthly R$/m² published by each state Sinduscon under Lei 4.591/1964 and NBR 12.721:2006. Curated by an administrator, never scraped.',
        })}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={showEstimator ? 'primary' : 'secondary'}
              size="sm"
              icon={<Calculator size={14} />}
              onClick={() => setShowEstimator((prev) => !prev)}
            >
              {t('price_index.cub_quick_estimate', { defaultValue: 'Estimativa rápida' })}
            </Button>
            {canManage && (
              <>
                <label className="flex items-center gap-1.5 text-xs text-content-tertiary">
                  <input
                    type="checkbox"
                    checked={verifyOnImport}
                    onChange={(event) => setVerifyOnImport(event.target.checked)}
                  />
                  {t('price_index.cub_verify_on_import', { defaultValue: 'Mark as checked' })}
                </label>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(event) => onPickFile(event.target.files?.[0])}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<FileUp size={14} />}
                  loading={importMutation.isPending}
                  onClick={() => fileRef.current?.click()}
                >
                  {t('price_index.cub_import_csv', { defaultValue: 'Import CSV' })}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Download size={14} />}
                  onClick={downloadTemplate}
                >
                  {t('price_index.cub_template', { defaultValue: 'Template' })}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Plus size={14} />}
                  onClick={() => setForm(emptyForm())}
                >
                  {t('price_index.cub_add', { defaultValue: 'Add value' })}
                </Button>
              </>
            )}
          </div>
        }
      />

      {/* Attribution leads, before any number: the credit is a condition of
          using a published CUB, not a footnote. */}
      <div className="mt-3 rounded-lg border border-border-light bg-surface-secondary/40 px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-content-secondary font-medium">{attribution}</p>
          {activeRow && (
            <span className="shrink-0 rounded bg-oe-blue/10 px-2 py-0.5 text-2xs font-semibold text-oe-blue">
              {activeRow.uf} · {activeRow.project_standard} · {activeRow.reference_month}
            </span>
          )}
        </div>
        <p className="mt-1 text-2xs text-content-tertiary">{CUB_EXCLUSIONS}</p>
      </div>

      {/* ── Estimativa rápida por CUB ─────────────────────────────────── */}
      {showEstimator && (
        <div
          className="mt-4 rounded-xl border border-oe-blue/30 bg-surface-primary p-4 shadow-sm"
          data-testid="cub-quick-estimator-card"
        >
          <div className="flex items-center justify-between border-b border-border-light pb-2">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-oe-blue/15 text-oe-blue">
                <Calculator size={16} />
              </span>
              <div>
                <h4 className="text-sm font-semibold text-content-primary">
                  {t('price_index.cub_quick_estimate_title', {
                    defaultValue: 'Estimativa rápida paramétrica por CUB',
                  })}
                </h4>
                <p className="text-2xs text-content-tertiary">
                  {t('price_index.cub_quick_estimate_sub', {
                    defaultValue: 'Área da obra × CUB/m² divulgado pelo Sinduscon regional (NBR 12.721)',
                  })}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              icon={<X size={14} />}
              onClick={() => setShowEstimator(false)}
            >
              {t('common.close', { defaultValue: 'Fechar' })}
            </Button>
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_area_label', { defaultValue: 'Área construída (m²)' })}
              <input
                type="number"
                min="1"
                step="any"
                value={estimatorForm.area}
                onChange={(e) => setEstimatorForm({ ...estimatorForm, area: e.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2.5 py-1.5 text-xs font-semibold tabular-nums text-content-primary"
                placeholder="Ex: 1250"
              />
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_uf', { defaultValue: 'UF' })}
              <select
                value={estimatorForm.uf}
                onChange={(e) => setEstimatorForm({ ...estimatorForm, uf: e.target.value })}
                className="oe-select mt-1 w-full text-xs font-medium"
              >
                {UFS.map((uf) => (
                  <option key={uf} value={uf}>{uf}</option>
                ))}
              </select>
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_standard', { defaultValue: 'Padrão (NBR 12.721)' })}
              <select
                value={estimatorForm.standard}
                onChange={(e) => setEstimatorForm({ ...estimatorForm, standard: e.target.value })}
                className="oe-select mt-1 w-full text-xs font-medium"
              >
                {(catalog?.standards.length ? catalog.standards : STANDARDS).map((std) => (
                  <option key={std} value={std}>{std}</option>
                ))}
              </select>
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_regime', { defaultValue: 'Regime tributário' })}
              <select
                value={estimatorForm.regime}
                onChange={(e) => setEstimatorForm({ ...estimatorForm, regime: e.target.value })}
                className="oe-select mt-1 w-full text-xs"
              >
                <option value="nao_desonerado">
                  {t('price_index.cub_regime_nao', { defaultValue: 'Não desonerado' })}
                </option>
                <option value="desonerado">
                  {t('price_index.cub_regime_des', { defaultValue: 'Desonerado' })}
                </option>
              </select>
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_margin_label', { defaultValue: 'Faixa de ajuste (±%)' })}
              <input
                type="number"
                min="0"
                max="50"
                step="1"
                value={estimatorForm.margin}
                onChange={(e) => setEstimatorForm({ ...estimatorForm, margin: e.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2.5 py-1.5 text-xs text-content-primary tabular-nums"
                placeholder="10"
              />
            </label>
          </div>

          {estimatorQuery.isLoading ? (
            <div className="mt-4 p-4 text-center text-xs text-content-tertiary">
              {t('price_index.cub_calculating', { defaultValue: 'Calculando estimativa...' })}
            </div>
          ) : estimatorQuery.isError ? (
            <div className="mt-4 rounded-lg border border-border-light bg-surface-secondary/50 p-4 text-center">
              <p className="text-xs text-content-secondary">
                {t('price_index.cub_estimate_not_found', {
                  defaultValue: 'Nenhum valor de CUB cadastrado para {{uf}} no padrão {{standard}} ({{regime}}).',
                  uf: estimatorForm.uf,
                  standard: estimatorForm.standard,
                  regime: estimatorForm.regime === 'desonerado' ? 'desonerado' : 'não desonerado',
                })}
              </p>
              <p className="mt-1 text-2xs text-content-tertiary">
                {t('price_index.cub_estimate_not_found_hint', {
                  defaultValue: 'Cadastre ou importe valores para esta UF e padrão na tabela abaixo.',
                })}
              </p>
            </div>
          ) : estimatorQuery.data ? (
            <div className="mt-4 space-y-3">
              {/* Resultado Principal & Faixa */}
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-oe-blue/20 bg-oe-blue/5 p-3">
                  <p className="text-2xs font-medium uppercase tracking-wide text-oe-blue">
                    {t('price_index.cub_rate_base', { defaultValue: 'CUB Unitário Referencial' })}
                  </p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-content-primary">
                    {money(locale, estimatorQuery.data.cub_sqm)}
                    <span className="ml-1 text-xs font-normal text-content-tertiary">/m²</span>
                  </p>
                  <p className="mt-0.5 text-2xs text-content-tertiary">
                    {estimatorQuery.data.uf} · {estimatorQuery.data.project_standard} · {estimatorQuery.data.reference_month}
                  </p>
                </div>

                <div className="rounded-lg border border-semantic-success/20 bg-semantic-success/5 p-3">
                  <p className="text-2xs font-medium uppercase tracking-wide text-semantic-success">
                    {t('price_index.cub_estimated_total', { defaultValue: 'Custo Total Estimado' })}
                  </p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-content-primary">
                    {money(locale, estimatorQuery.data.estimated_total)}
                  </p>
                  <p className="mt-0.5 text-2xs text-content-tertiary">
                    {estimatorQuery.data.area_sqm} m² calculados
                  </p>
                </div>

                <div className="rounded-lg border border-border-light bg-surface-secondary/40 p-3">
                  <p className="text-2xs font-medium uppercase tracking-wide text-content-tertiary">
                    {t('price_index.cub_range_label', {
                      defaultValue: 'Faixa Paramétrica (±{{margin}}%)',
                      margin: estimatorQuery.data.adjustment_pct,
                    })}
                  </p>
                  <div className="mt-1 flex items-baseline justify-between text-xs tabular-nums text-content-primary">
                    <span>
                      <span className="text-2xs text-content-tertiary">Mín: </span>
                      {money(locale, estimatorQuery.data.range_min)}
                    </span>
                    <span>
                      <span className="text-2xs text-content-tertiary">Máx: </span>
                      {money(locale, estimatorQuery.data.range_max)}
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-light">
                    <div className="h-full bg-oe-blue" style={{ width: '100%' }} />
                  </div>
                </div>
              </div>

              {/* Quebra por componentes */}
              <div className="rounded-lg border border-border-light bg-surface-secondary/20 p-3">
                <p className="text-2xs font-semibold uppercase tracking-wide text-content-tertiary">
                  {t('price_index.cub_breakdown_label', {
                    defaultValue: 'Composição Paramétrica Estimada',
                  })}
                </p>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 text-xs">
                  <div className="rounded border border-border-light/60 bg-surface-primary p-2">
                    <span className="text-2xs text-content-tertiary">
                      {t('price_index.cub_material', { defaultValue: 'Material' })}
                    </span>
                    <p className="font-semibold tabular-nums text-content-primary">
                      {money(locale, estimatorQuery.data.material_total)}
                    </p>
                  </div>
                  <div className="rounded border border-border-light/60 bg-surface-primary p-2">
                    <span className="text-2xs text-content-tertiary">
                      {t('price_index.cub_labor', { defaultValue: 'Mão de obra' })}
                    </span>
                    <p className="font-semibold tabular-nums text-content-primary">
                      {money(locale, estimatorQuery.data.labor_total)}
                    </p>
                  </div>
                  <div className="rounded border border-border-light/60 bg-surface-primary p-2">
                    <span className="text-2xs text-content-tertiary">
                      {t('price_index.cub_admin', { defaultValue: 'Despesas adm.' })}
                    </span>
                    <p className="font-semibold tabular-nums text-content-primary">
                      {money(locale, estimatorQuery.data.administrative_total)}
                    </p>
                  </div>
                  <div className="rounded border border-border-light/60 bg-surface-primary p-2">
                    <span className="text-2xs text-content-tertiary">
                      {t('price_index.cub_equipment', { defaultValue: 'Equipamentos' })}
                    </span>
                    <p className="font-semibold tabular-nums text-content-primary">
                      {money(locale, estimatorQuery.data.equipment_total)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Atribuição & Exclusões */}
              <div className="rounded-lg border border-border-light bg-surface-secondary/40 p-2.5">
                <p className="text-2xs font-medium text-content-secondary">
                  {estimatorQuery.data.attribution}
                </p>
                <p className="mt-0.5 text-2xs text-content-tertiary">
                  {estimatorQuery.data.exclusions}
                </p>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {lastSkipped.length > 0 && (
        <div className="mt-3 rounded-lg border border-semantic-warning/30 bg-semantic-warning-bg px-3 py-2">
          <p className="text-xs font-medium text-semantic-warning">
            {t('price_index.cub_skipped_title', {
              defaultValue: 'Some lines were not imported:',
            })}
          </p>
          <ul className="mt-1 list-disc pl-4 text-2xs text-content-secondary">
            {lastSkipped.map((item) => (
              <li key={`${item.line}-${item.message}`}>
                {t('price_index.cub_skipped_line', { defaultValue: 'Line {{line}}: {{message}}', line: item.line, message: item.message })}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Manual form ───────────────────────────────────────────────── */}
      {form && (
        <form
          className="mt-4 rounded-lg border border-border-light p-3"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate(form);
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-xs font-semibold text-content-primary">
              {form.id
                ? t('price_index.cub_edit_title', { defaultValue: 'Edit CUB value' })
                : t('price_index.cub_new_title', { defaultValue: 'New CUB value' })}
            </h4>
            <Button type="button" variant="ghost" size="sm" icon={<X size={14} />} onClick={() => setForm(null)}>
              {t('common.cancel', { defaultValue: 'Cancel' })}
            </Button>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_month', { defaultValue: 'Competence' })}
              <input
                type="month"
                required
                value={form.reference_month}
                onChange={(event) => setForm({ ...form, reference_month: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_uf', { defaultValue: 'UF' })}
              <select
                value={form.uf}
                onChange={(event) => setForm({ ...form, uf: event.target.value })}
                className="oe-select mt-1 w-full text-xs"
              >
                {UFS.map((uf) => (
                  <option key={uf} value={uf}>{uf}</option>
                ))}
              </select>
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_standard', { defaultValue: 'Standard (NBR 12.721)' })}
              <input
                list="cub-standards"
                required
                value={form.project_standard}
                onChange={(event) => setForm({ ...form, project_standard: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
              <datalist id="cub-standards">
                {STANDARDS.map((standard) => (
                  <option key={standard} value={standard} />
                ))}
              </datalist>
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_regime', { defaultValue: 'Tax regime' })}
              <select
                value={form.tax_regime}
                onChange={(event) =>
                  setForm({ ...form, tax_regime: event.target.value as FormState['tax_regime'] })
                }
                className="oe-select mt-1 w-full text-xs"
              >
                <option value="nao_desonerado">
                  {t('price_index.cub_regime_nao', { defaultValue: 'Not exempt (oneração)' })}
                </option>
                <option value="desonerado">
                  {t('price_index.cub_regime_des', { defaultValue: 'Exempt (desonerado)' })}
                </option>
              </select>
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_total', { defaultValue: 'CUB R$/m²' })}
              <input
                required
                inputMode="decimal"
                value={form.total_sqm}
                onChange={(event) => setForm({ ...form, total_sqm: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
            </label>
            {(['material', 'labor', 'administrative', 'equipment'] as const).map((key) => (
              <label key={key} className="text-2xs text-content-tertiary">
                {t(`price_index.cub_${key}`, {
                  defaultValue:
                    key === 'material'
                      ? 'Material'
                      : key === 'labor'
                        ? 'Labour'
                        : key === 'administrative'
                          ? 'Administrative'
                          : 'Equipment',
                })}
                <input
                  inputMode="decimal"
                  value={form[key]}
                  onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
                />
              </label>
            ))}
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_source', { defaultValue: 'Source (Sinduscon / CBIC)' })}
              <input
                value={form.source_name}
                onChange={(event) => setForm({ ...form, source_name: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_source_url', { defaultValue: 'Source URL' })}
              <input
                type="url"
                value={form.source_url}
                onChange={(event) => setForm({ ...form, source_url: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
            </label>
            <label className="text-2xs text-content-tertiary">
              {t('price_index.cub_published', { defaultValue: 'Published on' })}
              <input
                type="date"
                value={form.published_at}
                onChange={(event) => setForm({ ...form, published_at: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
            </label>
            <label className="text-2xs text-content-tertiary sm:col-span-2">
              {t('price_index.cub_notes', { defaultValue: 'Notes' })}
              <input
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
                className="mt-1 w-full rounded-md border border-border bg-surface-primary px-2 py-1.5 text-xs text-content-primary"
              />
            </label>
          </div>
          {breakdownMismatch && (
            <p className="mt-2 text-xs text-semantic-error">
              {t('price_index.cub_breakdown_mismatch', {
                defaultValue:
                  'Material + labour + administrative + equipment must equal the CUB total (currently {{sum}} vs {{total}}).',
                sum: money(locale, componentSum),
                total: money(locale, totalValue),
              })}
            </p>
          )}
          <div className="mt-3 flex justify-end">
            <Button
              type="submit"
              size="sm"
              loading={saveMutation.isPending}
              disabled={breakdownMismatch || totalValue <= 0}
            >
              {t('common.save', { defaultValue: 'Save' })}
            </Button>
          </div>
        </form>
      )}

      {/* ── Filters ───────────────────────────────────────────────────── */}
      <div className="mt-4 flex flex-wrap items-end gap-2" aria-label={filterLabel}>
        <label className="text-2xs text-content-tertiary">
          {t('price_index.cub_uf', { defaultValue: 'UF' })}
          <select
            value={filters.uf}
            onChange={(event) => setFilters({ ...filters, uf: event.target.value })}
            className="oe-select ml-1 text-xs"
          >
            <option value="">{t('price_index.cub_all', { defaultValue: 'All' })}</option>
            {UFS.map((uf) => (
              <option key={uf} value={uf}>{uf}</option>
            ))}
          </select>
        </label>
        <label className="text-2xs text-content-tertiary">
          {t('price_index.cub_month', { defaultValue: 'Competence' })}
          <select
            value={filters.month}
            onChange={(event) => setFilters({ ...filters, month: event.target.value })}
            className="oe-select ml-1 text-xs"
          >
            <option value="">{t('price_index.cub_all_months', { defaultValue: 'All months' })}</option>
            {(monthOptions.length ? monthOptions : []).map((month) => (
              <option key={month} value={month}>{month}</option>
            ))}
          </select>
        </label>
        <label className="text-2xs text-content-tertiary">
          {t('price_index.cub_standard', { defaultValue: 'Standard (NBR 12.721)' })}
          <select
            value={filters.standard}
            onChange={(event) => setFilters({ ...filters, standard: event.target.value })}
            className="oe-select ml-1 text-xs"
          >
            <option value="">{t('price_index.cub_all', { defaultValue: 'All' })}</option>
            {(catalog?.standards.length ? catalog.standards : STANDARDS).map((standard) => (
              <option key={standard} value={standard}>{standard}</option>
            ))}
          </select>
        </label>
        <label className="text-2xs text-content-tertiary">
          {t('price_index.cub_regime', { defaultValue: 'Tax regime' })}
          <select
            value={filters.regime}
            onChange={(event) => setFilters({ ...filters, regime: event.target.value })}
            className="oe-select ml-1 text-xs"
          >
            <option value="">{t('price_index.cub_all', { defaultValue: 'All' })}</option>
            <option value="desonerado">
              {t('price_index.cub_regime_des', { defaultValue: 'Exempt (desonerado)' })}
            </option>
            <option value="nao_desonerado">
              {t('price_index.cub_regime_nao', { defaultValue: 'Not exempt (oneração)' })}
            </option>
          </select>
        </label>
        {(filters.uf || filters.month || filters.standard || filters.regime) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setFilters({ uf: '', month: '', standard: '', regime: '' })}
          >
            {t('price_index.cub_clear', { defaultValue: 'Clear' })}
          </Button>
        )}
      </div>

      {/* ── Table ─────────────────────────────────────────────────────── */}
      <div className="mt-3">
        {listQuery.isLoading ? (
          <SkeletonTable rows={4} />
        ) : listQuery.isError ? (
          <ErrorState
            title={t('price_index.cub_load_error', { defaultValue: 'Could not load the CUB values' })}
            onRetry={() => void listQuery.refetch()}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<Landmark size={22} />}
            title={t('price_index.cub_empty', { defaultValue: 'No CUB value for this selection' })}
            description={
              canManage
                ? t('price_index.cub_empty_admin', {
                    defaultValue:
                      'Import the curated CSV from the official bulletin or add one value by hand.',
                  })
                : t('price_index.cub_empty_user', {
                    defaultValue: 'An administrator has not published this competence yet.',
                  })
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="oe-table-compact w-full">
                <thead>
                  <tr className="text-content-quaternary">
                    <th>{t('price_index.cub_month', { defaultValue: 'Competence' })}</th>
                    <th>{t('price_index.cub_uf', { defaultValue: 'UF' })}</th>
                    <th>{t('price_index.cub_standard', { defaultValue: 'Standard' })}</th>
                    <th>{t('price_index.cub_regime', { defaultValue: 'Regime' })}</th>
                    <th className="text-right">{t('price_index.cub_total', { defaultValue: 'R$/m²' })}</th>
                    <th>{t('price_index.cub_source', { defaultValue: 'Source' })}</th>
                    <th className="w-24">{t('price_index.cub_published', { defaultValue: 'Published' })}</th>
                    <th className="w-20 text-center">
                      {t('price_index.cub_status', { defaultValue: 'Checked' })}
                    </th>
                    {canManage && <th className="w-24 text-right">{t('common.actions', { defaultValue: 'Actions' })}</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const isSelected = row.id === activeRow?.id;
                    const isExample = Boolean(
                      row.notes &&
                        (row.notes.toUpperCase().includes('EXEMPLO') ||
                          row.notes.toUpperCase().includes('DEMO')),
                    );
                    return (
                      <tr
                        key={row.id}
                        onClick={() => setSelectedRowId(row.id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-oe-blue/10 font-medium'
                            : 'hover:bg-surface-secondary/50'
                        }`}
                      >
                        <td className="tabular-nums">{row.reference_month}</td>
                        <td>
                          <span className="font-medium text-content-primary">{row.uf}</span>
                          {row.regional_code && (
                            <span className="ml-1 text-2xs text-content-quaternary">
                              {row.regional_code}
                            </span>
                          )}
                          {isExample && (
                            <span className="ml-1.5 inline-block rounded bg-surface-secondary px-1.5 py-0.2 text-2xs font-semibold uppercase tracking-wider text-content-tertiary">
                              Exemplo
                            </span>
                          )}
                        </td>
                        <td>{row.project_standard}</td>
                        <td className="text-2xs">
                          {row.tax_regime === 'desonerado'
                            ? t('price_index.cub_regime_des', { defaultValue: 'Exempt (desonerado)' })
                            : t('price_index.cub_regime_nao', { defaultValue: 'Not exempt (oneração)' })}
                        </td>
                        <td className="text-right font-medium tabular-nums">
                          {money(locale, row.total_sqm)}
                        </td>
                        <td className="max-w-[220px] truncate text-2xs" title={row.attribution}>
                          {row.source_url ? (
                            <a
                              href={row.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="underline"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {row.sinduscon_name || row.source_name || 'Sinduscon/CBIC'}
                            </a>
                          ) : (
                            row.sinduscon_name || row.source_name || 'Sinduscon/CBIC'
                          )}
                        </td>
                        <td className="text-2xs tabular-nums">{row.published_at ?? '—'}</td>
                        <td className="text-center">
                          {row.verified ? (
                            <Badge variant="success" size="sm">
                              <BadgeCheck size={11} className="mr-0.5" aria-hidden />
                              {t('price_index.cub_verified', { defaultValue: 'Checked' })}
                            </Badge>
                          ) : (
                            <Badge variant="warning" size="sm">
                              {t('price_index.cub_unverified', { defaultValue: 'Draft' })}
                            </Badge>
                          )}
                        </td>
                        {canManage && (
                          <td className="text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="inline-flex items-center gap-1">
                            <button
                              type="button"
                              className="rounded p-1 text-content-tertiary hover:bg-surface-secondary hover:text-content-primary"
                              title={t('common.edit', { defaultValue: 'Edit' })}
                              onClick={() => setForm(fromRow(row))}
                            >
                              <Pencil size={13} />
                            </button>
                            <button
                              type="button"
                              className="rounded p-1 text-content-tertiary hover:bg-surface-secondary hover:text-content-primary"
                              title={
                                row.verified
                                  ? t('price_index.cub_unverify', { defaultValue: 'Back to draft' })
                                  : t('price_index.cub_mark_verified', { defaultValue: 'Mark as checked' })
                              }
                              onClick={() =>
                                verifyMutation.mutate({ id: row.id, verified: !row.verified })
                              }
                            >
                              <BadgeCheck size={13} />
                            </button>
                            <button
                              type="button"
                              className="rounded p-1 text-content-tertiary hover:bg-semantic-error-bg hover:text-semantic-error"
                              title={t('common.delete', { defaultValue: 'Delete' })}
                              onClick={() => {
                                if (window.confirm(
                                  t('price_index.cub_delete_confirm', {
                                    defaultValue: 'Delete this CUB value?',
                                  }),
                                )) {
                                  deleteMutation.mutate(row.id);
                                }
                              }}
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-2xs text-content-quaternary">
              {t('price_index.cub_count', { defaultValue: '{{count}} values stored', count: total })}
            </p>
          </>
        )}
      </div>

      <div className="mt-3 flex justify-end">
        <InfoHint text={`${attribution} ${CUB_EXCLUSIONS}`} />
      </div>
    </Card>
  );
}
