import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useActiveProjectId } from '@/shared/hooks/useActiveProjectId';
import { boqApi } from '@/features/boq/api';

/** Offers belong to an estimate. Choose it before opening the offer editor. */
export function OffersPage() {
  const projectId = useActiveProjectId();
  const query = useQuery({ queryKey: ['offer-estimates', projectId],
    queryFn: () => boqApi.list(projectId!), enabled: Boolean(projectId) });
  return <section className="p-6 space-y-4">
    <h1 className="text-2xl font-semibold">Propostas</h1>
    <p>Selecione o orçamento para preparar ou consultar sua proposta.</p>
    {!projectId ? <Link to="/projects">Selecione uma obra</Link>
      : query.isPending ? <p role="status">Carregando orçamentos…</p>
      : query.isError ? <p role="alert">Não foi possível carregar os orçamentos. <button onClick={() => void query.refetch()}>Tentar novamente</button></p>
      : query.data?.length ? <ul className="space-y-2">{query.data.map((boq) =>
        <li key={boq.id}><Link className="underline text-oe-blue" to={`/boq/${encodeURIComponent(boq.id)}/offer?project=${encodeURIComponent(projectId)}`}>{boq.name}</Link></li>)}</ul>
      : <p>Nenhum orçamento nesta obra. <Link className="underline" to="/boq">Criar orçamento</Link></p>}
  </section>;
}
