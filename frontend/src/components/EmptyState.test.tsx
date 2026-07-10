import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EmptyState } from '@/components/EmptyState';

describe('EmptyState', () => {
  it('renders the title and description', () => {
    render(
      <EmptyState
        title="Aucun ticket"
        description="Créez votre premier ticket."
      />
    );
    expect(screen.getByText('Aucun ticket')).toBeInTheDocument();
    expect(screen.getByText('Créez votre premier ticket.')).toBeInTheDocument();
  });

  it('renders a CTA button and calls onAction when clicked', async () => {
    const onAction = vi.fn();
    render(<EmptyState title="Vide" actionLabel="Créer" onAction={onAction} />);
    const cta = screen.getByRole('button', { name: 'Créer' });
    expect(cta).toBeInTheDocument();
    await userEvent.click(cta);
    expect(onAction).toHaveBeenCalledOnce();
  });

  it('omits the CTA when no action is provided', () => {
    render(<EmptyState title="Vide" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
