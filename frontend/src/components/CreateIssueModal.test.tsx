import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { CreateIssueModal } from '@/components/CreateIssueModal';
import { useUiStore } from '@/stores/uiStore';

function renderModal() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CreateIssueModal />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('CreateIssueModal', () => {
  beforeEach(() => {
    useUiStore.setState({ isCreateIssueOpen: false });
  });
  afterEach(() => {
    useUiStore.setState({ isCreateIssueOpen: false });
  });

  it('is closed by default (no dialog rendered)', () => {
    renderModal();
    expect(screen.queryByText('Créer un ticket')).not.toBeInTheDocument();
  });

  it('opens when the UI store flag is set', () => {
    renderModal();
    act(() => useUiStore.getState().openCreateIssue());
    expect(
      screen.getByRole('dialog', { name: /créer un ticket/i })
    ).toBeInTheDocument();
  });

  it('closes when the Annuler button is clicked', async () => {
    renderModal();
    act(() => useUiStore.getState().openCreateIssue());

    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }));

    expect(useUiStore.getState().isCreateIssueOpen).toBe(false);
    expect(screen.queryByText('Créer un ticket')).not.toBeInTheDocument();
  });
});
