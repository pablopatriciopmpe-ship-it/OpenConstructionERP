// Configurações > Documentos e modelos: dados comerciais da proposta da EMPRESA (por tenant).
// O timbrado (razão social, endereço, logo) continua no painel de documentos; aqui ficam o nome
// fantasia, o WhatsApp e os padrões da proposta: pagamento, validade, PIX e exclusões.
import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, CardContent, CardHeader, Input } from '@/shared/ui';
import { getErrorMessage } from '@/shared/lib/api';
import { useToastStore } from '@/stores/useToastStore';
import { saasApi } from './api';

type Form = {
  trade_name: string;
  whatsapp: string;
  proposal_payment_terms: string;
  proposal_validity: string;
  proposal_pix: string;
  proposal_exclusions: string;
};
const EMPTY: Form = {
  trade_name: '',
  whatsapp: '',
  proposal_payment_terms: '',
  proposal_validity: '',
  proposal_pix: '',
  proposal_exclusions: '',
};

export function CompanyCommercialCard() {
  const qc = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  const meQ = useQuery({ queryKey: ['saas', 'me'], queryFn: saasApi.me, retry: false, staleTime: 15_000 });
  const q = useQuery({ queryKey: ['saas', 'company'], queryFn: saasApi.company, retry: false, enabled: !!meQ.data });
  const [form, setForm] = useState<Form>(EMPTY);
  useEffect(() => {
    if (q.data) {
      const p = q.data.profile;
      setForm({
        trade_name: p.trade_name ?? '',
        whatsapp: p.whatsapp ?? '',
        proposal_payment_terms: p.proposal_payment_terms ?? '',
        proposal_validity: p.proposal_validity ?? '',
        proposal_pix: p.proposal_pix ?? '',
        proposal_exclusions: p.proposal_exclusions ?? '',
      });
    }
  }, [q.data]);
  const save = useMutation({
    mutationFn: () => saasApi.saveCompany({ ...form }),
    onSuccess: () => {
      addToast({ type: 'success', title: 'Dados comerciais salvos' });
      void qc.invalidateQueries({ queryKey: ['saas', 'company'] });
    },
    onError: (e) => addToast({ type: 'error', title: getErrorMessage(e) }),
  });
  if (!meQ.data || !q.data) return null; // sem empresa (instalação não-SaaS): nada a mostrar
  const canEdit = meQ.data.role === 'owner' || meQ.data.role === 'admin';
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const area = 'mt-1 block w-full rounded-lg border border-border-light bg-surface-primary px-3 py-2 text-sm';
  return (
    <Card data-testid="company-commercial-card">
      <CardHeader
        title="Dados comerciais da proposta"
        subtitle="Aparecem nas propostas e documentos desta empresa. Cada empresa tem os seus: nada é compartilhado."
      />
      <CardContent>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <Input label="Nome fantasia" value={form.trade_name} onChange={set('trade_name')} disabled={!canEdit} />
          <Input label="WhatsApp" value={form.whatsapp} onChange={set('whatsapp')} disabled={!canEdit} />
          <Input label="Validade da proposta" value={form.proposal_validity} onChange={set('proposal_validity')} placeholder="30 dias" disabled={!canEdit} />
          <Input label="Chave PIX" value={form.proposal_pix} onChange={set('proposal_pix')} disabled={!canEdit} />
          <label className="sm:col-span-2 text-sm text-content-secondary">
            Condições de pagamento
            <textarea className={area} rows={3} maxLength={600} value={form.proposal_payment_terms} onChange={set('proposal_payment_terms')} disabled={!canEdit} />
          </label>
          <label className="sm:col-span-2 text-sm text-content-secondary">
            Exclusões (o que a proposta não inclui)
            <textarea className={area} rows={4} maxLength={1200} value={form.proposal_exclusions} onChange={set('proposal_exclusions')} disabled={!canEdit} />
          </label>
          <div className="sm:col-span-2">
            {canEdit ? (
              <Button type="submit" variant="primary" loading={save.isPending}>Salvar dados comerciais</Button>
            ) : (
              <p className="text-xs text-content-tertiary">Somente o dono ou um administrador da empresa edita estes dados.</p>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
