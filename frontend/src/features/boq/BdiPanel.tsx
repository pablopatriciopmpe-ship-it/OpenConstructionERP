import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Calculator, Loader2 } from 'lucide-react';
import { Badge, Button, Card, Input } from '@/shared/ui';
import { useToastStore } from '@/stores/useToastStore';
import { boqApi, type BdiComponentValues, type BdiResponse } from './api';

const INITIAL: BdiComponentValues = { ac: '', s: '', r: '', g: '', df: '', l: '', taxes: [] };
const brl = (value: string | number | null | undefined) =>
  Number(value ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const pct = (value: string | number | null | undefined) =>
  `${Number(value ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}%`;

export function BdiPanel({
  boqId,
  directCost,
  readOnly = false,
}: {
  boqId: string;
  directCost?: number;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const addToast = useToastStore((s) => s.addToast);
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ['boq-bdi', boqId], queryFn: () => boqApi.getBdi(boqId) });
  const [form, setForm] = useState<BdiComponentValues>(INITIAL);

  useEffect(() => {
    if (query.data) {
      const d = query.data as Record<string, any>;
      const comps = d.components as Record<string, any> | undefined;
      setForm({
        ac: d.ac ?? comps?.ac ?? '4.0000',
        s: d.s ?? comps?.s ?? '0.8000',
        r: d.r ?? comps?.r ?? '1.2700',
        g: d.g ?? comps?.g ?? '0.4000',
        df: d.df ?? comps?.df ?? '1.2300',
        l: d.l ?? comps?.l ?? '7.4000',
        taxes: d.taxes ?? comps?.taxes ?? [],
      });
    }
  }, [query.data]);

  const save = useMutation({
    mutationFn: () => boqApi.updateBdi(boqId, form),
    onSuccess: (data) => {
      qc.setQueryData(['boq-bdi', boqId], data);
      qc.invalidateQueries({ queryKey: ['boq-markups', boqId] });
      qc.invalidateQueries({ queryKey: ['boq', boqId] });
      qc.invalidateQueries({ queryKey: ['boq-cost-breakdown', boqId] });
      addToast({ type: 'success', title: t('brasil.bdi.saved', { defaultValue: 'BDI salvo' }) });
    },
    onError: () =>
      addToast({
        type: 'error',
        title: t('common.error', { defaultValue: 'Erro' }),
        message: t('brasil.bdi.save_error', { defaultValue: 'Não foi possível salvar o BDI.' }),
      }),
  });

  const result = query.data as (BdiResponse & { price_with_bdi?: string }) | undefined;
  const field = (key: keyof Omit<BdiComponentValues, 'taxes'>, label: string) => (
    <label className="flex flex-col gap-1 text-xs">
      <span>{label}</span>
      <Input
        inputMode="decimal"
        value={form[key]}
        disabled={readOnly}
        onChange={(e) =>
          setForm((current) => ({ ...current, [key]: e.target.value.replace(',', '.') }))
        }
        placeholder="0,0000"
      />
    </label>
  );

  const effectiveDirectCost =
    result?.direct_cost && Number(result.direct_cost) > 0
      ? Number(result.direct_cost)
      : (directCost ?? 0);
  const effectiveBdiAmount = result?.bdi_amount ? Number(result.bdi_amount) : 0;
  const effectiveTotal =
    result?.total_with_bdi ??
    result?.price_with_bdi ??
    (effectiveDirectCost + effectiveBdiAmount);

  return (
    <Card className="mt-6" data-testid="bdi-panel">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Calculator className="h-4 w-4" />
            {t('brasil.bdi.title', { defaultValue: 'BDI — Benefícios e Despesas Indiretas' })}
          </h2>
          <p className="text-xs text-content-secondary">
            {t('brasil.bdi.subtitle', {
              defaultValue: 'Componentes pela fórmula TCU 2.622/2013, aplicados ao orçamento.',
            })}
          </p>
        </div>
        {result?.bdi_percent ? <Badge>{pct(result.bdi_percent)}</Badge> : null}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {field('ac', 'Administração central (AC) %')}
        {field('s', 'Seguros (S) %')}
        {field('r', 'Riscos (R) %')}
        {field('g', 'Garantias (G) %')}
        {field('df', 'Despesas financeiras (DF) %')}
        {field('l', 'Lucro (L) %')}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
        <span>
          {t('brasil.bdi.direct', { defaultValue: 'Custo direto' })}:{' '}
          <strong>{brl(effectiveDirectCost)}</strong>
        </span>
        <span>
          {t('brasil.bdi.amount', { defaultValue: 'BDI' })}:{' '}
          <strong>{brl(effectiveBdiAmount)}</strong>
        </span>
        <span>
          {t('brasil.bdi.total', { defaultValue: 'Total com BDI' })}:{' '}
          <strong className="text-lg text-oe-blue">{brl(effectiveTotal)}</strong>
        </span>
        {!readOnly && (
          <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
            {t('common.save', { defaultValue: 'Salvar' })}
          </Button>
        )}
      </div>
    </Card>
  );
}
