// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';
import type { CurvaAbcItem } from './curvaAbcCalculations';
import { formatMoneyPtBr, formatPercentPtBr } from './curvaAbcExport';

export interface CurvaAbcChartProps {
  items: CurvaAbcItem[];
  cutoffA: number;
  cutoffB: number;
}

const COLORS = {
  classA: '#156D61', // Verde Evolux (#156D61)
  classB: '#163953', // Azul Evolux (#163953)
  classC: '#8CA1A9', // Muted neutro (#8CA1A9)
  line: '#E05D38',   // Linha de acumulado em destaque
  grid: '#CED8D5',   // Divisor dos tokens
};

function formatCompactMoney(val: number): string {
  if (val >= 1_000_000) {
    return `R$ ${(val / 1_000_000).toFixed(1)}M`;
  }
  if (val >= 1_000) {
    return `R$ ${(val / 1_000).toFixed(0)}k`;
  }
  return `R$ ${val.toFixed(0)}`;
}

interface TooltipPayloadItem {
  payload: CurvaAbcItem;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}

function CustomParetoTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  const badgeBg =
    data.abc_class === 'A'
      ? 'bg-[#E2F2EC] text-[#12594D] border-[#156D61]/30'
      : data.abc_class === 'B'
      ? 'bg-[#DCEEE9] text-[#163953] border-[#163953]/30'
      : 'bg-[#F6F6EF] text-[#465C69] border-[#CED8D5]';

  return (
    <div className="rounded-lg border border-[#CED8D5] bg-white p-3 shadow-md max-w-xs text-xs">
      <div className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-[#CED8D5]">
        <span className="font-semibold text-[#163953] truncate">{data.code ? `${data.code} · ` : ''}{data.description}</span>
        <span className={`inline-block px-1.5 py-0.5 rounded text-2xs font-bold border ${badgeBg}`}>
          Classe {data.abc_class}
        </span>
      </div>
      <div className="space-y-1 text-content-secondary">
        <div className="flex justify-between">
          <span>Valor:</span>
          <span className="font-medium text-[#163953]">{formatMoneyPtBr(data.total_cost)}</span>
        </div>
        <div className="flex justify-between">
          <span>% Individual:</span>
          <span className="font-medium text-[#163953]">{formatPercentPtBr(data.percentage)}</span>
        </div>
        <div className="flex justify-between">
          <span>% Acumulado:</span>
          <span className="font-medium text-[#E05D38]">{formatPercentPtBr(data.cumulative_percentage)}</span>
        </div>
      </div>
    </div>
  );
}

export function CurvaAbcChart({ items, cutoffA, cutoffB }: CurvaAbcChartProps) {
  const [maxDisplay, setMaxDisplay] = useState<number>(20);

  const displayData = useMemo(() => {
    if (items.length <= maxDisplay) return items;
    return items.slice(0, maxDisplay);
  }, [items, maxDisplay]);

  if (!items.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-[#CED8D5] bg-[#F6F6EF]/50 text-sm text-[#465C69]">
        Nenhum item com valor para compor o gráfico de Pareto.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#CED8D5] bg-white p-4 shadow-sm space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-[#163953]">Gráfico de Pareto · Distribuição de Custo e % Acumulado</h4>
          <p className="text-xs text-[#465C69]">
            Barras representam o valor individual (escala à esquerda) e a linha representa a curva acumulada (escala à direita).
          </p>
        </div>
        {items.length > 20 && (
          <div className="flex items-center gap-1.5 text-xs text-[#465C69]">
            <span>Exibir:</span>
            <div className="inline-flex rounded-md border border-[#CED8D5] p-0.5 bg-[#F6F6EF]">
              {[20, 50, 100].map((limit) => (
                <button
                  key={limit}
                  type="button"
                  onClick={() => setMaxDisplay(limit)}
                  className={`rounded px-2 py-0.5 font-medium transition-colors ${
                    maxDisplay === limit
                      ? 'bg-white text-[#163953] shadow-xs'
                      : 'text-[#465C69] hover:text-[#163953]'
                  }`}
                >
                  Top {limit}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setMaxDisplay(items.length)}
                className={`rounded px-2 py-0.5 font-medium transition-colors ${
                  maxDisplay >= items.length
                    ? 'bg-white text-[#163953] shadow-xs'
                    : 'text-[#465C69] hover:text-[#163953]'
                }`}
              >
                Todos ({items.length})
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="h-72 w-full pt-2" data-testid="curva-abc-pareto-chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={displayData} margin={{ top: 10, right: 35, left: 15, bottom: 45 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} opacity={0.6} />
            <XAxis
              dataKey="description"
              tick={{ fontSize: 10, fill: '#465C69' }}
              angle={-25}
              textAnchor="end"
              interval={0}
              height={45}
              tickFormatter={(val: string) => (val.length > 22 ? val.slice(0, 20) + '…' : val)}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 10, fill: '#465C69' }}
              tickFormatter={formatCompactMoney}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: '#465C69' }}
              tickFormatter={(val) => `${val}%`}
            />
            <Tooltip content={<CustomParetoTooltip />} />
            <ReferenceLine
              yAxisId="right"
              y={cutoffA}
              stroke={COLORS.classA}
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{
                value: `Limite A (${cutoffA}%)`,
                fill: COLORS.classA,
                fontSize: 10,
                position: 'top',
              }}
            />
            <ReferenceLine
              yAxisId="right"
              y={cutoffB}
              stroke={COLORS.classB}
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{
                value: `Limite B (${cutoffB}%)`,
                fill: COLORS.classB,
                fontSize: 10,
                position: 'top',
              }}
            />
            <Bar yAxisId="left" dataKey="total_cost" radius={[3, 3, 0, 0]}>
              {displayData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    entry.abc_class === 'A'
                      ? COLORS.classA
                      : entry.abc_class === 'B'
                      ? COLORS.classB
                      : COLORS.classC
                  }
                />
              ))}
            </Bar>
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="cumulative_percentage"
              stroke={COLORS.line}
              strokeWidth={2.5}
              dot={{ r: 2.5, fill: COLORS.line }}
              activeDot={{ r: 5 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legenda das Classes */}
      <div className="flex flex-wrap items-center justify-center gap-6 pt-1 border-t border-[#CED8D5]/60 text-xs text-[#465C69]">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-xs" style={{ backgroundColor: COLORS.classA }} />
          <span>Classe A (Até {cutoffA}%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-xs" style={{ backgroundColor: COLORS.classB }} />
          <span>Classe B ({cutoffA}% a {cutoffB}%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-xs" style={{ backgroundColor: COLORS.classC }} />
          <span>Classe C (Acima de {cutoffB}%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-0.5 w-4 rounded-full" style={{ backgroundColor: COLORS.line }} />
          <span>% Acumulado</span>
        </div>
      </div>
    </div>
  );
}
