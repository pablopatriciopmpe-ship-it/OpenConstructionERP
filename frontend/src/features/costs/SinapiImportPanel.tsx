import { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { FileSpreadsheet, Loader2, Upload } from 'lucide-react';
import { Button, Card, Input } from '@/shared/ui';
import { fetchWithAuth } from '@/shared/lib/api';

interface SinapiResult { inserted: number; unchanged: number; updated?: number; uf: string; regime: string; month: string }

async function importSinapi(file: File, uf: string, month: string, regime: string): Promise<SinapiResult> {
  const form = new FormData(); form.append('file', file); form.append('uf', uf); form.append('month', month); form.append('regime', regime);
  const response = await fetchWithAuth('/api/v1/costs/import/sinapi/', { method: 'POST', headers: { Accept: 'application/json' }, body: form });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Não foi possível importar o SINAPI.');
  return body as SinapiResult;
}

export function SinapiImportPanel() {
  const { t } = useTranslation(); const input = useRef<HTMLInputElement>(null); const [file, setFile] = useState<File | null>(null); const [uf, setUf] = useState('SP'); const [month, setMonth] = useState('2026-10'); const [regime, setRegime] = useState('desonerado'); const [result, setResult] = useState<SinapiResult | null>(null);
  const mutation = useMutation({ mutationFn: () => importSinapi(file as File, uf, month, regime), onSuccess: setResult });
  return <Card data-testid="sinapi-import-panel"><div className="flex items-center gap-2"><FileSpreadsheet className="h-4 w-4" /><div><h2 className="font-semibold">{t('brasil.sinapi.title', { defaultValue: 'Importar SINAPI' })}</h2><p className="text-xs text-content-secondary">{t('brasil.sinapi.subtitle', { defaultValue: 'Catálogo oficial brasileiro por UF, competência e regime.' })}</p></div></div><div className="mt-4 grid gap-3 sm:grid-cols-4"><label className="text-xs">UF<select className="oe-select mt-1" value={uf} onChange={(e) => setUf(e.target.value)}><option>SP</option><option>RJ</option><option>MG</option><option>PR</option><option>RS</option><option>BA</option></select></label><label className="text-xs">{t('brasil.sinapi.month', { defaultValue: 'Mês' })}<Input className="mt-1" type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></label><label className="text-xs">{t('brasil.sinapi.regime', { defaultValue: 'Regime' })}<select className="oe-select mt-1" value={regime} onChange={(e) => setRegime(e.target.value)}><option value="desonerado">{t('brasil.sinapi.desonerado', { defaultValue: 'Desonerado' })}</option><option value="nao_desonerado">{t('brasil.sinapi.nao_desonerado', { defaultValue: 'Não desonerado' })}</option></select></label><div className="flex items-end gap-2"><input ref={input} type="file" accept=".xlsx,.xls" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /><Button variant="secondary" onClick={() => input.current?.click()}><Upload className="mr-1 h-4 w-4" />{file?.name ?? t('brasil.sinapi.choose', { defaultValue: 'Escolher XLSX' })}</Button><Button onClick={() => mutation.mutate()} disabled={!file || mutation.isPending}>{mutation.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}{t('brasil.sinapi.import', { defaultValue: 'Importar' })}</Button></div></div>{result && <p className="mt-3 text-sm text-semantic-success">{t('brasil.sinapi.result', { defaultValue: '{{inserted}} inseridos, {{unchanged}} inalterados{{updated}}.', inserted: result.inserted, unchanged: result.unchanged, updated: result.updated ? `, ${result.updated} atualizados` : '' })}</p>}{mutation.error && <p className="mt-3 text-sm text-semantic-error">{(mutation.error as Error).message}</p>}</Card>;
}
