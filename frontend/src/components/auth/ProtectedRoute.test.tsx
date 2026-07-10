import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { ProtectedRoute } from './ProtectedRoute';
import type { User } from '@/features/auth/types';
import { useAuthStore } from '@/stores/authStore';

const member: User = {
  id: 1,
  email: 'm@example.com',
  full_name: 'Member',
  avatar_url: null,
  role: 'member',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function renderGuarded(roles?: ('admin' | 'member' | 'viewer')[]) {
  return render(
    <MemoryRouter initialEntries={['/secret']}>
      <Routes>
        <Route element={<ProtectedRoute roles={roles} />}>
          <Route path="/secret" element={<div>SECRET</div>} />
        </Route>
        <Route path="/login" element={<div>LOGIN</div>} />
        <Route path="/projects" element={<div>PROJECTS</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  afterEach(() => {
    useAuthStore.setState({ status: 'unauthenticated', user: null });
  });

  it('redirige vers /login si non authentifié', () => {
    useAuthStore.setState({ status: 'unauthenticated', user: null });
    renderGuarded();
    expect(screen.queryByText('SECRET')).toBeNull();
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
  });

  it('laisse passer un utilisateur authentifié', () => {
    useAuthStore.setState({ status: 'authenticated', user: member });
    renderGuarded();
    expect(screen.getByText('SECRET')).toBeInTheDocument();
  });

  it('redirige vers /projects si le rôle est insuffisant', () => {
    useAuthStore.setState({ status: 'authenticated', user: member });
    renderGuarded(['admin']);
    expect(screen.queryByText('SECRET')).toBeNull();
    expect(screen.getByText('PROJECTS')).toBeInTheDocument();
  });
});
