// Configurações > Equipe e plano: plano, uso (usuários, obras, créditos de IA), dias de teste e membros.
import { useState, type FormEvent, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Card, CardContent, CardHeader, Input } from '@/shared/ui';
import type { BadgeVariant } from '@/shared/ui';
import { ApiError, getErrorMessage } from '@/shared/lib/api';
import { useToastStore } from '@/stores/useToastStore';
import { roleLabel, saasApi, stateLabel, type SaasMe, type SaasUsageItem } from './api';

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const color = pct >= 100 ? 'bg-semantic-error' : pct >= 80 ? 'bg-semantic-warning' : 'bg-oe-blue';
  return (
    <div data-testid={`usage-${label}`}>
      <div className="flex justify-between text-sm">
        <span className="text-content-secondary">{label}</span>
        <span className="font-medium text-content-primary">
          {used} / {limit ?? 'ilimitado'}
        </span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-surface-secondary overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${limit ? pct : 0}%` }} />
      </div>
    </div>
  );
}

const STATE_VARIANT: Record<SaasMe['state'], BadgeVariant> = {
  trial: 'blue',
  trial_expired: 'warning',
  active: 'success',
  past_due: 'warning',
  canceled: 'error',
  suspended: 'error',
  deleted: 'error',
};

function PlanCard({ me }: { me: SaasMe }) {
  const usage = me.usage;
  const credits: SaasUsageItem = { used: usage.ai_credits.used, limit: usage.ai_credits.limit + usage.ai_credits.topup };
  return (
    <Card>
      <CardHeader
        title={`${me.tenant.legal_name}`}
        subtitle={`Plano ${me.plan.name}`}
        action={<Badge variant={STATE_VARIANT[me.state]}>{stateLabel(me.state)}</Badge>}
      />
      <CardContent>
        <div className="space-y-3">
          {me.state === 'trial' && me.trial_days_left != null && (
            <p className="text-sm text-content-secondary" data-testid="trial-days">
              Teste grátis: <strong>{me.trial_days_left} {me.trial_days_left === 1 ? 'dia restante' : 'dias restantes'}</strong>. Sem cartão e sem cobrança
              automática. Os créditos de IA do teste são limitados a {me.plan.ai_credits}.
            </p>
          )}
          {me.state === 'trial_expired' && (
            <p className="text-sm text-semantic-warning" data-testid="trial-expired">
              Seu teste grátis terminou. Seus dados continuam disponíveis para leitura; assine um plano para voltar a editar.
            </p>
          )}
          <UsageBar label="Usuários" used={usage.users.used} limit={usage.users.limit} />
          <UsageBar label="Obras ativas" used={usage.projects.used} limit={usage.projects.limit} />
          <UsageBar label="Créditos de IA" used={credits.used} limit={credits.limit} />
          {usage.ai_credits.state === 'alert' && (
            <p className="text-xs text-semantic-warning">Você já usou mais de 80% dos créditos de IA.</p>
          )}
          {usage.ai_credits.topup > 0 && (
            <p className="text-xs text-content-tertiary">Inclui {usage.ai_credits.topup} créditos avulsos.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function MembersCard({ me }: { me: SaasMe }) {
  const qc = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  const canManage = me.role === 'owner' || me.role === 'admin';
  const membersQ = useQuery({ queryKey: ['saas', 'members'], queryFn: saasApi.members, enabled: canManage });
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'editor' as 'editor' | 'viewer' });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['saas'] });
  };
  const add = useMutation({
    mutationFn: () => saasApi.addMember(form),
    onSuccess: () => {
      addToast({ type: 'success', title: 'Membro adicionado' });
      setForm({ email: '', full_name: '', password: '', role: 'editor' });
      refresh();
    },
    onError: (e) => addToast({ type: 'error', title: errorText(e) }),
  });
  const change = useMutation({
    mutationFn: (v: { id: string; role: 'editor' | 'viewer' }) => saasApi.changeRole(v.id, v.role),
    onSuccess: refresh,
    onError: (e) => addToast({ type: 'error', title: errorText(e) }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => saasApi.removeMember(id),
    onSuccess: () => {
      addToast({ type: 'success', title: 'Membro removido' });
      refresh();
    },
    onError: (e) => addToast({ type: 'error', title: errorText(e) }),
  });

  if (!canManage) {
    return (
      <Card>
        <CardHeader title="Equipe" subtitle="Somente o dono ou um administrador da empresa gerencia a equipe." />
      </Card>
    );
  }
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  const full = me.usage.users.limit != null && me.usage.users.used >= me.usage.users.limit;
  return (
    <Card>
      <CardHeader
        title="Equipe"
        subtitle={`${me.usage.users.used} de ${me.usage.users.limit ?? 'ilimitados'} usuários do plano`}
      />
      <CardContent>
        <ul className="divide-y divide-border-light" data-testid="members-list">
          {(membersQ.data ?? []).map((m) => (
            <li key={m.user_id} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-content-primary">{m.full_name || m.email}</div>
                <div className="truncate text-xs text-content-tertiary">{m.email}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {m.role === 'owner' ? (
                  <Badge variant="purple">{roleLabel(m.role)}</Badge>
                ) : (
                  <>
                    <select
                      aria-label={`Papel de ${m.email}`}
                      className="rounded-lg border border-border-light bg-surface-primary px-2 py-1 text-sm"
                      value={m.role === 'viewer' ? 'viewer' : 'editor'}
                      onChange={(e) => change.mutate({ id: m.user_id, role: e.target.value as 'editor' | 'viewer' })}
                    >
                      <option value="editor">Editor</option>
                      <option value="viewer">Visualizador</option>
                    </select>
                    <Button size="sm" variant="ghost" onClick={() => remove.mutate(m.user_id)}>
                      Remover
                    </Button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>

        <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2" data-testid="add-member-form">
          <h3 className="sm:col-span-2 text-sm font-semibold text-content-primary">Adicionar membro</h3>
          <Input label="Nome" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          <Input
            label="E-mail"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <Input
            label="Senha provisória"
            type="password"
            required
            minLength={10}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            hint="Mínimo de 10 caracteres, com letra e número. Combine a troca com a pessoa."
          />
          <label className="text-sm text-content-secondary">
            Papel
            <select
              className="mt-1 block w-full rounded-lg border border-border-light bg-surface-primary px-3 py-2 text-sm"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as 'editor' | 'viewer' })}
            >
              <option value="editor">Editor (edita orçamentos e obras)</option>
              <option value="viewer">Visualizador (somente leitura)</option>
            </select>
          </label>
          <div className="sm:col-span-2 flex items-center gap-3">
            <Button type="submit" variant="primary" loading={add.isPending} disabled={!me.write_access || (full && form.role === 'editor')}>
              Adicionar à equipe
            </Button>
            {full && form.role === 'editor' && (
              <span className="text-xs text-semantic-warning">Limite de usuários do plano atingido.</span>
            )}
            {!me.write_access && <span className="text-xs text-semantic-warning">Assine um plano para adicionar membros.</span>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const body = e.body as { detail?: { message?: string } | string } | null;
    const d = body?.detail;
    if (d && typeof d === 'object' && d.message) return d.message;
  }
  return getErrorMessage(e);
}

/** Painel de equipe e plano da empresa; sem empresa (instalação não-SaaS) mostra o ``fallback``. */
export function TeamPlanPanel({ fallback }: { fallback?: ReactNode }) {
  const meQ = useQuery({ queryKey: ['saas', 'me'], queryFn: saasApi.me, retry: false, staleTime: 15_000 });
  if (meQ.isLoading) return null;
  if (!meQ.data) return <>{fallback}</>; // 404: usuário sem empresa
  return (
    <div className="space-y-4" data-testid="team-plan-panel">
      <PlanCard me={meQ.data} />
      <MembersCard me={meQ.data} />
      {fallback}
    </div>
  );
}
