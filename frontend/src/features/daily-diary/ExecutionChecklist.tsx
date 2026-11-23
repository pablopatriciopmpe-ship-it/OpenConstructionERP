import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  Circle,
  Search,
  Filter,
  Calendar,
  Check,
  AlertCircle,
  ListTodo,
  ExternalLink,
  Plus,
} from 'lucide-react';
import { Card, Button, Badge } from '@/shared/ui';
import { fetchTasks, completeTask, updateTask, createTask, type Task } from '@/features/tasks/api';
import { boqApi } from '@/features/boq/api';
import { useToastStore } from '@/stores/useToastStore';
import { getErrorMessage } from '@/shared/lib/api';

interface ExecutionChecklistProps {
  projectId: string;
}

type StatusFilter = 'all' | 'pending' | 'completed';

export function ExecutionChecklist({ projectId }: ExecutionChecklistProps) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [isImporting, setIsImporting] = useState(false);

  const tasksQ = useQuery({
    queryKey: ['project-tasks', projectId],
    queryFn: () => fetchTasks({ project_id: projectId }),
    enabled: Boolean(projectId),
  });

  const boqQ = useQuery({
    queryKey: ['project-boq', projectId],
    queryFn: () => boqApi.list(projectId),
    enabled: Boolean(projectId),
  });

  const tasks = tasksQ.data?.items ?? [];

  const toggleTaskMutation = useMutation({
    mutationFn: async ({ id, completed }: { id: string; completed: boolean }) => {
      if (completed) {
        return completeTask(id);
      }
      return updateTask(id, { status: 'open' });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
    },
    onError: (err) => {
      addToast({
        type: 'error',
        title: t('common.error', { defaultValue: 'Erro ao atualizar serviço' }),
        message: getErrorMessage(err),
      });
    },
  });

  const importFromBoq = async () => {
    const estimates = boqQ.data ?? [];
    if (estimates.length === 0) {
      addToast({
        type: 'info',
        title: t('daily_diary.no_boq_title', { defaultValue: 'Nenhuma planilha orçamentária encontrada' }),
        message: t('daily_diary.no_boq_desc', { defaultValue: 'Crie um orçamento antes de importar serviços para o checklist.' }),
      });
      return;
    }
    setIsImporting(true);
    try {
      const primaryBoq = estimates[0];
      const positions = await boqApi.getPositions(primaryBoq.id);
      const leafItems = positions.filter((p) => p.unit !== 'section');
      let created = 0;
      for (const pos of leafItems.slice(0, 30)) {
        await createTask({
          project_id: projectId,
          title: pos.description,
          task_type: 'task',
          priority: 'normal',
          metadata: {
            source: 'boq',
            boq_id: primaryBoq.id,
            position_id: pos.id,
            quantity: pos.quantity,
            unit: pos.unit,
          },
        });
        created += 1;
      }
      addToast({
        type: 'success',
        title: t('daily_diary.services_imported', { defaultValue: 'Serviços importados' }),
        message: `${created} serviço(s) adicionados ao checklist de execução.`,
      });
      void qc.invalidateQueries({ queryKey: ['project-tasks', projectId] });
    } catch (err) {
      addToast({
        type: 'error',
        title: t('common.error', { defaultValue: 'Erro na importação' }),
        message: getErrorMessage(err),
      });
    } finally {
      setIsImporting(false);
    }
  };

  const total = tasks.length;
  const completedCount = tasks.filter((t) => t.status === 'completed').length;
  const percent = total > 0 ? Math.round((completedCount / total) * 100) : 0;

  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      const isCompleted = t.status === 'completed';
      if (filter === 'pending' && isCompleted) return false;
      if (filter === 'completed' && !isCompleted) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        return t.title.toLowerCase().includes(q) || (t.description && t.description.toLowerCase().includes(q));
      }
      return true;
    });
  }, [tasks, filter, search]);

  return (
    <div className="space-y-5" data-testid="execution-checklist">
      {/* Header Card com Progresso Visual */}
      <Card>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-content-primary flex items-center gap-2">
              <CheckCircle2 className="text-[#156D61]" size={20} />
              {t('daily_diary.tab_checklist', { defaultValue: 'Checklist de Execução de Serviços' })}
            </h2>
            <p className="text-sm text-content-secondary mt-1">
              {t('daily_diary.checklist_progress', {
                defaultValue: '{{completed}} de {{total}} serviços concluídos ({{percent}}%)',
                completed: completedCount,
                total,
                percent,
              })}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {total === 0 && (
              <Button
                variant="primary"
                onClick={importFromBoq}
                loading={isImporting}
                icon={<Plus size={16} />}
              >
                {t('daily_diary.import_boq_services', { defaultValue: 'Importar serviços do Orçamento' })}
              </Button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4">
          <div className="w-full bg-surface-secondary rounded-full h-3 overflow-hidden border border-border-light">
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                percent === 100 ? 'bg-emerald-500' : 'bg-[#156D61]'
              }`}
              style={{ width: `${percent}%` }}
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>

        {/* Filters and Search */}
        <div className="mt-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-border-light">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0" role="tablist">
            {(
              [
                ['all', 'Todos', total],
                ['pending', 'Pendentes', total - completedCount],
                ['completed', 'Concluídos', completedCount],
              ] as [StatusFilter, string, number][]
            ).map(([f, label, count]) => (
              <button
                key={f}
                type="button"
                className={`min-h-[44px] px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 shrink-0 ${
                  filter === f
                    ? 'bg-[#156D61] text-white shadow-sm'
                    : 'bg-surface-secondary text-content-secondary hover:bg-surface-secondary/80 hover:text-content-primary'
                }`}
                onClick={() => setFilter(f)}
              >
                <span>{label}</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] font-semibold ${
                    filter === f ? 'bg-white/20 text-white' : 'bg-surface-primary text-content-tertiary'
                  }`}
                >
                  {count}
                </span>
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-64">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar serviço..."
              className="oe-input w-full pl-8 text-xs h-10"
            />
          </div>
        </div>
      </Card>

      {/* Task List */}
      {filteredTasks.length === 0 ? (
        <Card padding="md">
          <div className="py-10 text-center">
            <ListTodo size={36} className="mx-auto text-content-tertiary mb-2" />
            <p className="text-sm font-medium text-content-primary">
              {total === 0
                ? 'Nenhum serviço lançado no checklist desta obra'
                : 'Nenhum serviço encontrado para o filtro atual'}
            </p>
            <p className="text-xs text-content-secondary mt-1">
              {total === 0
                ? 'Importe os itens da planilha orçamentária ou crie tarefas na aba de Tarefas da obra.'
                : 'Tente alterar a busca ou os filtros acima.'}
            </p>
            {total === 0 && (
              <div className="mt-4">
                <Button variant="secondary" onClick={importFromBoq} loading={isImporting}>
                  Importar itens do Orçamento
                </Button>
              </div>
            )}
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {filteredTasks.map((task) => {
            const isCompleted = task.status === 'completed';
            return (
              <div
                key={task.id}
                className={`flex items-center gap-3 p-3.5 rounded-lg border transition-all ${
                  isCompleted
                    ? 'bg-surface-secondary/50 border-border-light opacity-80'
                    : 'bg-surface-primary border-border hover:border-[#156D61]/40 shadow-sm'
                }`}
              >
                <button
                  type="button"
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center -ml-2 cursor-pointer focus:outline-none"
                  aria-label={isCompleted ? 'Desmarcar serviço' : 'Marcar serviço como concluído'}
                  onClick={() => toggleTaskMutation.mutate({ id: task.id, completed: !isCompleted })}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="text-emerald-600 fill-emerald-100 dark:fill-emerald-950/40" size={22} />
                  ) : (
                    <Circle className="text-content-tertiary hover:text-[#156D61]" size={22} />
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-sm font-medium ${
                        isCompleted ? 'line-through text-content-tertiary' : 'text-content-primary'
                      }`}
                    >
                      {task.title}
                    </span>
                    {task.metadata?.unit && task.metadata?.quantity && (
                      <Badge variant="neutral" size="sm">
                        {String(task.metadata.quantity)} {String(task.metadata.unit).toLowerCase()}
                      </Badge>
                    )}
                  </div>
                  {task.description && (
                    <p className="text-xs text-content-secondary mt-0.5 line-clamp-1">{task.description}</p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isCompleted ? (
                    <Badge variant="success" size="sm">
                      Concluído
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      Pendente
                    </Badge>
                  )}
                  {task.due_date && (
                    <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-content-tertiary">
                      <Calendar size={12} />
                      {task.due_date.slice(0, 10)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
