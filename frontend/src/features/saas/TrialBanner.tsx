// Faixa de aviso do plano: dias de teste restantes, teste encerrado (somente leitura) ou empresa excluída.
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuthStore } from '@/stores/useAuthStore';
import { saasApi } from './api';

export function TrialBanner() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const q = useQuery({
    queryKey: ['saas', 'me'],
    queryFn: saasApi.me,
    enabled: isAuthenticated,
    retry: false,
    staleTime: 60_000,
  });
  const me = q.data;
  if (!me) return null;
  const to = '/settings?tab=team';
  if (me.state === 'trial' && me.trial_days_left != null && me.trial_days_left <= 7) {
    return (
      <div role="status" data-testid="trial-banner" className="bg-oe-blue/10 px-4 py-2 text-center text-sm text-content-primary">
        Seu teste grátis termina em <strong>{me.trial_days_left} {me.trial_days_left === 1 ? 'dia' : 'dias'}</strong>.{' '}
        <Link to={to} className="font-medium text-oe-blue underline">Ver plano</Link>
      </div>
    );
  }
  if (me.state === 'trial_expired' || me.state === 'canceled' || me.state === 'suspended') {
    return (
      <div role="alert" data-testid="readonly-banner" className="bg-semantic-warning/15 px-4 py-2 text-center text-sm text-content-primary">
        Seu acesso está em <strong>modo somente leitura</strong>. Assine um plano para voltar a editar.{' '}
        <Link to={to} className="font-medium text-oe-blue underline">Ver plano</Link>
      </div>
    );
  }
  if (me.state === 'deleted') {
    return (
      <div role="alert" data-testid="deleted-banner" className="bg-semantic-error/15 px-4 py-2 text-center text-sm text-content-primary">
        Esta empresa foi excluída. Fale com o suporte para restaurar o acesso.
      </div>
    );
  }
  return null;
}
