// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP​‌‍⁠​‌‍⁠​‌‍⁠​‌‍⁠
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
/**
 * CostPerAreaBenchmark - a compact strip under the estimate totals that shows
 * the cost per square metre and positions it against the tenant's own past
 * projects.
 *
 * Cost per m2 is the estimate direct cost divided by the gross floor area,
 * taken from the BOQ's $GFA variable. When no $GFA is set there is nothing to
 * divide by, so the strip renders nothing (it never shows a wrong or blank
 * figure). When a $GFA is set the strip always shows the cost per m2; the
 * portfolio comparison is added only when the endpoint has past projects to
 * compare against.
 *
 * Everything is explained on the strip itself through a How it works note, so
 * an estimator understands where the number comes from and what the percentile
 * means without leaving the page.
 */

import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Landmark, Ruler } from 'lucide-react';
import { InfoHint } from '@/shared/ui';
import { fetchCostBenchmark } from '@/features/costs/api';
import { getLatestCub } from '@/features/price-index/api';
import { fmtWithCurrency } from './boqHelpers';
import { fmtFixed } from '@/shared/lib/formatters';

interface CostPerAreaBenchmarkProps {
  /** Estimate direct cost in the project base currency. */
  directCost: number;
  /** Project base currency code, e.g. 'EUR'. */
  currencyCode: string;
  /** Gross floor area in m2 (from the BOQ $GFA variable). Null hides the strip. */
  grossFloorArea: number | null;
  locale: string;
  project?: {
    name?: string;
    address?: { state?: string | null } | null;
    region?: string | null;
  } | null;
}

function deriveUf(project?: { name?: string; address?: { state?: string | null } | null } | null): string {
  if (!project) return 'SP';
  const state = project.address?.state?.trim().toUpperCase();
  if (state && state.length === 2) return state;
  if (state?.includes('SÃO PAULO') || state?.includes('SAO PAULO')) return 'SP';
  if (state?.includes('RIO DE JANEIRO')) return 'RJ';
  if (state?.includes('MINAS GERAIS')) return 'MG';
  const name = project.name?.toUpperCase() ?? '';
  if (name.includes('SÃO PAULO') || name.includes('SAO PAULO') || name.includes(' - SP')) return 'SP';
  if (name.includes('RIO DE JANEIRO') || name.includes(' - RJ')) return 'RJ';
  if (name.includes('MINAS GERAIS') || name.includes('BELO HORIZONTE') || name.includes(' - MG')) return 'MG';
  return 'SP';
}

