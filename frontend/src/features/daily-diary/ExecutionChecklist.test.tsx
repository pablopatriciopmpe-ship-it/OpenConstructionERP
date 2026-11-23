import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ExecutionChecklist } from './ExecutionChecklist';
import { createTask } from '@/features/tasks/api';
import { boqApi } from '@/features/boq/api';

vi.mock('@/features/tasks/api', () => ({
  fetchTasks: vi.fn().mockResolvedValue({
    items: [
      { id: 't1', title: 'Alvenaria de vedação', status: 'completed', project_id: 'proj-1' },
      { id: 't2', title: 'Reboco paulista', status: 'pending', project_id: 'proj-1' },
      { id: 't3', title: 'Pintura acrílica', status: 'pending', project_id: 'proj-1' },
    ],
    total: 3,
  }),
  completeTask: vi.fn().mockResolvedValue({}),
  updateTask: vi.fn().mockResolvedValue({}),
  createTask: vi.fn().mockResolvedValue({ id: 'new-t' }),
}));

vi.mock('@/features/boq/api', () => ({
  boqApi: {
    list: vi.fn().mockResolvedValue([{ id: 'boq-1', title: 'Orçamento Principal' }]),
    get: vi.fn().mockResolvedValue({
      id: 'boq-1',
      title: 'Orçamento Principal',
      positions: [
        { id: 'p1', description: 'Instalação de tomadas', unit: 'un', quantity: 20 },
        { id: 'p2', description: 'SEÇÃO ELÉTRICA', unit: 'section', quantity: 0 },
      ],
    }),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('ExecutionChecklist', () => {
  it('displays progress bar with completed vs total services', async () => {
    renderWithClient(<ExecutionChecklist projectId="proj-1" />);

    await waitFor(() => {
      expect(screen.getByText(/1 de 3 serviços concluídos \(33%\)/i)).toBeDefined();
    });

    expect(screen.getByText('Alvenaria de vedação')).toBeDefined();
    expect(screen.getByText('Reboco paulista')).toBeDefined();
    expect(screen.getByText('Pintura acrílica')).toBeDefined();
  });

  it('filters pending and completed tasks', async () => {
    renderWithClient(<ExecutionChecklist projectId="proj-1" />);

    await waitFor(() => {
      expect(screen.getByText('Alvenaria de vedação')).toBeDefined();
    });

    // Click "Pendentes" filter button
    const pendingBtn = screen.getByText('Pendentes').closest('button');
    expect(pendingBtn).not.toBeNull();
    if (pendingBtn) {
      fireEvent.click(pendingBtn);
    }

    expect(screen.queryByText('Alvenaria de vedação')).toBeNull();
    expect(screen.getByText('Reboco paulista')).toBeDefined();
    expect(screen.getByText('Pintura acrílica')).toBeDefined();
  });

  it('imports services from BOQ calling boqApi.get', async () => {
    renderWithClient(<ExecutionChecklist projectId="proj-1" />);

    // Wait for initial render and queries to load
    await waitFor(() => {
      expect(screen.getByText('Alvenaria de vedação')).toBeDefined();
    });

    const importBtn = await screen.findByRole('button', { name: /Importar serviços do Orçamento/i });
    fireEvent.click(importBtn);

    await waitFor(() => {
      expect(boqApi.get).toHaveBeenCalledWith('boq-1');
      expect(createTask).toHaveBeenCalledWith(
        expect.objectContaining({
          project_id: 'proj-1',
          title: 'Instalação de tomadas',
        })
      );
    });
  });
});
