// Autoatendimento do SaaS (v0.3-D): tipos e chamadas da API /v1/saas.
import { apiDelete, apiGet, apiPatch, apiPost } from '@/shared/lib/api';

export type TenantState =
  | 'trial'
  | 'trial_expired'
  | 'active'
  | 'past_due'
  | 'canceled'
  | 'suspended'
  | 'deleted';

export interface SaasUsageItem {
  used: number;
  limit: number | null;
}

export interface SaasMe {
  tenant: { id: string; legal_name: string; status: string; plan_code: string; trial_ends_at: string | null };
  role: 'owner' | 'admin' | 'member' | 'viewer';
  write_access: boolean;
  state: TenantState;
  trial_days_left: number | null;
  plan: { code: string; name: string; max_users: number | null; max_projects: number | null; ai_credits: number };
  usage: {
    users: SaasUsageItem;
    projects: SaasUsageItem;
    ai_credits: { used: number; limit: number; topup: number; state: 'ok' | 'alert' | 'blocked' };
  };
}

export interface SaasMember {
  user_id: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  email: string;
  full_name: string;
  is_active: boolean;
}

export interface SignupBody {
  full_name: string;
  email: string;
  password: string;
  company_name: string;
  cnpj?: string | null;
  accept_terms: boolean;
  website?: string;
}

export interface SignupResult {
  tenant_id?: string;
  status: string;
  plan_code?: string;
  trial_ends_at?: string;
  ai_credits_trial?: number;
  email_confirmation: 'sent' | 'pending';
  account_active: boolean;
}

export interface MasterTenant {
  id: string;
  legal_name: string;
  cnpj: string | null;
  status: string;
  plan_code: string;
  state: TenantState;
  trial_days_left: number | null;
  write_access: boolean;
  deleted_at: string | null;
  usage: SaasMe['usage'];
}

export const saasApi = {
  me: () => apiGet<SaasMe>('/v1/saas/me'),
  members: () => apiGet<SaasMember[]>('/v1/saas/members'),
  addMember: (body: { email: string; full_name: string; password: string; role: 'editor' | 'viewer' }) =>
    apiPost<{ user_id: string; role: string }>('/v1/saas/members', body),
  changeRole: (userId: string, role: 'editor' | 'viewer') =>
    apiPatch<{ user_id: string; role: string }>(`/v1/saas/members/${userId}`, { role }),
  removeMember: (userId: string) => apiDelete(`/v1/saas/members/${userId}`),
  masterTenants: (includeDeleted: boolean) =>
    apiGet<MasterTenant[]>(`/v1/saas/master/tenants${includeDeleted ? '?include_deleted=true' : ''}`),
  masterRename: (id: string, legal_name: string) =>
    apiPatch<{ id: string; legal_name: string }>(`/v1/saas/master/tenants/${id}`, { legal_name }),
  masterDelete: (id: string, reason: string, force = false) =>
    apiDelete<{ id: string; deleted_at: string }>(`/v1/saas/master/tenants/${id}`, { reason, force }),
  masterRestore: (id: string) => apiPost<{ id: string; status: string }>(`/v1/saas/master/tenants/${id}/restore`, {}),
};

/** Papel mostrado na tela: o papel interno "member" aparece como "Editor". */
export function roleLabel(role: SaasMember['role']): string {
  return { owner: 'Dono', admin: 'Administrador', member: 'Editor', viewer: 'Visualizador' }[role];
}

export function stateLabel(state: TenantState): string {
  return {
    trial: 'Teste grátis',
    trial_expired: 'Teste encerrado',
    active: 'Assinatura ativa',
    past_due: 'Pagamento pendente',
    canceled: 'Assinatura cancelada',
    suspended: 'Suspensa',
    deleted: 'Excluída',
  }[state];
}
