import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { AppLayout } from '@/components/layout/AppLayout';

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/projects" element={<div>Contenu projet</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AppLayout', () => {
  it('renders the sidebar navigation', () => {
    renderLayout();
    expect(
      screen.getByRole('navigation', { name: 'Navigation principale' })
    ).toBeInTheDocument();
    expect(screen.getByText('Projets')).toBeInTheDocument();
  });

  it('renders the topbar with the Jirou logo and Créer action', () => {
    renderLayout();
    expect(screen.getByRole('link', { name: 'Jirou' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /créer/i })).toBeInTheDocument();
  });

  it('renders the routed child content (Outlet)', () => {
    renderLayout();
    expect(screen.getByText('Contenu projet')).toBeInTheDocument();
  });
});
