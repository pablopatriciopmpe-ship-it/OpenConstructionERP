// Painel master (dono do SaaS): empresas, renomear, excluir de forma lógica e restaurar.
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Card, CardContent, CardHeader, Input } from '@/shared/ui';
import { getErrorMessage } from '@/shared/lib/api';
import { useToastStore } from '@/stores/useToastStore';
import { saasApi, stateLabel, type MasterTenant } from './api';

export function MasterPanelPage() {
  const qc = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);
  const q = useQuery({ queryKey: ['saas', 'master', includeDeleted], queryFn: () => saasApi.masterTenants(includeDeleted) });
  const done = (msg: string) => {
    addToast({ type: 'success', title: msg });
    void qc.invalidateQueries({ queryKey: ['saas', 'master'] });
  };
  const fail = (e: unknown) => addToast({ type: 'error', title: getErrorMessage(e) });
  const rename = useMutation({
    mutationFn: (v: { id: string; name: string }) => saasApi.masterRename(v.id, v.name),
    onSuccess: () => {
      setEditing(null);
      done('Empresa renomeada');
    },
    onError: fail,
  });
  const del = useMutation({
    mutationFn: (v: { t: MasterTenant; force: boolean }) => saasApi.masterDelete(v.t.id, 'Exclusão pelo painel master', v.force),
    onSuccess: () => done('Empresa excluída (reversível)'),
    onError: fail,
  });
  const restore = useMutation({
    mutationFn: (id: string) => saasApi.masterRestore(id),
    onSuccess: () => done('Empresa restaurada'),
    onError: fail,
  });
  const onDelete = (t: MasterTenant) => {
    if (!window.confirm(`Excluir "${t.legal_name}"? É uma exclusão lógica: nada é apagado e você pode restaurar depois. Os usuários da empresa perdem o acesso.`)) return;
    del.mutate({ t, force: false });
  };
  return (
    <div className="space-y-4 max-w-5xl" data-testid="master-panel">
      <Card>
        <CardHeader
          title="Empresas clientes"
          subtitle="Renomear, excluir (reversível) e restaurar. Toda ação fica na trilha de auditoria."
          action={
            <label className="flex items-center gap-2 text-sm text-content-secondary">
              <input type="checkbox" checked={includeDeleted} onChange={(e) => setIncludeDeleted(e.target.checked)} />
              Mostrar excluídas
            </label>
          }
        />
        <CardContent>
          {q.isLoading && <p className="text-sm text-content-tertiary">Carregando…</p>}
          {q.isError && <p className="text-sm text-semantic-error">Acesso restrito ao dono do SaaS.</p>}
          <ul className="divide-y divide-border-light" data-testid="master-tenants">
            {(q.data ?? []).map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  {editing?.id === t.id ? (
                    <form
                      className="flex items-center gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        rename.mutate({ id: t.id, name: editing.name });
                      }}
                    >
                      <Input aria-label="Novo nome" value={editing.name} onChange={(e) => setEditing({ id: t.id, name: e.target.value })} required minLength={2} />
                      <Button size="sm" type="submit" variant="primary" loading={rename.isPending}>Salvar</Button>
                      <Button size="sm" type="button" variant="ghost" onClick={() => setEditing(null)}>Cancelar</Button>
                    </form>
                  ) : (
                    <div className="truncate text-sm font-medium text-content-primary">{t.legal_name}</div>
                  )}
                  <div className="text-xs text-content-tertiary">
                    Plano {t.plan_code} · {t.usage.users.used} usuário(s) · {t.usage.projects.used} obra(s)
                    {t.trial_days_left != null ? ` · ${t.trial_days_left} dia(s) de teste` : ''}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={t.state === 'deleted' ? 'error' : t.state === 'trial' ? 'blue' : 'neutral'}>{stateLabel(t.state)}</Badge>
                  {t.state === 'deleted' ? (
                    <Button size="sm" variant="secondary" onClick={() => restore.mutate(t.id)}>Restaurar</Button>
                  ) : (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => setEditing({ id: t.id, name: t.legal_name })}>Renomear</Button>
                      <Button size="sm" variant="danger" onClick={() => onDelete(t)}>Excluir</Button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
