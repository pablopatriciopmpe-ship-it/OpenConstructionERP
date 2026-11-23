import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ExecutionChecklist } from './ExecutionChecklist';

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
  createTask: vi.fn().mockResolvedValue({}),
}));

vi.mock('@/features/boq/api', () => ({
  boqApi: {
    list: vi.fn().mockResolvedValue([{ id: 'boq-1', title: 'Orçamento Principal' }]),
    get: vi.fn().mockResolvedValue({ items: [] }),
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
});
