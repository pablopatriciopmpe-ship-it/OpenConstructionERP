// Orçamento rápido: cliente tipado da API /api/v1/boq/quick-budget.
// Valores monetários e quantidades trafegam como texto decimal (convenção da plataforma).

import { ApiError, apiGet, apiPost } from '@/shared/lib/api';

const BASE = '/v1/boq/quick-budget';

export type QuickBudgetTipo = 'casa_nova' | 'comercial' | 'reforma';
export type QuickBudgetRegime = 'desonerado' | 'nao_desonerado';
export type QuickBudgetModo = 'completo' | 'so_mao_de_obra';

export interface QbServico {
  id: string;
  descricao: string;
  unidade: string;
  sinapi: string | null;
  preco_informado: boolean;
  nota: string;
}

export interface QbCategoria {
  id: string;
  rotulo: string;
  servicos: QbServico[];
}

export interface QbCatalogo {
  versao: string;
  sinapi_referencia: string;
  tipos: string[];
  cub_aplicavel: boolean;
  categorias: QbCategoria[];
}

export interface QbItemIn {
  servico: string;
  quantidade: string;
  preco_unitario?: string;
}

export interface QbBdiIn {
  ac: string;
  s: string;
  r: string;
  g: string;
  df: string;
  l: string;
  taxes: { name: string; percentage: string }[];
}

export interface QbPlanIn {
  tipo: QuickBudgetTipo;
  uf: string;
  regime: QuickBudgetRegime;
  modo: QuickBudgetModo;
  itens: QbItemIn[];
}

export interface QbGenerateIn extends QbPlanIn {
  project_id: string;
  nome: string;
  ignorar_indisponiveis?: boolean;
  bdi?: QbBdiIn | null;
}

export type QbItemStatus = 'ok' | 'indisponivel' | 'sem_mao_de_obra';

export interface QbItemOut {
  servico: string;
  categoria: string;
  categoria_rotulo: string;
  descricao: string;
  unidade: string;
  quantidade: string;
  sinapi: string | null;
  sinapi_descricao: string;
  preco_unitario: string;
  total: string;
  material: string;
  mao_de_obra: string;
  equipamento: string;
  terceiros: string;
  status: QbItemStatus;
  motivo: string;
}

export interface QbPlanOut {
  tipo: string;
  uf: string;
  regime: string;
  modo: string;
  sinapi_referencia: string;
  total: string;
  por_tipo: Record<string, string>;
  itens: QbItemOut[];
}

export interface QbBdiOut {
  configured: boolean;
  bdi_percent?: string;
  bdi_amount?: string;
  price_with_bdi?: string;
}

export interface QbGenerateOut extends QbPlanOut {
  boq_id: string;
  bdi?: QbBdiOut;
}

export interface QbCubOut {
  tipo: string;
  uf: string;
  regime: string;
  padrao: string;
  competencia: string;
  area_m2: string;
  cub_por_m2: string;
  total: string;
  por_parcela: Record<string, string>;
  fonte: string;
  aviso: string;
}

export interface QbCubParams {
  tipo: QuickBudgetTipo;
  uf: string;
  area_m2: string;
  regime: QuickBudgetRegime;
  padrao: string;
}

export function getQuickBudgetCatalog(tipo: QuickBudgetTipo): Promise<QbCatalogo> {
  return apiGet<QbCatalogo>(`${BASE}/catalog/?tipo=${encodeURIComponent(tipo)}`);
}

export function previewQuickBudget(body: QbPlanIn): Promise<QbPlanOut> {
  return apiPost<QbPlanOut, QbPlanIn>(`${BASE}/preview/`, body);
}

export function generateQuickBudget(body: QbGenerateIn): Promise<QbGenerateOut> {
  return apiPost<QbGenerateOut, QbGenerateIn>(`${BASE}/generate/`, body);
}

export function getQuickBudgetCub(p: QbCubParams): Promise<QbCubOut> {
  const qs = new URLSearchParams({
    tipo: p.tipo,
    uf: p.uf,
    area_m2: p.area_m2,
    regime: p.regime,
    padrao: p.padrao,
  });
  return apiGet<QbCubOut>(`${BASE}/cub/?${qs.toString()}`);
}

export interface QbErrorInfo {
  code: string;
  message: string;
  status: number;
}

/** Lê `{detail:{code,message}}` dos erros do Orçamento rápido (409 SINAPI não importado, 404 CUB, 422...). */
export function readQuickBudgetError(err: unknown): QbErrorInfo | null {
  if (!(err instanceof ApiError)) return null;
  const body = err.body as { detail?: unknown } | null;
  const detail = body && typeof body === 'object' ? body.detail : undefined;
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const d = detail as { code?: unknown; message?: unknown };
    return {
      code: String(d.code ?? ''),
      message: typeof d.message === 'string' ? d.message : err.message,
      status: err.status,
    };
  }
  return { code: '', message: err.message, status: err.status };
}