export function CostPerAreaBenchmark({
  directCost,
  currencyCode,
  grossFloorArea,
  locale,
  project,
}: CostPerAreaBenchmarkProps) {
  const { t } = useTranslation();

  const hasArea = typeof grossFloorArea === 'number' && grossFloorArea > 0 && directCost > 0;
  const costPerM2 = hasArea ? directCost / (grossFloorArea as number) : 0;

  const { data } = useQuery({
    // Round the key so tiny recomputations do not refetch on every keystroke.
    queryKey: ['costs', 'benchmark', currencyCode, Math.round(costPerM2)],
    queryFn: () =>
      fetchCostBenchmark({ cost_per_m2: fmtFixed(costPerM2, 2), currency: currencyCode }),
    enabled: hasArea,
    staleTime: 5 * 60 * 1000,
  });

  const isBrazil =
    currencyCode === 'BRL' ||
    locale?.startsWith('pt') ||
    project?.region === 'BR' ||
    project?.region === 'Brazil';

  const cubUf = useMemo(() => deriveUf(project), [project]);
  const [cubStandard] = useState('R8-N');

  const { data: cubData } = useQuery({
    queryKey: ['price-index', 'cub', 'latest', cubUf, cubStandard, 'nao_desonerado'],
    queryFn: () => getLatestCub(cubUf, cubStandard, 'nao_desonerado'),
    enabled: hasArea && isBrazil,
    staleTime: 5 * 60 * 1000,
  });

  const cubSqm = cubData ? Number(cubData.total_sqm) : null;
  const cubDelta =
    cubSqm && cubSqm > 0 ? ((costPerM2 - cubSqm) / cubSqm) * 100 : null;

  const areaFmt = useMemo(
    () => new Intl.NumberFormat(locale || undefined, { maximumFractionDigits: 0 }),
    [locale],
  );

  if (!hasArea) return null;

  const portfolio = data?.own_portfolio ?? null;
  const median = portfolio ? Number(portfolio.median) : null;
  const percentile =
    typeof data?.percentile_vs_own === 'number' ? Math.round(data.percentile_vs_own) : null;

  const helpText = t('boq.cost_per_area_help', {
    defaultValue:
      'Cost per m2 is the Orçamento direct cost divided by the gross floor area, taken from the $GFA variable. The comparison positions that figure against your own past projects that recorded both a cost and an area. The percentile is how many of those projects came in below this Orçamento, so a lower percentile means a cheaper Orçamento than most of your work.',
  });

  return (
    <div
      className="mt-3 rounded-xl border border-border-light bg-surface-primary px-4 py-3"
      data-testid="boq-cost-per-area-strip"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-oe-blue-subtle text-oe-blue-text">
            <Ruler size={16} strokeWidth={1.75} />
          </span>
          <div>
            <p className="text-2xs uppercase tracking-wide text-content-tertiary">
              {t('boq.cost_per_area_label', { defaultValue: 'Cost per m2' })}
            </p>
            <p className="text-lg font-semibold text-content-primary tabular-nums">
              {fmtWithCurrency(costPerM2, locale || 'de-DE', currencyCode)}
              <span className="ml-1 text-xs font-normal text-content-tertiary">
                {t('boq.cost_per_area_over', {
                  defaultValue: 'over {{area}} m2',
                  area: areaFmt.format(grossFloorArea as number),
                })}
              </span>
            </p>
          </div>
        </div>

        {portfolio && median !== null && (
          <div className="min-w-0">
            <p className="text-2xs uppercase tracking-wide text-content-tertiary">
              {t('boq.cost_per_area_portfolio', { defaultValue: 'Your portfolio' })}
            </p>
            <p className="text-sm text-content-secondary">
              {t('boq.cost_per_area_median', {
                defaultValue: 'median {{median}}',
                median: fmtWithCurrency(median, locale || 'de-DE', data?.currency || currencyCode),
              })}
              {percentile !== null && (
                <span
                  className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-semibold tabular-nums ${
                    percentile <= 50
                      ? 'bg-semantic-success/15 text-semantic-success'
                      : percentile <= 75
                        ? 'bg-semantic-warning/15 text-semantic-warning'
                        : 'bg-semantic-error/15 text-semantic-error'
                  }`}
                  title={data?.explanation || undefined}
                >
                  {t('boq.cost_per_area_percentile', {
                    defaultValue: '{{pct}}th percentile',
                    pct: percentile,
                  })}
                </span>
              )}
            </p>
          </div>
        )}

        {/* ── CUB Benchmark Comparison ──────────────────────────────── */}
        {cubData && cubSqm !== null && (
          <div
            className="min-w-0 border-l border-border-light pl-4"
            data-testid="boq-cub-benchmark-chip"
          >
            <div className="flex items-center gap-1.5">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-oe-blue">
                <Landmark size={12} strokeWidth={2} />
              </span>
              <p className="text-2xs uppercase tracking-wide text-content-tertiary">
                {t('boq.cub_reference_label', {
                  defaultValue: 'CUB {{uf}} · {{std}}',
                  uf: cubData.uf,
                  std: cubData.project_standard,
                })}
              </p>
              <span className="text-2xs text-content-tertiary">
                ({cubData.reference_month})
              </span>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-content-primary tabular-nums">
                {fmtWithCurrency(cubSqm, locale || 'pt-BR', 'BRL')}
                <span className="ml-1 text-2xs font-normal text-content-tertiary">/m²</span>
              </p>
              {cubDelta !== null && (
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-semibold tabular-nums ${
                    Math.abs(cubDelta) <= 5
                      ? 'bg-semantic-success/15 text-semantic-success'
                      : cubDelta > 5
                        ? 'bg-semantic-warning/15 text-semantic-warning'
                        : 'bg-oe-blue/15 text-oe-blue'
                  }`}
                  title={`Diferença de ${cubDelta >= 0 ? '+' : ''}${cubDelta.toFixed(1)}% em relação ao CUB ${cubData.uf}`}
                >
                  Δ {cubDelta >= 0 ? `+${cubDelta.toFixed(1)}%` : `${cubDelta.toFixed(1)}%`}{' '}
                  {cubDelta >= 0
                    ? t('boq.cub_above', { defaultValue: 'acima' })
                    : t('boq.cub_below', { defaultValue: 'abaixo' })}
                </span>
              )}
              <InfoHint
                text={`${cubData.attribution}\n\n${t('boq.cub_disclaimer', {
                  defaultValue:
                    'O CUB não inclui fundações, elevadores, instalações especiais, projetos e BDI. Comparação direta com o custo direto de execução.',
                })}`}
              />
            </div>
          </div>
        )}

        <div className="ml-auto">
          <InfoHint text={helpText} />
        </div>
      </div>

      {portfolio?.note && (
        <p className="mt-2 text-xs text-content-tertiary">{portfolio.note}</p>
      )}
    </div>
  );
}

export default CostPerAreaBenchmark;
