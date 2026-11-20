// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
/**
 * Lógica de cálculo e classificação para a Curva ABC e Análise de Pareto.
 *
 * Padrão brasileiro e internacional:
 * - Classe A: Itens mais representativos (padrão até 80% do valor acumulado)
 * - Classe B: Itens de representatividade intermediária (padrão de 80% a 95% do valor acumulado)
 * - Classe C: Itens de menor representatividade econômica (padrão de 95% a 100% do valor acumulado)
 */

export type AbcClass = 'A' | 'B' | 'C';

export interface RawCurvaAbcInput {
  id: string;
  code?: string | null;
  description: string;
  unit?: string | null;
  quantity?: number | null;
  unit_rate?: number | null;
  total_cost?: number | null;
  category?: string | null;
}

export interface CurvaAbcItem {
  id: string;
  index: number;
  code: string;
  description: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  total_cost: number;
  percentage: number;
  cumulative_percentage: number;
  abc_class: AbcClass;
  category?: string;
}

export interface ClassMetrics {
  count: number;
  total: number;
  percentage: number;
  cumulative_percentage: number;
}

export interface CurvaAbcResult {
  items: CurvaAbcItem[];
  grand_total: number;
  total_count: number;
  cutoff_a: number;
  cutoff_b: number;
  summary: {
    A: ClassMetrics;
    B: ClassMetrics;
    C: ClassMetrics;
  };
}

/**
 * Normaliza valores decimais para evitar desvios de arredondamento em centavos.
 */
export function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function round4(value: number): number {
  return Math.round((value + Number.EPSILON) * 10000) / 10000;
}

/**
 * Calcula e classifica os itens para a Curva ABC segundo a regra de Pareto.
 *
 * @param inputs Lista de itens brutos (serviços ou insumos)
 * @param cutoffA Limite superior da Classe A em porcentagem (padrão: 80)
 * @param cutoffB Limite superior da Classe B em porcentagem (padrão: 95)
 */
export function calculateCurvaAbc(
  inputs: RawCurvaAbcInput[],
  cutoffA = 80,
  cutoffB = 95,
): CurvaAbcResult {
  const safeCutoffA = Math.max(1, Math.min(cutoffA, 98));
  const safeCutoffB = Math.max(safeCutoffA + 1, Math.min(cutoffB, 99));

  // Filtra itens com valores válidos e positivos
  const prepared = inputs
    .map((input) => {
      const qty = Number(input.quantity) || 0;
      const rate = Number(input.unit_rate) || 0;
      const explicitTotal = Number(input.total_cost);
      const total = Number.isFinite(explicitTotal) && explicitTotal !== 0 ? explicitTotal : qty * rate;
      return {
        id: input.id,
        code: (input.code || '').trim(),
        description: (input.description || '').trim() || 'Item sem descrição',
        unit: (input.unit || 'un').trim(),
        quantity: qty,
        unit_rate: rate,
        total_cost: round2(Math.max(0, total)),
        category: input.category || undefined,
      };
    })
    .filter((item) => item.total_cost > 0);

  // Ordena por custo total decrescente
  prepared.sort((a, b) => {
    if (b.total_cost !== a.total_cost) {
      return b.total_cost - a.total_cost;
    }
    return a.description.localeCompare(b.description);
  });

  const grand_total = round2(prepared.reduce((sum, item) => sum + item.total_cost, 0));

  let runningCumulative = 0;
  const items: CurvaAbcItem[] = [];

  for (let i = 0; i < prepared.length; i++) {
    const raw = prepared[i]!;
    const pct = grand_total > 0 ? (raw.total_cost / grand_total) * 100 : 0;

    // Regra clássica de Pareto (conforme router.py e padrão de engenharia):
    // Se o acumulado antes deste item era menor que cutoffA, ele pertence à Classe A.
    // Se o acumulado antes era menor que cutoffB, pertence à Classe B.
    // Caso contrário, Classe C.
    let abc_class: AbcClass = 'C';
    if (runningCumulative < safeCutoffA) {
      abc_class = 'A';
    } else if (runningCumulative < safeCutoffB) {
      abc_class = 'B';
    } else {
      abc_class = 'C';
    }

    runningCumulative += pct;
    const finalCumulative = i === prepared.length - 1 ? 100 : Math.min(100, runningCumulative);

    items.push({
      id: raw.id,
      index: i + 1,
      code: raw.code || String(i + 1).padStart(2, '0'),
      description: raw.description,
      unit: raw.unit,
      quantity: raw.quantity,
      unit_rate: raw.unit_rate,
      total_cost: raw.total_cost,
      percentage: round2(pct),
      cumulative_percentage: round2(finalCumulative),
      abc_class,
      category: raw.category,
    });
  }

  // Agrega métricas por classe
  const summary = {
    A: { count: 0, total: 0, percentage: 0, cumulative_percentage: 0 },
    B: { count: 0, total: 0, percentage: 0, cumulative_percentage: 0 },
    C: { count: 0, total: 0, percentage: 0, cumulative_percentage: 0 },
  };

  for (const item of items) {
    const target = summary[item.abc_class];
    target.count += 1;
    target.total += item.total_cost;
  }

  summary.A.total = round2(summary.A.total);
  summary.B.total = round2(summary.B.total);
  summary.C.total = round2(summary.C.total);

  if (grand_total > 0) {
    summary.A.percentage = round2((summary.A.total / grand_total) * 100);
    summary.B.percentage = round2((summary.B.total / grand_total) * 100);
    summary.C.percentage = round2(Math.max(0, 100 - summary.A.percentage - summary.B.percentage));

    summary.A.cumulative_percentage = summary.A.percentage;
    summary.B.cumulative_percentage = round2(summary.A.percentage + summary.B.percentage);
    summary.C.cumulative_percentage = 100;
  }

  return {
    items,
    grand_total,
    total_count: items.length,
    cutoff_a: safeCutoffA,
    cutoff_b: safeCutoffB,
    summary,
  };
}

/**
 * Retorna os rótulos em português para os tipos de insumo.
 */
export function getCategoriaLabel(category?: string): string {
  if (!category) return 'Outros';
  const norm = category.toLowerCase().trim();
  switch (norm) {
    case 'material':
      return 'Material';
    case 'labor':
      return 'Mão de Obra';
    case 'equipment':
    case 'machinery':
      return 'Equipamento / Máquina';
    case 'subcontractor':
      return 'Empreiteiro / Terceirizado';
    case 'other':
    default:
      return 'Outros';
  }
}
